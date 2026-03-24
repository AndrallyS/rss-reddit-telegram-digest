"""Validate public Reddit JSON endpoints before enabling them in production."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import load_app_config, load_sources_config
from app.logger import configure_logging, get_logger
from app.sources.reddit_json_fetcher import run_reddit_validation
from app.utils import save_json


def _print_table(checks: list[dict[str, object]]) -> None:
    headers = [
        "subreddit",
        "endpoint",
        "status",
        "content-type",
        "json válido",
        "posts",
        "campos ausentes",
        "tempo(ms)",
        "diagnóstico",
    ]
    rows = []
    for check in checks:
        rows.append(
            [
                str(check["subreddit"]),
                str(check["endpoint"]),
                str(check.get("status_code") or "-"),
                str(check.get("content_type") or "-"),
                "sim" if check.get("json_valid") else "não",
                str(check.get("posts_count", 0)),
                ",".join(check.get("missing_fields", [])) or "-",
                str(check.get("elapsed_ms") or "-"),
                str(check.get("diagnosis") or "-"),
            ]
        )
    widths = [
        max(len(header), *(len(row[index]) for row in rows)) if rows else len(header)
        for index, header in enumerate(headers)
    ]

    def render(row: list[str]) -> str:
        return " | ".join(value.ljust(widths[index]) for index, value in enumerate(row))

    print(render(headers))
    print("-+-".join("-" * width for width in widths))
    for row in rows:
        print(render(row))


def main() -> int:
    app_config = load_app_config(PROJECT_ROOT)
    configure_logging(app_config.log_dir, app_config.log_level)
    logger = get_logger("scripts.validate_reddit_json")
    sources_config = load_sources_config(PROJECT_ROOT)

    report = run_reddit_validation(
        app_config=app_config,
        sample_subreddits=sources_config.reddit_validation_subreddits,
        endpoints=sources_config.reddit_endpoints,
        request_delay_seconds=sources_config.reddit_request_delay_seconds,
        logger=logger,
    )
    report_path = app_config.output_dir / "reddit_validation_report.json"
    save_json(report_path, report)

    _print_table(report["checks"])
    print()
    print(json.dumps(report["summary"], indent=2, ensure_ascii=False))
    print(json.dumps(report["recommendations"], indent=2, ensure_ascii=False))
    print(f"Relatório salvo em: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
