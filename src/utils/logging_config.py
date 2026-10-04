import logging
import logging.handlers
import json
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


_thread_local = threading.local()


class ContextFilter(logging.Filter):
    """Injects case_id, file, operation from thread-local storage into log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        ctx = getattr(_thread_local, "log_context", {})
        record.case_id = ctx.get("case_id")
        record.file = ctx.get("file")
        record.operation = ctx.get("operation")
        return True


class JsonFormatter(logging.Formatter):
    """JSON log formatter with forensics-friendly fields."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if record.case_id is not None:
            log_obj["case_id"] = record.case_id
        if record.file:
            log_obj["file"] = record.file
        if record.operation:
            log_obj["operation"] = record.operation

        if hasattr(record, "duration_ms"):
            log_obj["duration_ms"] = record.duration_ms
        if hasattr(record, "context"):
            log_obj["context"] = record.context

        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj, ensure_ascii=False)


def set_log_context(case_id: Optional[int] = None, file: Optional[str] = None, operation: Optional[str] = None) -> None:
    """Sets thread-local log context for the current thread."""
    ctx = getattr(_thread_local, "log_context", {})
    if case_id is not None:
        ctx["case_id"] = case_id
    if file is not None:
        ctx["file"] = file
    if operation is not None:
        ctx["operation"] = operation
    _thread_local.log_context = ctx


def clear_log_context() -> None:
    """Clears thread-local log context."""
    if hasattr(_thread_local, "log_context"):
        del _thread_local.log_context


def _get_log_dir(case_path: Optional[Path]) -> Path:
    if case_path:
        log_dir = Path(case_path) / "logs"
    else:
        log_dir = Path.cwd() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def setup_logging(
    case_path: Optional[Path] = None,
    console_level: int = logging.WARNING,
    file_level: int = logging.DEBUG,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
) -> None:
    """Configures root logger with JSON file handlers and optional console output."""

    log_dir = _get_log_dir(case_path)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.handlers.clear()

    context_filter = ContextFilter()

    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / "app.log",
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(file_level)
    file_handler.setFormatter(JsonFormatter())
    file_handler.addFilter(context_filter)
    root_logger.addHandler(file_handler)

    daily_handler = logging.handlers.TimedRotatingFileHandler(
        log_dir / "app_daily.log",
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
    )
    daily_handler.setLevel(file_level)
    daily_handler.setFormatter(JsonFormatter())
    daily_handler.addFilter(context_filter)
    root_logger.addHandler(daily_handler)

    if console_level <= logging.CRITICAL:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(console_level)
        console_handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%H:%M:%S"
        ))
        console_handler.addFilter(context_filter)
        root_logger.addHandler(console_handler)

    logging.getLogger("PIL").setLevel(logging.WARNING)
    logging.getLogger("pymediainfo").setLevel(logging.WARNING)
    logging.getLogger("exiftool").setLevel(logging.WARNING)

    logging.info("Logging initialized", extra={"operation": "logging_setup", "context": {"log_dir": str(log_dir)}})