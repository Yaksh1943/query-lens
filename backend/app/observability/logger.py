"""
Structured logging.

Phase 1 scope: emit structured (JSON-friendly) log records for each
pipeline stage. This is deliberately NOT a metrics/dashboard system —
that is Phase 4 (analytics), built on top of data captured here once
there is real pipeline activity to show.
"""
import logging
import sys


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            fmt='{"time":"%(asctime)s","level":"%(levelname)s",'
                '"logger":"%(name)s","message":"%(message)s"}'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger
