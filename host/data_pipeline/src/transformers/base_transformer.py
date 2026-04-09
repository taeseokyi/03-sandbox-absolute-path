"""Base Transformer - All transformers must inherit from this class."""

from abc import ABC, abstractmethod
from typing import Any


class BaseTransformer(ABC):
    """Common interface for all data transformers."""

    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def transform(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Transform a list of records and return the result."""

    def run(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return self.transform(records)
