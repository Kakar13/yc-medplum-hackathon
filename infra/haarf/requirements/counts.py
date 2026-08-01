#!/usr/bin/env python3
"""Validate HAARF requirements CSV against manuscript narrative.

Reads haarf_requirements.csv and prints category totals, implementation
level totals, and subcategory breakdowns. Expected counts:
  - 279 total requirements across 8 categories (C1-C8)
  - 3 implementation levels: L1=85, L2=144, L3=50
"""

from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path

EXPECTED_CATEGORY_COUNTS = {
    "C1": 30,
    "C2": 34,
    "C3": 35,
    "C4": 38,
    "C5": 30,
    "C6": 35,
    "C7": 35,
    "C8": 42,
}

EXPECTED_LEVEL_COUNTS = {
    "L1": 85,
    "L2": 144,
    "L3": 50,
}

# Map full-text level names to short codes for normalization
LEVEL_ALIASES = {
    "Foundation": "L1",
    "Advanced": "L2",
    "Expert": "L3",
    "L1": "L1",
    "L2": "L2",
    "L3": "L3",
}

EXPECTED_TOTAL = 279

CATEGORY_NAMES = {
    "C1": "Unified Risk & Lifecycle Assessment",
    "C2": "AI Model Passport & Traceability",
    "C3": "Proactive Cybersecurity Framework",
    "C4": "Human Oversight & Integration",
    "C5": "Agent Registration & Identity Management",
    "C6": "Autonomy Governance & Control",
    "C7": "Bias Mitigation & Population Equity",
    "C8": "Tool Use & Integration Security",
}


def load_requirements(csv_path: Path) -> list[dict]:
    """Load requirements from CSV file."""
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def validate_and_report(requirements: list[dict]) -> bool:
    """Print counts and validate against expected values. Returns True if valid."""
    all_ok = True

    # --- Total count ---
    total = len(requirements)
    status = "OK" if total == EXPECTED_TOTAL else "MISMATCH"
    if status == "MISMATCH":
        all_ok = False
    print(f"Total requirements: {total}  (expected {EXPECTED_TOTAL}) [{status}]")
    print()

    # --- Category counts ---
    cat_counter: Counter[str] = Counter()
    for req in requirements:
        cat_counter[req["category"]] += 1

    print("Category Totals")
    print("-" * 65)
    print(f"  {'Category':<6} {'Name':<42} {'Count':>5} {'Expected':>8} {'Status'}")
    print("-" * 65)
    for cat in sorted(EXPECTED_CATEGORY_COUNTS):
        actual = cat_counter.get(cat, 0)
        expected = EXPECTED_CATEGORY_COUNTS[cat]
        ok = "OK" if actual == expected else "MISMATCH"
        if ok == "MISMATCH":
            all_ok = False
        name = CATEGORY_NAMES.get(cat, "")
        print(f"  {cat:<6} {name:<42} {actual:>5} {expected:>8}  {ok}")
    cat_total = sum(cat_counter.values())
    print("-" * 65)
    print(f"  {'TOTAL':<6} {'':<42} {cat_total:>5} {EXPECTED_TOTAL:>8}")
    print()

    # --- Implementation level counts ---
    # Normalize level values to short codes (L1/L2/L3)
    level_counter: Counter[str] = Counter()
    for req in requirements:
        raw_level = req["implementation_level"]
        normalized = LEVEL_ALIASES.get(raw_level, raw_level)
        level_counter[normalized] += 1

    print("Implementation Level Totals")
    print("-" * 50)
    print(f"  {'Level':<12} {'Description':<16} {'Count':>5} {'Expected':>8} {'Status'}")
    print("-" * 50)
    level_names = {"L1": "Foundation", "L2": "Advanced", "L3": "Expert"}
    for level in sorted(EXPECTED_LEVEL_COUNTS):
        actual = level_counter.get(level, 0)
        expected = EXPECTED_LEVEL_COUNTS[level]
        ok = "OK" if actual == expected else "MISMATCH"
        if ok == "MISMATCH":
            all_ok = False
        desc = level_names.get(level, "")
        print(f"  {level:<12} {desc:<16} {actual:>5} {expected:>8}  {ok}")
    lvl_total = sum(level_counter.values())
    print("-" * 50)
    print(f"  {'TOTAL':<12} {'':<16} {lvl_total:>5} {EXPECTED_TOTAL:>8}")
    print()

    # --- Risk level distribution ---
    risk_counter: Counter[str] = Counter()
    for req in requirements:
        risk_counter[req["risk_level"]] += 1

    print("Risk Level Distribution")
    print("-" * 30)
    for risk in sorted(risk_counter, key=lambda r: {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}.get(r, 9)):
        print(f"  {risk:<12} {risk_counter[risk]:>5}")
    print("-" * 30)
    print(f"  {'TOTAL':<12} {sum(risk_counter.values()):>5}")
    print()

    # --- Subcategory breakdown ---
    subcat_counter: Counter[str] = Counter()
    for req in requirements:
        rid = req["requirement_id"]
        # Extract subcategory: e.g. C8.1.5 -> C8.1
        parts = rid.split(".")
        if len(parts) >= 2:
            subcat = f"{parts[0]}.{parts[1]}"
            subcat_counter[subcat] += 1

    print("Subcategory Breakdown")
    print("-" * 40)
    current_cat = ""
    for subcat in sorted(subcat_counter, key=lambda s: (s.split(".")[0], int(s.split(".")[1]))):
        cat = subcat.split(".")[0]
        if cat != current_cat:
            if current_cat:
                print()
            current_cat = cat
            print(f"  {cat} - {CATEGORY_NAMES.get(cat, '')}:")
        print(f"    {subcat}: {subcat_counter[subcat]} requirements")
    print()

    # --- Final verdict ---
    if all_ok:
        print("VALIDATION: All counts match manuscript narrative.")
    else:
        print("VALIDATION FAILED: One or more counts do not match expected values.")

    return all_ok


def main() -> int:
    csv_path = Path(__file__).parent / "haarf_requirements.csv"
    if not csv_path.exists():
        print(f"ERROR: {csv_path} not found", file=sys.stderr)
        return 1

    requirements = load_requirements(csv_path)
    ok = validate_and_report(requirements)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
