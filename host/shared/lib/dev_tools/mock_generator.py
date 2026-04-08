"""Mock Generator - Generates synthetic records for testing."""

import random
import string
from typing import Any
from lib.base_tool import BaseTool


class MockGenerator(BaseTool):
    """Generate mock records based on a schema definition.

    config keys:
        n      : number of records to generate (default: 10)
        seed   : random seed (default: None)
        schema : dict of {field: {"type": "str"|"int"|"float"|"bool"}}
    """

    name = "mock_generator"
    description = "Generate synthetic records for testing"

    def run(self, schema: dict | None = None) -> list[dict[str, Any]]:
        schema = schema or self.config.get("schema", {})
        n = self.config.get("n", 10)
        seed = self.config.get("seed")
        rng = random.Random(seed)

        records = []
        for _ in range(n):
            rec = {}
            for field, rules in schema.items():
                t = rules.get("type", "str")
                rec[field] = self._gen(t, rng)
            records.append(rec)
        return records

    def _gen(self, t: str, rng: random.Random) -> Any:
        if t == "int":
            return rng.randint(0, 10000)
        if t == "float":
            return round(rng.uniform(0, 1000), 4)
        if t == "bool":
            return rng.choice([True, False])
        # default: random string
        return "".join(rng.choices(string.ascii_lowercase, k=8))
