"""Schema Generator - Auto-generates a validator schema from sample records."""

from typing import Any
from ..base_tool import BaseTool
from ..data_tools.schema_inspector import SchemaInspector


class SchemaGenerator(BaseTool):
    """Generate a SchemaValidator-compatible schema dict from sample records.

    The generated schema marks a field as required if its null_rate == 0.

    Usage:
        gen = SchemaGenerator()
        schema = gen.run(records)
    """

    name = "schema_generator"
    description = "Auto-generate a validator schema from sample records"

    _TYPE_MAP = {
        "str": str,
        "int": int,
        "float": float,
        "bool": bool,
        "list": list,
        "dict": dict,
    }

    def run(self, records: list[dict[str, Any]]) -> dict:
        inspector = SchemaInspector()
        field_info = inspector.run(records)

        schema = {}
        for field, info in field_info.items():
            type_cls = self._TYPE_MAP.get(info["type"])
            schema[field] = {
                "type": type_cls,
                "required": info["null_rate"] == 0.0,
            }
        return schema
