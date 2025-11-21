"""utils/error_handling.py

Centralized error handling and retry helpers used across the application
to improve production robustness and reduce duplicated try/except logic.
"""
from __future__ import annotations

import functools
import logging
import sys
import time
from typing import Callable, Iterable, Tuple, Type

logger = logging.getLogger(__name__)


def retry(max_retries: int = 3, backoff_factor: float = 0.5, exceptions: Tuple[Type[BaseException], ...] = (Exception,)):
    """Decorator to retry a function on specified exceptions with exponential backoff.

    Usage:
        @retry(max_retries=5, backoff_factor=1.0)
        def call():
            ...
    """

    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            attempt = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    attempt += 1
                    if attempt > max_retries:
                        logger.exception("Max retries exceeded for %s", func.__name__)
                        raise
                    sleep_time = backoff_factor * (2 ** (attempt - 1))
                    logger.warning("Retrying %s after exception (attempt %d/%d): %s; sleeping %.2fs",
                                   func.__name__, attempt, max_retries, exc, sleep_time)
                    time.sleep(sleep_time)

        return wrapper

    return decorator


def handle_exceptions(exit_on_exception: bool = False, rethrow: bool = False):
    """Decorator to centrally handle exceptions for top-level functions.

    - Logs full exception information.
    - Optionally exits the process (useful for initialization failures in containers).
    - Optionally re-raises the exception for upstream handling (when used in tests).
    """

    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                logger.exception("Unhandled exception in %s: %s", func.__name__, exc)
                if rethrow:
                    raise
                if exit_on_exception:
                    # Give a clear exit code for orchestration systems
                    logger.error("Exiting due to fatal error in %s", func.__name__)
                    sys.exit(1)
                return None

        return wrapper

    return decorator


def safe_call(func: Callable, *args, default=None, **kwargs):
    """Call a function and return default on any exception after logging."""
    try:
        return func(*args, **kwargs)
    except Exception:
        logger.exception("safe_call caught exception in %s", getattr(func, '__name__', str(func)))
        return default
