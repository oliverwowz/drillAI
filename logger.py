"""DrillAI Logging System.

Provides console and rotating file logging with configurable levels.
Ensures no API keys or sensitive data are logged.
"""

import logging
import re
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


class SensitiveDataFilter(logging.Filter):
    """Filter that redacts sensitive data from log records."""

    PATTERNS = [
        (re.compile(r'(api[_-]?key\s*[=:]\s*)[\w-]+', re.IGNORECASE), r'\1[REDACTED]'),
        (re.compile(r'(AIza[\w-]{35})'), '[REDACTED_API_KEY]'),
        (re.compile(r'(Bearer\s+)[\w.-]+', re.IGNORECASE), r'\1[REDACTED]'),
        (re.compile(r'(token\s*[=:]\s*)[\w.-]+', re.IGNORECASE), r'\1[REDACTED]'),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        """Redact sensitive data from the log message."""
        if isinstance(record.msg, str):
            for pattern, replacement in self.PATTERNS:
                record.msg = pattern.sub(replacement, record.msg)
        if record.args:
            new_args = []
            for arg in (record.args if isinstance(record.args, tuple) else (record.args,)):
                if isinstance(arg, str):
                    for pattern, replacement in self.PATTERNS:
                        arg = pattern.sub(replacement, arg)
                new_args.append(arg)
            record.args = tuple(new_args) if isinstance(record.args, tuple) else new_args[0]
        return True


def setup_logging(
    log_level: str = "INFO",
    log_dir: Optional[Path] = None,
    debug: bool = False,
) -> logging.Logger:
    """Set up application logging with console and file handlers.

    Args:
        log_level: Logging level string (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_dir: Directory for log files. If None, file logging is disabled.
        debug: If True, forces DEBUG level and includes stack traces.

    Returns:
        Configured root logger for DrillAI.
    """
    logger = logging.getLogger("drillai")

    # Prevent duplicate handlers on repeated calls
    if logger.handlers:
        logger.handlers.clear()

    effective_level = logging.DEBUG if debug else getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(effective_level)

    # Console handler
    console_fmt = logging.Formatter(
        fmt="[%(levelname)-7s] %(message)s",
        datefmt="%H:%M:%S",
    )
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(effective_level)
    console_handler.setFormatter(console_fmt)
    console_handler.addFilter(SensitiveDataFilter())
    logger.addHandler(console_handler)

    # File handler
    if log_dir is not None:
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / "drillai.log"
            file_fmt = logging.Formatter(
                fmt="%(asctime)s [%(levelname)-7s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            file_handler = RotatingFileHandler(
                str(log_file),
                maxBytes=5 * 1024 * 1024,  # 5 MB
                backupCount=3,
                encoding="utf-8",
            )
            file_handler.setLevel(logging.DEBUG)  # File always captures DEBUG
            file_handler.setFormatter(file_fmt)
            file_handler.addFilter(SensitiveDataFilter())
            logger.addHandler(file_handler)
        except OSError as e:
            logger.warning(f"Could not set up file logging: {e}")

    return logger


def get_logger(name: str = "drillai") -> logging.Logger:
    """Get a named logger under the drillai namespace.

    Args:
        name: Logger name. Will be prefixed with 'drillai.' if not already.

    Returns:
        Logger instance.
    """
    if not name.startswith("drillai"):
        name = f"drillai.{name}"
    return logging.getLogger(name)
