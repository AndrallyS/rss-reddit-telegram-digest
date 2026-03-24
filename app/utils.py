"""Utility helpers for serialization, text cleanup and HTTP calls."""

from __future__ import annotations

import json
import logging
import math
import re
import time
from collections.abc import Iterable
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import requests

from app.constants import TRANSIENT_HTTP_STATUSES


def utcnow() -> datetime:
    return datetime.now(tz=UTC)


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def serialize_data(data: Any) -> Any:
    if is_dataclass(data):
        return serialize_data(asdict(data))
    if isinstance(data, datetime):
        return data.astimezone(UTC).isoformat()
    if isinstance(data, Path):
        return str(data)
    if isinstance(data, dict):
        return {str(key): serialize_data(value) for key, value in data.items()}
    if isinstance(data, list):
        return [serialize_data(item) for item in data]
    return data


def save_json(path: Path, data: Any) -> None:
    ensure_directory(path.parent)
    path.write_text(
        json.dumps(serialize_data(data), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def load_json(path: Path) -> dict[str, Any] | list[Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def truncate_text(value: str, max_length: int) -> str:
    cleaned = clean_text(value)
    if len(cleaned) <= max_length:
        return cleaned
    return cleaned[: max_length - 1].rstrip() + "…"


def normalize_title(value: str) -> str:
    cleaned = clean_text(value).lower()
    cleaned = re.sub(r"[^a-z0-9\s]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def canonicalize_url(url: str | None) -> str:
    if not url:
        return ""
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower() or "https"
    netloc = parts.netloc.lower()
    path = re.sub(r"/+$", "", parts.path) or "/"
    return urlunsplit((scheme, netloc, path, "", ""))


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=UTC)
    if isinstance(value, str):
        candidate = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            return None
        return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return None


def age_in_hours(published_at: datetime, now: datetime | None = None) -> float:
    reference = now or utcnow()
    delta = reference - published_at.astimezone(UTC)
    return max(delta.total_seconds() / 3600, 0.0)


def log1p_scaled(value: int | float) -> float:
    return math.log1p(max(float(value), 0.0))


def split_messages(parts: Iterable[str], max_length: int) -> list[str]:
    messages: list[str] = []
    current = ""
    for part in parts:
        if not part.strip():
            continue
        if len(current) + len(part) + 2 <= max_length:
            current = f"{current}\n\n{part}".strip()
            continue
        if current:
            messages.append(current)
        if len(part) <= max_length:
            current = part
            continue
        start = 0
        while start < len(part):
            chunk = part[start : start + max_length]
            messages.append(chunk)
            start += max_length
        current = ""
    if current:
        messages.append(current)
    return messages


def request_with_retry(
    *,
    session: requests.Session,
    url: str,
    headers: dict[str, str],
    timeout: float,
    max_retries: int,
    backoff_base_seconds: float,
    logger: logging.Logger,
    params: dict[str, Any] | None = None,
) -> tuple[requests.Response, float]:
    attempt = 0
    last_error: Exception | None = None
    while attempt <= max_retries:
        started = time.perf_counter()
        try:
            response = session.get(url, headers=headers, timeout=timeout, params=params)
            elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
            if response.status_code in TRANSIENT_HTTP_STATUSES and attempt < max_retries:
                sleep_seconds = backoff_base_seconds * (2**attempt)
                logger.warning(
                    "Transient HTTP status for %s: %s. Retrying in %.2fs",
                    url,
                    response.status_code,
                    sleep_seconds,
                )
                time.sleep(sleep_seconds)
                attempt += 1
                continue
            return response, elapsed_ms
        except requests.Timeout as exc:
            last_error = exc
            if attempt >= max_retries:
                raise
            sleep_seconds = backoff_base_seconds * (2**attempt)
            logger.warning("Timeout on %s. Retrying in %.2fs", url, sleep_seconds)
            time.sleep(sleep_seconds)
            attempt += 1
        except requests.RequestException as exc:
            last_error = exc
            if attempt >= max_retries:
                raise
            sleep_seconds = backoff_base_seconds * (2**attempt)
            logger.warning("Network error on %s. Retrying in %.2fs", url, sleep_seconds)
            time.sleep(sleep_seconds)
            attempt += 1
    if last_error:
        raise last_error
    raise RuntimeError(f"Request failed without response: {url}")

