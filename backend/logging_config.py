"""
Logging configuration — structured JSON-style in production, readable in dev.
"""
import logging
import sys
from backend.config import settings


def _get_formatter() -> logging.Formatter:
    if settings.APP_ENV == "production":
        fmt = '{"time":"%(asctime)s","level":"%(levelname)s","module":"%(name)s","msg":"%(message)s"}'
    else:
        fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    return logging.Formatter(fmt, datefmt="%Y-%m-%dT%H:%M:%S")


def setup_logging() -> None:
    root = logging.getLogger()
    root.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(_get_formatter())
        root.addHandler(handler)


setup_logging()
logger = logging.getLogger("crimenet")
