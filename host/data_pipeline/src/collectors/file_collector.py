"""File Collector - Collects data from local files (CSV, JSON, JSONL)."""

import csv
import json
from pathlib import Path
from typing import Any
from .base_collector import BaseCollector


class FileCollector(BaseCollector):
    """Reads records from a local file.

    config keys:
        path      : file path (str)
        format    : 'csv' | 'json' | 'jsonl'  (default: auto-detect from extension)
        encoding  : file encoding              (default: 'utf-8')
    """

    def connect(self) -> None:
        path = Path(self.config["path"])
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

    def collect(self) -> list[dict[str, Any]]:
        path = Path(self.config["path"])
        fmt = self.config.get("format", path.suffix.lstrip(".").lower())
        encoding = self.config.get("encoding", "utf-8")

        if fmt == "csv":
            return self._read_csv(path, encoding)
        if fmt == "json":
            return self._read_json(path, encoding)
        if fmt == "jsonl":
            return self._read_jsonl(path, encoding)
        raise ValueError(f"Unsupported format: {fmt}")

    def close(self) -> None:
        pass

    def _read_csv(self, path: Path, encoding: str) -> list[dict]:
        with path.open(encoding=encoding, newline="") as f:
            return list(csv.DictReader(f))

    def _read_json(self, path: Path, encoding: str) -> list[dict]:
        with path.open(encoding=encoding) as f:
            data = json.load(f)
        return data if isinstance(data, list) else [data]

    def _read_jsonl(self, path: Path, encoding: str) -> list[dict]:
        records = []
        with path.open(encoding=encoding) as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records
