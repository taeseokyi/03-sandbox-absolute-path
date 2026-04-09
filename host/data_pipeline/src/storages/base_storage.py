"""Base Storage - All storages must inherit from this class."""

from abc import ABC, abstractmethod
from typing import Any


class BaseStorage(ABC):
    """Common interface for all storage backends."""

    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def connect(self) -> None:
        """Open connection to the storage backend."""

    @abstractmethod
    def save(self, records: list[dict[str, Any]]) -> int:
        """Persist records. Returns the number of records saved."""

    @abstractmethod
    def close(self) -> None:
        """Close the connection."""

    def run(self, records: list[dict[str, Any]]) -> int:
        """Template method: connect → save → close."""
        self.connect()
        try:
            return self.save(records)
        finally:
            self.close()
