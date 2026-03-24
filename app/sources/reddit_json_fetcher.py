"""Optional Reddit JSON collection with explicit validation and graceful degradation."""

from __future__ import annotations

import logging
import time
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import requests

from app.constants import (
    DEFAULT_REDDIT_BASE_URL,
    REDDIT_LISTING_KIND,
    REDDIT_MINIMUM_CHILD_KIND,
    REDDIT_REQUIRED_FIELDS,
)
from app.health import HealthTracker
from app.models import (
    AppConfig,
    FetchOutcome,
    RedditEndpointConfig,
    RedditValidationCheck,
    SubredditConfig,
)
from app.utils import clean_text, request_with_retry, safe_int


def build_reddit_url(subreddit: str, endpoint: RedditEndpointConfig) -> str:
    return f"{DEFAULT_REDDIT_BASE_URL}/r/{subreddit}/{endpoint.path}"


def validate_listing_payload(payload: Any) -> tuple[bool, list[str], list[dict[str, Any]], str]:
    if not isinstance(payload, dict):
        return False, list(REDDIT_REQUIRED_FIELDS), [], "payload is not a JSON object"
    if payload.get("kind") != REDDIT_LISTING_KIND:
        return False, ["kind"], [], "unexpected top-level kind"
    data = payload.get("data")
    if not isinstance(data, dict):
        return False, ["data"], [], "missing data object"
    children = data.get("children")
    if not isinstance(children, list):
        return False, ["data.children"], [], "missing children list"

    missing_fields: set[str] = set()
    valid_children: list[dict[str, Any]] = []
    for child in children:
        if not isinstance(child, dict):
            continue
        if child.get("kind") != REDDIT_MINIMUM_CHILD_KIND:
            continue
        child_data = child.get("data")
        if not isinstance(child_data, dict):
            missing_fields.add("child.data")
            continue
        for field in REDDIT_REQUIRED_FIELDS:
            if child_data.get(field) in (None, ""):
                missing_fields.add(field)
        valid_children.append(child_data)
    diagnosis = "ok" if valid_children and not missing_fields else "incomplete_payload"
    return bool(valid_children), sorted(missing_fields), valid_children, diagnosis


