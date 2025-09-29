import logging
import os


def setup_logging(default_level: int = logging.INFO) -> None:
    if logging.getLogger().handlers:
        return
    logging.basicConfig(
        level=default_level,
        format="%(asctime)s %(levelname)s [%(threadName)s] %(name)s: %(message)s",
    )


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(name)


__all__ = ["get_logger", "setup_logging"]


