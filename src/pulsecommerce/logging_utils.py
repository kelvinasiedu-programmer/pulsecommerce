"""Rich-powered logging helper, shared across the package."""

from __future__ import annotations

import logging

from rich.console import Console
from rich.logging import RichHandler

_console = Console()


def get_logger(name: str = "pulsecommerce", level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(level)
    handler = RichHandler(console=_console, rich_tracebacks=True, show_time=True, show_path=False)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def console() -> Console:
    return _console
