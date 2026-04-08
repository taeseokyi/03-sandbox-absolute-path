"""Retry Manager - Wraps a callable with configurable retry logic."""

import time
import logging
from typing import Any, Callable
from ..base_tool import BaseTool

log = logging.getLogger(__name__)


class RetryManager(BaseTool):
    """Retry a callable on failure with exponential backoff.

    config keys:
        max_attempts  : total attempts including first (default: 3)
        backoff       : initial wait in seconds (default: 2)
        backoff_factor: multiplier per retry (default: 2)
        exceptions    : tuple of exception types to catch (default: Exception)
    """

    name = "retry_manager"
    description = "Retry a callable with exponential backoff on failure"

    def run(self, fn: Callable, *args: Any, **kwargs: Any) -> Any:
        max_attempts = self.config.get("max_attempts", 3)
        backoff = self.config.get("backoff", 2)
        factor = self.config.get("backoff_factor", 2)
        exceptions = tuple(self.config.get("exceptions", [Exception]))

        wait = backoff
        for attempt in range(1, max_attempts + 1):
            try:
                return fn(*args, **kwargs)
            except exceptions as exc:
                if attempt == max_attempts:
                    raise
                log.warning(
                    "Attempt %d/%d failed (%s). Retrying in %.1fs...",
                    attempt, max_attempts, exc, wait,
                )
                time.sleep(wait)
                wait *= factor
