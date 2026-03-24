"""Telegram delivery with graceful failure."""

from __future__ import annotations

import logging

import requests

from app.models import AppConfig, TelegramSendResult


def send_telegram_messages(
    *,
    app_config: AppConfig,
    messages: list[str],
    logger: logging.Logger,
) -> TelegramSendResult:
    if not app_config.telegram_bot_token or not app_config.telegram_chat_id:
        detail = "Telegram credentials are missing. Preview kept locally."
        logger.warning(detail)
        return TelegramSendResult(sent=False, delivered_messages=0, detail=detail)

    endpoint = f"https://api.telegram.org/bot{app_config.telegram_bot_token}/sendMessage"
    delivered = 0
    for message in messages:
        try:
            response = requests.post(
                endpoint,
                timeout=app_config.request_timeout_seconds,
                data={
                    "chat_id": app_config.telegram_chat_id,
                    "text": message,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": "true",
                },
            )
            response.raise_for_status()
            payload = response.json()
            if not payload.get("ok"):
                raise ValueError(payload)
            delivered += 1
        except Exception as exc:  # noqa: BLE001
            detail = f"Telegram send failed after {delivered} message(s): {exc}"
            logger.error(detail)
            return TelegramSendResult(sent=False, delivered_messages=delivered, detail=detail)
    detail = f"Delivered {delivered} Telegram message(s)."
    logger.info(detail)
    return TelegramSendResult(sent=True, delivered_messages=delivered, detail=detail)
