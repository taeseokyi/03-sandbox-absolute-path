"""Pipeline Checker - Verifies each stage output meets minimum expectations."""

from typing import Any
from lib.base_tool import BaseTool


class PipelineChecker(BaseTool):
    """Run a set of checks on stage output and return a report.

    config keys:
        min_records   : minimum number of records expected (default: 1)
        required_fields: list of fields that must be present in every record
    """

    name = "pipeline_checker"
    description = "Verify stage output meets minimum quality expectations"

    def run(self, records: list[dict[str, Any]], stage: str = "unknown") -> dict:
        min_records = self.config.get("min_records", 1)
        required_fields = self.config.get("required_fields", [])

        report = {"stage": stage, "record_count": len(records), "errors": []}

        if len(records) < min_records:
            report["errors"].append(
                f"Expected at least {min_records} records, got {len(records)}"
            )

        for field in required_fields:
            missing = sum(1 for r in records if field not in r or r[field] is None)
            if missing:
                report["errors"].append(
                    f"Field '{field}' missing or null in {missing}/{len(records)} records"
                )

        report["passed"] = len(report["errors"]) == 0
        return report
