"""Logger configuration."""

from __future__ import annotations

import logging
from pathlib import Path

from app.constants import LOG_FILE_NAME
from app.utils import ensure_directory


def configure_logging(log_dir: Path, level: str) -> None:
    ensure_directory(log_dir)
    log_file = log_dir / LOG_FILE_NAME
    root_logger = logging.getLogger()
    root_logger.setLevel(level.upper())
    root_logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)

