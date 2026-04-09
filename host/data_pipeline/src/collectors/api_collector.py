"""API Collector - Collects data from HTTP REST APIs."""

import requests
from typing import Any
from .base_collector import BaseCollector


class APICollector(BaseCollector):
    """Fetches data from a paginated REST API endpoint."""

    def __init__(self, config: dict):
        super().__init__(config)
        # config keys: url, headers, params, page_param, page_size_param, page_size
        self.session: requests.Session | None = None

    def connect(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(self.config.get("headers", {}))

    def collect(self) -> list[dict[str, Any]]:
        url = self.config["url"]
        params = dict(self.config.get("params", {}))
        page_param = self.config.get("page_param", "page")
        page_size_param = self.config.get("page_size_param", "size")
        page_size = self.config.get("page_size", 100)

        records: list[dict[str, Any]] = []
        page = 1
        while True:
            params[page_param] = page
            params[page_size_param] = page_size
            resp = self.session.get(url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            items = data if isinstance(data, list) else data.get("items", [])
            if not items:
                break
            records.extend(items)
            if len(items) < page_size:
                break
            page += 1
        return records

    def close(self) -> None:
        if self.session:
            self.session.close()
            self.session = None
