"""Stream Collector - Collects data from a streaming source (stub)."""

from typing import Any
from .base_collector import BaseCollector


class StreamCollector(BaseCollector):
    """Stub for stream-based collectors (Kafka, WebSocket, etc.).

    config keys:
        topic     : stream topic or channel name
        max_items : max records to collect per run (default: 1000)
    """

    def connect(self) -> None:
        # TODO: initialize stream client (e.g. confluent_kafka.Consumer)
        raise NotImplementedError("StreamCollector.connect() not implemented")

    def collect(self) -> list[dict[str, Any]]:
        # TODO: poll messages up to max_items, deserialize, return
        raise NotImplementedError("StreamCollector.collect() not implemented")

    def close(self) -> None:
        # TODO: close stream client
        pass
