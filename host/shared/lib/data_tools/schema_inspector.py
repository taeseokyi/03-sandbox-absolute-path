"""Schema Inspector - Infers field types and null rates from records."""

from typing import Any
from lib.base_tool import BaseTool


class SchemaInspector(BaseTool):
    """Inspect a list of records and infer their schema.

    Returns a dict keyed by field name with:
        type        : most common Python type name
        null_rate   : fraction of records where field is None/missing
        unique      : number of distinct non-null values (capped at 1000)
        sample      : up to 3 example values
    """

    name = "schema_inspector"
    description = "Infer schema and null rates from a list of records"

    def run(self, records: list[dict[str, Any]]) -> dict[str, dict]:
        if not records:
            return {}
        fields: dict[str, list] = {}
        for rec in records:
            for k, v in rec.items():
                fields.setdefault(k, []).append(v)

        schema = {}
        total = len(records)
        for field, values in fields.items():
            non_null = [v for v in values if v is not None]
            null_count = total - len(non_null)
            types = [type(v).__name__ for v in non_null]
            most_common_type = max(set(types), key=types.count) if types else "null"
            unique_vals = set(str(v) for v in non_null)
            schema[field] = {
                "type": most_common_type,
                "null_rate": round(null_count / total, 4),
                "unique": min(len(unique_vals), 1000),
                "sample": non_null[:3],
            }
        return schema
