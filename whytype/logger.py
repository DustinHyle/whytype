"""Centralized logging configuration for WhyType."""

import logging
import os
from platformdirs import user_log_dir

APP_NAME = "WhyType"


def setup_logging() -> logging.Logger:
    """Configure file-based logging in the platform-appropriate log directory.

    Returns the root logger for the application.
    """
    log_dir = user_log_dir(APP_NAME)
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "whytype.log")

    handler = logging.FileHandler(log_file, encoding="utf-8")
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
    )

    logger = logging.getLogger("whytype")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        logger.addHandler(handler)
    return logger
