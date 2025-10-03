"""
Safe, non-blocking logging for COM-AI v3

- Uses QueueHandler + QueueListener so request threads never block on I/O
- Rotates local log file; no network/syslog sinks (Windows-friendly)
- Respects LOG_LEVEL from env (default INFO)
"""

from __future__ import annotations

import atexit
import logging
import logging.handlers
import os
import queue
from typing import Optional

_LOG_QUEUE: Optional[queue.Queue] = None
_LISTENER: Optional[logging.handlers.QueueListener] = None

def _build_formatter() -> logging.Formatter:
    # compact, readable; add asctime first for easier tailing
    return logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

def _build_file_handler(log_dir: str) -> logging.Handler:
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "app.log")

    # 10 MB per file, keep 5 backups
    fh = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    fh.setFormatter(_build_formatter())
    fh.setLevel(logging.DEBUG)  # file gets everything
    return fh

def _build_console_handler() -> logging.Handler:
    ch = logging.StreamHandler()
    ch.setFormatter(_build_formatter())
    # keep console a bit quieter; overridden by LOG_LEVEL if needed
    ch.setLevel(logging.INFO)
    return ch

def setup_logging() -> None:
    """
    Configure root logger with a QueueHandler feeding a QueueListener
    that writes to console + rotating file. Idempotent.
    """
    global _LOG_QUEUE, _LISTENER

    if _LISTENER is not None:
        return  # already configured

    # Respect LOG_LEVEL env, default INFO
    level_str = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_str, logging.INFO)

    # Create the queue and listener targets
    _LOG_QUEUE = queue.Queue(-1)
    file_handler = _build_file_handler(log_dir=os.getenv("LOG_DIR", "logs"))
    console_handler = _build_console_handler()

    # QueueListener writes to the real handlers
    _LISTENER = logging.handlers.QueueListener(_LOG_QUEUE, file_handler, console_handler, respect_handler_level=True)
    _LISTENER.start()
    atexit.register(_stop_listener)

    # Root logger uses a single QueueHandler (non-blocking for producers)
    root = logging.getLogger()
    root.setLevel(level)
    # Remove any pre-existing handlers to avoid duplicates
    for h in list(root.handlers):
        root.removeHandler(h)
    root.addHandler(logging.handlers.QueueHandler(_LOG_QUEUE))

    # Quiet down very chatty third-party loggers if desired
    for noisy in ("uvicorn.error", "uvicorn.access", "watchfiles.main"):
        logging.getLogger(noisy).setLevel(max(level, logging.WARNING))

def _stop_listener() -> None:
    global _LISTENER
    if _LISTENER is not None:
        try:
            _LISTENER.stop()
        except Exception:
            pass
        _LISTENER = None
