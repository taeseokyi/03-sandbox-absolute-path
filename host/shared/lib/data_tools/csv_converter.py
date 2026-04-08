"""CSV Converter - Converts between CSV and list-of-dicts."""

import csv
import io
from pathlib import Path
from typing import Any
from lib.base_tool import BaseTool


class CSVConverter(BaseTool):
    """Read a CSV file into records, or write records out to CSV.

    Usage:
        tool = CSVConverter()
        records = tool.run(src="input.csv")                        # read
        tool.run(src=records, dst="output.csv")                    # write
        csv_str = tool.run(src=records)                            # to string
    """

    name = "csv_converter"
    description = "Convert CSV files to/from list-of-dicts"

    def run(
        self,
        src: str | Path | list[dict[str, Any]],
        dst: str | Path | None = None,
        encoding: str = "utf-8",
    ) -> list[dict[str, Any]] | str:
        if isinstance(src, (str, Path)):
            return self._read(Path(src), encoding)
        return self._write(src, dst, encoding)

    def _read(self, path: Path, encoding: str) -> list[dict[str, Any]]:
        with path.open(encoding=encoding, newline="") as f:
            return list(csv.DictReader(f))

    def _write(
        self,
        records: list[dict[str, Any]],
        dst: str | Path | None,
        encoding: str,
    ) -> str:
        if not records:
            return ""
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=list(records[0].keys()))
        writer.writeheader()
        writer.writerows(records)
        csv_str = buf.getvalue()
        if dst:
            Path(dst).write_text(csv_str, encoding=encoding)
        return csv_str
