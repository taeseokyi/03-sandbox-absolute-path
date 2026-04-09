"""Data Sampler - Draws random or stratified samples from records."""

import random
from typing import Any
from ..base_tool import BaseTool


class DataSampler(BaseTool):
    """Sample records from a large list.

    config keys:
        n      : number of records to sample
        seed   : random seed for reproducibility (default: None)
        strata : field name for stratified sampling (optional)
    """

    name = "data_sampler"
    description = "Draw random or stratified samples from records"

    def run(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        n = self.config.get("n", 100)
        seed = self.config.get("seed")
        strata = self.config.get("strata")

        rng = random.Random(seed)

        if not strata:
            return rng.sample(records, min(n, len(records)))

        # Stratified: proportional sample per stratum
        groups: dict[Any, list] = {}
        for rec in records:
            key = rec.get(strata)
            groups.setdefault(key, []).append(rec)

        result = []
        for grp in groups.values():
            k = max(1, round(n * len(grp) / len(records)))
            result.extend(rng.sample(grp, min(k, len(grp))))
        return result[:n]
