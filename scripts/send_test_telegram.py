"""Send a simple Telegram test message using the current environment variables."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import load_app_config
from app.delivery.telegram_sender import send_telegram_messages
from app.logger import configure_logging, get_logger


def main() -> int:
    app_config = load_app_config(PROJECT_ROOT)
    configure_logging(app_config.log_dir, app_config.log_level)
    logger = get_logger("scripts.send_test_telegram")
    result = send_telegram_messages(
        app_config=app_config,
        messages=[
            "<b>Teste do Digest</b>\nSe voce recebeu esta mensagem, o Telegram do projeto esta configurado corretamente."
        ],
        logger=logger,
    )
    print(result.detail)
    return 0 if result.sent else 1


if __name__ == "__main__":
    raise SystemExit(main())

