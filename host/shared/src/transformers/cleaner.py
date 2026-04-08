"""Cleaner - Removes nulls, strips whitespace, normalizes types."""

from typing import Any
from .base_transformer import BaseTransformer


class Cleaner(BaseTransformer):
    """Cleans raw records.

    config keys:
        drop_null_fields  : list of field names that must not be null
        strip_fields      : list of string fields to strip whitespace
        rename            : dict {old_key: new_key}
    """

    def transform(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        drop_null = set(self.config.get("drop_null_fields", []))
        strip_fields = set(self.config.get("strip_fields", []))
        rename = self.config.get("rename", {})

        result = []
        for rec in records:
            # Drop records missing required fields
            if any(rec.get(f) is None for f in drop_null):
                continue

            # Strip whitespace
            for f in strip_fields:
                if isinstance(rec.get(f), str):
                    rec[f] = rec[f].strip()

            # Rename fields
            for old, new in rename.items():
                if old in rec:
                    rec[new] = rec.pop(old)

            result.append(rec)
        return result
