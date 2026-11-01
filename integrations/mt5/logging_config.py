import sys
from pathlib import Path

from loguru import logger


def configure_logging(log_path: str = "logs/mt5.log") -> None:
    """Configure console and rotating-file logging for the MT5 integration.

    Args:
        log_path: Destination path for the rotating application log.
    """
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    logger.remove()

    logger.add(sys.stdout, level="INFO", enqueue=True, backtrace=True, diagnose=False)

    try:
        logger.add(
            log_path,
            level="INFO",
            rotation="10 MB",
            retention="14 days",
            compression="zip",
            enqueue=True,
            backtrace=True,
            diagnose=False,
        )
    except PermissionError:
        logger.warning("Cannot write to {log_path}, falling back to stdout-only logging")
