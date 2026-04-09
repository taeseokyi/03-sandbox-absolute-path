"""Base Collector - All collectors must inherit from this class."""

from abc import ABC, abstractmethod
from typing import Any

from data_pipeline.lib.pipeline_tools.retry_manager import RetryManager


class BaseCollector(ABC):
    """Common interface for all data collectors.

    config keys:
        retry : dict - optional retry config (max_attempts, backoff, backoff_factor)
                       if omitted, no retry is applied
    """

    def __init__(self, config: dict):
        self.config = config
        retry_cfg = config.get("retry")
        self._retry = RetryManager(retry_cfg) if retry_cfg else None

    @abstractmethod
    def connect(self) -> None:
        """Establish connection to the data source."""

    @abstractmethod
    def collect(self) -> list[dict[str, Any]]:
        """Collect data and return as a list of records."""

    @abstractmethod
    def close(self) -> None:
        """Close the connection."""

    def run(self) -> list[dict[str, Any]]:
        """Template method: connect → (retry) collect → close."""
        self.connect()
        try:
            if self._retry:
                return self._retry.run(self.collect)
            return self.collect()
        finally:
            self.close()
