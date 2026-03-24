from __future__ import annotations

import json
import logging

from app.models import TelegramSendResult
from app.pipeline.runner import run_digest


def test_empty_sources_generate_outputs(app_config, sources_config, ranking_config):
    report = run_digest(
        app_config=app_config,
        sources_config=sources_config,
        ranking_config=ranking_config,
        logger=logging.getLogger("test"),
        rss_fetcher=lambda **kwargs: ([], []),
        reddit_fetcher=lambda **kwargs: ([], []),
        telegram_sender=lambda **kwargs: TelegramSendResult(False, 0, "skipped"),
    )

    assert report["rss_items"] == 0
    assert report["reddit_items"] == 0
    assert (app_config.output_dir / "raw_rss_items.json").exists()
    assert (app_config.output_dir / "raw_reddit_items.json").exists()
    preview = (app_config.output_dir / "telegram_preview.txt").read_text(encoding="utf-8")
    assert "Nenhum item relevante" in preview


def test_empty_sources_ranked_output_is_empty(app_config, sources_config, ranking_config):
    run_digest(
        app_config=app_config,
        sources_config=sources_config,
        ranking_config=ranking_config,
        logger=logging.getLogger("test"),
        rss_fetcher=lambda **kwargs: ([], []),
        reddit_fetcher=lambda **kwargs: ([], []),
        telegram_sender=lambda **kwargs: TelegramSendResult(False, 0, "skipped"),
    )

    ranked = json.loads((app_config.output_dir / "ranked_items.json").read_text(encoding="utf-8"))
    assert ranked == []
