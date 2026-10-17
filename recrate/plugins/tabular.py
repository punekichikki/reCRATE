"""Tabular plugin: numbers, tables and JSON observed-value files.

Owner: Person 3. Standard library only, so the verifier has no heavy dependencies.
"""
import csv
import math
from typing import Any

from .base import Change, Comparison, DataPlugin


def _as_list(v):
    return v if isinstance(v, list) else [v]


def _quantile(sorted_vals, q):
    """Linear-interpolation quantile of an already sorted list (same as numpy's default)."""
    if not sorted_vals:
        raise ValueError("no values")
    pos = (len(sorted_vals) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


def compare_values(observed, expected, comparison: str, tolerance: float = 0.0,
                   decimal_places: int = None, interval: float = 0.95) -> Comparison:
    """Compare one observed value (or list of values) with the expected value(s).

    comparison:
      exact         values identical (lists compared element by element)
      rounded       observed lies inside the rounding interval of the reported value
                    (|obs - exp| <= 0.5 * 10^-dp); accepts either rounding rule at ties
      abs           |obs - exp| <= tolerance
      rel           |obs - exp| <= tolerance * |exp|
      distribution  observed is a list of samples from seeded runs; passes when the
                    reported value lies inside their central `interval` (default 95%)
    "near" means outside tolerance but within twice the tolerance (or, for distribution,
    inside the full min..max range).
    """
    if comparison == "exact":
        ok = observed == expected
        return Comparison(ok, False, "identical" if ok else f"{observed!r} != {expected!r}")

    if comparison == "distribution":
        samples = sorted(float(x) for x in observed)
        e = float(expected)
        a = (1 - interval) / 2
        lo, hi = _quantile(samples, a), _quantile(samples, 1 - a)
        ok = lo <= e <= hi
        near = (not ok) and samples[0] <= e <= samples[-1]
        return Comparison(ok, near, f"reported {e} vs central {interval:.0%} [{lo:.6g}, {hi:.6g}] of {len(samples)} runs")

    obs, exp = _as_list(observed), _as_list(expected)
    if len(obs) != len(exp):
        return Comparison(False, False, f"expected {len(exp)} values, got {len(obs)}")

    if comparison == "rounded":
        if decimal_places is None:
            raise ValueError("rounded comparison needs rc:decimalPlaces")
        bound = 0.5 * 10 ** (-decimal_places)
    elif comparison in ("abs", "rel"):
        bound = float(tolerance)
    else:
        raise ValueError(f"unknown comparison: {comparison}")

    eps = 1e-12
    worst = 0.0
    for o, e in zip(obs, exp):
        o, e = float(o), float(e)
        b = bound * abs(e) if comparison == "rel" else bound
        dev = abs(o - e)
        worst = max(worst, dev / b if b > 0 else (0.0 if dev <= eps else math.inf))
    ok = worst <= 1 + 1e-9
    near = (not ok) and worst <= 2 + 1e-9
    return Comparison(ok, near, f"largest deviation = {worst:.3g} x tolerance")


class TabularPlugin(DataPlugin):
    name = "tabular"
    EXTENSIONS = (".csv", ".tsv", ".json", ".txt")

    def can_handle(self, path: str) -> bool:
        return path.lower().endswith(self.EXTENSIONS)

    # Observed-value files are dicts with an "outputs" mapping.
    def extract(self, data: Any, output_key) -> Any:
        outputs = data["outputs"] if isinstance(data, dict) and "outputs" in data else data
        if isinstance(output_key, list):
            return [outputs[k] for k in output_key]
        return outputs[output_key]

    def has_outputs(self, data: Any, output_key) -> bool:
        outputs = data.get("outputs", {})
        keys = output_key if isinstance(output_key, list) else [output_key]
        return all(k in outputs for k in keys)

    def compare(self, observed: Any, claim: dict) -> Comparison:
        return compare_values(
            observed, claim["rc:expectedValue"], claim["rc:comparison"],
            tolerance=claim.get("rc:toleranceValue", 0.0),
            decimal_places=claim.get("rc:decimalPlaces"),
            interval=claim.get("rc:interval", 0.95),
        )

    # ---------- transfer support ----------
    def load(self, path: str) -> list:
        delim = "\t" if path.lower().endswith(".tsv") else ","
        with open(path, newline="") as f:
            return list(csv.DictReader(f, delimiter=delim))

    def profile(self, rows: list) -> dict:
        cols = list(rows[0].keys()) if rows else []
        prof = {"rows": len(rows), "columns": {}}
        for c in cols:
            vals = [r[c] for r in rows]
            missing = sum(1 for v in vals if v in ("", "NA", "NaN", None))
            nums = []
            for v in vals:
                try:
                    nums.append(float(v))
                except (TypeError, ValueError):
                    pass
            numeric = len(nums) == len(vals) - missing and len(nums) > 0
            prof["columns"][c] = {"type": "numeric" if numeric else "text", "missing": missing,
                                  "min": min(nums) if numeric else None, "max": max(nums) if numeric else None}
        return prof

    def check_compatibility(self, profile: dict, contract: dict) -> list:
        changes = []
        cols = profile["columns"]
        for c in contract.get("rc:requiredColumns", []):
            if c not in cols:
                changes.append(Change("missing-column", c, f"Required column '{c}' is missing; needs a mapping from an existing column"))
        for c, t in contract.get("rc:columnTypes", {}).items():
            if c in cols and cols[c]["type"] != t:
                changes.append(Change("type-conversion", c, f"Column '{c}' is {cols[c]['type']}, contract expects {t}"))
        for c, info in cols.items():
            if info["missing"]:
                changes.append(Change("missing-values", c, f"{info['missing']} missing values in '{c}'"))
        for c, (lo, hi) in contract.get("rc:validatedRange", {}).items():
            if c in cols and cols[c]["min"] is not None and (cols[c]["min"] < lo or cols[c]["max"] > hi):
                changes.append(Change("out-of-range", c, f"'{c}' spans {cols[c]['min']}..{cols[c]['max']}; method validated on {lo}..{hi}"))
        return changes
