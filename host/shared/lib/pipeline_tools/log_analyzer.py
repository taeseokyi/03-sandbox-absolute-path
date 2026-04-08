"""Log Analyzer - Parses JSON pipeline logs and surfaces errors/stats."""

import json
from pathlib import Path
from typing import Any
from lib.base_tool import BaseTool


class LogAnalyzer(BaseTool):
    """Parse a JSON-lines log file produced by PipelineMonitor.

    Usage:
        tool = LogAnalyzer()
        report = tool.run("pipeline.log")
    """

    name = "log_analyzer"
    description = "Parse pipeline JSON log and surface errors and stage stats"

    def run(self, log_path: str | Path) -> dict[str, Any]:
        path = Path(log_path)
        lines = path.read_text(encoding="utf-8").splitlines()

        entries = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                pass

        errors = [e for e in entries if e.get("level") in ("ERROR", "CRITICAL")]
        warnings = [e for e in entries if e.get("level") == "WARNING"]
        stage_stats = {}
        for e in entries:
            msg = e.get("msg", "")
            if isinstance(msg, str):
                try:
                    data = json.loads(msg)
                    if "stage" in data:
                        stage_stats[data["stage"]] = data
                except (json.JSONDecodeError, TypeError):
                    pass

        return {
            "total_lines": len(entries),
            "error_count": len(errors),
            "warning_count": len(warnings),
            "errors": errors,
            "stage_stats": stage_stats,
        }