def parse_reddit_listing(
    *,
    payload: dict[str, Any],
    subreddit: str,
    category: str,
    endpoint_name: str,
    time_window_hours: int,
    fetched_at: datetime | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    fetched_reference = fetched_at or datetime.now(tz=UTC)
    is_valid, missing_fields, children, _ = validate_listing_payload(payload)
    if not is_valid:
        return [], missing_fields

    cutoff = fetched_reference - timedelta(hours=time_window_hours)
    items: list[dict[str, Any]] = []
    for child_data in children:
        created_at = datetime.fromtimestamp(float(child_data["created_utc"]), tz=UTC)
        if created_at < cutoff:
            continue
        if child_data.get("stickied"):
            continue

        permalink = clean_text(child_data.get("permalink", ""))
        full_permalink = (
            f"{DEFAULT_REDDIT_BASE_URL}{permalink}" if permalink.startswith("/") else permalink
        )
        items.append(
            {
                "id": clean_text(child_data.get("id", "")),
                "source_type": "reddit",
                "subreddit": subreddit,
                "source": f"r/{subreddit}",
                "category": category,
                "endpoint": endpoint_name,
                "title": clean_text(child_data.get("title", "")),
                "score": safe_int(child_data.get("score")),
                "num_comments": safe_int(child_data.get("num_comments")),
                "permalink": full_permalink,
                "external_url": clean_text(child_data.get("url", "")),
                "created_utc": created_at,
                "domain": clean_text(child_data.get("domain", "")),
                "summary": clean_text(child_data.get("selftext", ""))[:240],
                "over_18": bool(child_data.get("over_18", False)),
                "stickied": bool(child_data.get("stickied", False)),
                "raw": child_data,
            }
        )
    return items, missing_fields


def request_reddit_listing(
    *,
    app_config: AppConfig,
    subreddit: str,
    endpoint: RedditEndpointConfig,
    logger: logging.Logger,
    session: requests.Session,
) -> tuple[dict[str, Any] | None, FetchOutcome]:
    url = build_reddit_url(subreddit, endpoint)
    params = dict(endpoint.params)
    headers = {
        "User-Agent": app_config.reddit_user_agent,
        "Accept": "application/json",
    }
    try:
        response, elapsed_ms = request_with_retry(
            session=session,
            url=url,
            params=params,
            headers=headers,
            timeout=app_config.request_timeout_seconds,
            max_retries=app_config.max_retries,
            backoff_base_seconds=app_config.backoff_base_seconds,
            logger=logger,
        )
        status_code = response.status_code
        content_type = response.headers.get("content-type", "")
        if status_code >= 400:
            return None, FetchOutcome(
                source=f"r/{subreddit}",
                status="http_error",
                detail=f"http_{status_code}",
                elapsed_ms=elapsed_ms,
                endpoint=endpoint.name,
                status_code=status_code,
                content_type=content_type,
            )
        if "json" not in content_type.lower():
            snippet = response.text[:80].strip().lower()
            detail = "html_response" if snippet.startswith("<") else "invalid_content_type"
            return None, FetchOutcome(
                source=f"r/{subreddit}",
                status="unexpected_content",
                detail=detail,
                elapsed_ms=elapsed_ms,
                endpoint=endpoint.name,
                status_code=status_code,
                content_type=content_type,
            )
        try:
            payload = response.json()
        except ValueError:
            return None, FetchOutcome(
                source=f"r/{subreddit}",
                status="invalid_json",
                detail="json_decode_error",
                elapsed_ms=elapsed_ms,
                endpoint=endpoint.name,
                status_code=status_code,
                content_type=content_type,
            )
        return payload, FetchOutcome(
            source=f"r/{subreddit}",
            status="ok",
            elapsed_ms=elapsed_ms,
            endpoint=endpoint.name,
            status_code=status_code,
            content_type=content_type,
        )
    except requests.Timeout:
        return None, FetchOutcome(
            source=f"r/{subreddit}",
            status="timeout",
            detail="timeout",
            endpoint=endpoint.name,
        )
    except requests.RequestException as exc:
        return None, FetchOutcome(
            source=f"r/{subreddit}",
            status="network_error",
            detail=type(exc).__name__,
            endpoint=endpoint.name,
        )


def fetch_reddit_items(
    *,
    app_config: AppConfig,
    subreddits: list[SubredditConfig],
    endpoints: list[RedditEndpointConfig],
    time_window_hours: int,
    request_delay_seconds: float,
    max_items_per_category: int,
    max_requests_per_run: int,
    logger: logging.Logger,
    health_tracker: HealthTracker,
) -> tuple[list[dict[str, Any]], list[FetchOutcome]]:
    session = requests.Session()
    collected: list[dict[str, Any]] = []
    outcomes: list[FetchOutcome] = []
    enabled_endpoints = [endpoint for endpoint in endpoints if endpoint.enabled]
    category_totals: dict[str, int] = {}
    seen_post_ids: set[str] = set()
    requests_made = 0

    for subreddit in subreddits:
        if requests_made >= max_requests_per_run:
            logger.warning(
                "Reddit request budget reached (%s/%s). Stopping early to reduce runner instability.",
                requests_made,
                max_requests_per_run,
            )
            break
        if category_totals.get(subreddit.category, 0) >= max_items_per_category:
            logger.info(
                "Reddit category target already satisfied for %s (%s items). Skipping r/%s.",
                subreddit.category,
                category_totals[subreddit.category],
                subreddit.name,
            )
            continue

        subreddit_failures = 0
        subreddit_collected = 0
        for endpoint in enabled_endpoints:
            if requests_made >= max_requests_per_run:
                break
            if category_totals.get(subreddit.category, 0) >= max_items_per_category:
                break
            if subreddit_collected >= subreddit.limit:
                break

            requests_made += 1
            payload, outcome = request_reddit_listing(
                app_config=app_config,
                subreddit=subreddit.name,
                endpoint=endpoint,
                logger=logger,
                session=session,
            )
            if payload is None:
                subreddit_failures += 1
                outcomes.append(outcome)
                health_tracker.record_failure(
                    f"r/{subreddit.name}",
                    f"{outcome.status}:{outcome.detail or 'unknown'}",
                )
                logger.warning(
                    "Reddit endpoint unavailable: %s %s (%s)",
                    subreddit.name,
                    endpoint.name,
                    outcome.detail or outcome.status,
                )
                continue

            items, missing_fields = parse_reddit_listing(
                payload=payload,
                subreddit=subreddit.name,
                category=subreddit.category,
                endpoint_name=endpoint.name,
                time_window_hours=time_window_hours,
            )
            remaining_category_slots = max(
                max_items_per_category - category_totals.get(subreddit.category, 0),
                0,
            )
            remaining_subreddit_slots = max(subreddit.limit - subreddit_collected, 0)
            unique_items: list[dict[str, Any]] = []
            for item in items:
                item_id = item.get("id", "")
                if not item_id or item_id in seen_post_ids:
                    continue
                unique_items.append(item)
                seen_post_ids.add(item_id)
                if len(unique_items) >= min(remaining_category_slots, remaining_subreddit_slots):
                    break

            if missing_fields:
                logger.warning(
                    "Reddit payload incomplete for %s %s: missing=%s",
                    subreddit.name,
                    endpoint.name,
                    ",".join(missing_fields),
                )
            if unique_items:
                health_tracker.record_success(f"r/{subreddit.name}")
            elif items:
                logger.info(
                    "Reddit endpoint returned only duplicate posts for %s %s.",
                    subreddit.name,
                    endpoint.name,
                )
            else:
                subreddit_failures += 1
                health_tracker.record_failure(
                    f"r/{subreddit.name}",
                    "empty_or_outside_window",
                )
            category_totals[subreddit.category] = category_totals.get(subreddit.category, 0) + len(
                unique_items
            )
            subreddit_collected += len(unique_items)
            outcome.items_collected = len(unique_items)
            outcomes.append(outcome)
            collected.extend(unique_items)

            if request_delay_seconds > 0 and requests_made < max_requests_per_run:
                time.sleep(request_delay_seconds)
        if subreddit_failures >= len(enabled_endpoints):
            logger.error("All Reddit endpoints failed for r/%s", subreddit.name)

    logger.info(
        "Reddit fetch completed with %s request(s) and %s item(s). Category totals: %s",
        requests_made,
        len(collected),
        category_totals,
    )
    return collected, outcomes


def run_reddit_validation(
    *,
    app_config: AppConfig,
    sample_subreddits: list[str],
    endpoints: list[RedditEndpointConfig],
    request_delay_seconds: float,
    logger: logging.Logger,
) -> dict[str, Any]:
    checks: list[RedditValidationCheck] = []
    session = requests.Session()
    enabled_endpoints = [endpoint for endpoint in endpoints if endpoint.enabled]

    for subreddit in sample_subreddits:
        for endpoint in enabled_endpoints:
            url = build_reddit_url(subreddit, endpoint)
            full_url = f"{url}?{urlencode(endpoint.params)}" if endpoint.params else url
            payload, outcome = request_reddit_listing(
                app_config=app_config,
                subreddit=subreddit,
                endpoint=endpoint,
                logger=logger,
                session=session,
            )
            if payload is None:
                checks.append(
                    RedditValidationCheck(
                        subreddit=subreddit,
                        endpoint=endpoint.name,
                        url=full_url,
                        status_code=outcome.status_code or _status_from_detail(outcome.detail),
                        content_type=outcome.content_type,
                        json_valid=False,
                        posts_count=0,
                        missing_fields=[],
                        elapsed_ms=outcome.elapsed_ms,
                        diagnosis=outcome.detail or outcome.status,
                    )
                )
                continue

            is_valid, missing_fields, children, diagnosis = validate_listing_payload(payload)
            checks.append(
                RedditValidationCheck(
                    subreddit=subreddit,
                    endpoint=endpoint.name,
                    url=full_url,
                    status_code=outcome.status_code or 200,
                    content_type=outcome.content_type or "application/json",
                    json_valid=is_valid,
                    posts_count=len(children),
                    missing_fields=missing_fields,
                    elapsed_ms=outcome.elapsed_ms,
                    diagnosis=diagnosis,
                )
            )
            if request_delay_seconds > 0:
                time.sleep(request_delay_seconds)

    summary = summarize_validation_checks(checks)
    return {
        "checked_at": datetime.now(tz=UTC).isoformat(),
        "checks": [asdict(check) for check in checks],
        "summary": summary,
        "recommendations": {
            "enable_reddit_by_default": False,
            "enable_reddit_optionally": summary["classification"]
            in {"functional", "functional_but_unstable"},
            "operate_only_rss": summary["classification"] in {"blocked", "not_recommended"},
        },
    }


def summarize_validation_checks(checks: list[RedditValidationCheck]) -> dict[str, Any]:
    total = len(checks)
    json_valid = sum(1 for check in checks if check.json_valid)
    blocked_like = sum(
        1
        for check in checks
        if check.diagnosis.startswith("http_403")
        or check.diagnosis.startswith("http_429")
        or check.diagnosis == "html_response"
    )
    incomplete = sum(1 for check in checks if check.missing_fields)
    avg_elapsed_ms = round(
        sum(check.elapsed_ms or 0.0 for check in checks) / total, 2
    ) if total else 0.0

    if json_valid == 0:
        classification = "blocked" if blocked_like else "not_recommended"
        conclusion = "No endpoint produced a valid Reddit Listing payload."
    elif json_valid == total and incomplete == 0:
        classification = "functional"
        conclusion = (
            "The public Reddit JSON endpoints responded with valid Listing payloads, "
            "but they should still remain optional."
        )
    else:
        classification = "functional_but_unstable"
        conclusion = (
            "Some Reddit JSON endpoints worked, but failures or incomplete payloads confirm instability."
        )

    return {
        "total_checks": total,
        "valid_json_checks": json_valid,
        "blocked_like_checks": blocked_like,
        "incomplete_checks": incomplete,
        "average_elapsed_ms": avg_elapsed_ms,
        "classification": classification,
        "conclusion": conclusion,
    }


def _status_from_detail(detail: str | None) -> int | None:
    if not detail or not detail.startswith("http_"):
        return None
    raw = detail.split("_", maxsplit=1)[1]
    try:
        return int(raw)
    except ValueError:
        return None
