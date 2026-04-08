"""Base Tool - All tools must inherit from this class."""

from abc import ABC, abstractmethod
from typing import Any


class BaseTool(ABC):
    """Common interface for all pipeline tools."""

    name: str = ""
    description: str = ""

    def __init__(self, config: dict | None = None):
        self.config = config or {}

    @abstractmethod
    def run(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the tool."""

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r})"
