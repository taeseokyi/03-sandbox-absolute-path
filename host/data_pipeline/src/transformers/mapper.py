"""Mapper - Maps raw fields to target schema using a field map."""

from typing import Any, Callable
from .base_transformer import BaseTransformer


class Mapper(BaseTransformer):
    """Remaps record fields to a target schema.

    config keys:
        field_map     : dict {source_field: target_field}
        keep_extra    : bool - keep fields not in field_map (default: False)
        coercions     : dict {target_field: callable} - type coercions to apply
    """

    def transform(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        field_map: dict[str, str] = self.config.get("field_map", {})
        keep_extra: bool = self.config.get("keep_extra", False)
        coercions: dict[str, Callable] = self.config.get("coercions", {})

        result = []
        for rec in records:
            mapped: dict[str, Any] = {}
            for src, tgt in field_map.items():
                if src in rec:
                    mapped[tgt] = rec[src]
            if keep_extra:
                for k, v in rec.items():
                    if k not in field_map:
                        mapped[k] = v
            for field, fn in coercions.items():
                if field in mapped and mapped[field] is not None:
                    mapped[field] = fn(mapped[field])
            result.append(mapped)
        return result
