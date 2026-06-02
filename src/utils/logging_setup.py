import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

def setup_logging():
    logdir = Path("logs")
    logdir.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(logdir / "app.log", maxBytes=2_000_000, backupCount=3)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    file_handler.setFormatter(fmt)
    root = logging.getLogger()
    # Use DEBUG during development so worker/presenter debug logs are visible
    root.setLevel(logging.DEBUG)

    # Add file handler if not already present
    if not any(isinstance(h, RotatingFileHandler) and getattr(h, 'baseFilename', None) == str(logdir / "app.log") for h in root.handlers):
        root.addHandler(file_handler)

    # Also log to console for immediate feedback in the terminal
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        console = logging.StreamHandler()
        console.setFormatter(fmt)
        console.setLevel(logging.DEBUG)
        root.addHandler(console)
