"""Schema Validator - Validates records against a field schema."""

from __future__ import annotations
from typing import Any


class ValidationError(Exception):
    pass


_TYPE_MAP = {
    "str": str, "int": int, "float": float,
    "bool": bool, "list": list, "dict": dict,
}


class SchemaValidator:
    """Validates a list of records against a declared schema.

    schema format:
        {
            "field_name": {
                "type"    : str | int | float | bool | list | dict,
                "required": True | False,
                "choices" : [allowed, values]   # optional
            },
            ...
        }
    """

    def __init__(self, schema: dict):
        self.schema = schema

    @classmethod
    def from_sample(cls, records: list[dict[str, Any]]) -> SchemaValidator:
        """샘플 레코드에서 스키마를 자동 추론하여 SchemaValidator를 생성합니다.

        lib.data_tools.SchemaInspector를 활용하여 필드 타입과 null 비율을 분석하고
        null_rate == 0인 필드를 required로 설정합니다.
        """
        from lib.data_tools.schema_inspector import SchemaInspector
        field_info = SchemaInspector().run(records)
        schema = {
            field: {
                "type": _TYPE_MAP.get(info["type"]),
                "required": info["null_rate"] == 0.0,
            }
            for field, info in field_info.items()
        }
        return cls(schema)

    def validate(self, records: list[dict[str, Any]]) -> list[str]:
        """Returns a list of error messages. Empty list = valid."""
        errors: list[str] = []
        for idx, rec in enumerate(records):
            for field, rules in self.schema.items():
                required = rules.get("required", False)
                expected_type = rules.get("type")
                choices = rules.get("choices")
                value = rec.get(field)

                if value is None:
                    if required:
                        errors.append(f"[{idx}] '{field}' is required but missing")
                    continue

                if expected_type and not isinstance(value, expected_type):
                    errors.append(
                        f"[{idx}] '{field}' expected {expected_type.__name__}, "
                        f"got {type(value).__name__}"
                    )

                if choices and value not in choices:
                    errors.append(
                        f"[{idx}] '{field}' value {value!r} not in allowed choices"
                    )
        return errors

    def check_collection(self, records: list[dict[str, Any]]) -> bool:
        errors = self.validate(records)
        if errors:
            raise ValidationError("\n".join(errors))
        return True
