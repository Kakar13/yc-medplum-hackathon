"""Compute regulatory framework coverage from the mapping coding sheet.

Reproduces the coverage percentages reported in the manuscript (Table 1):
    FDA Digital Health:  84%
    EU AI Act:           71%
    Health Canada SGBA+: 67%
    UK MHRA AI Airlock:  60%
    NIST AI RMF:         88%
    OWASP AISVS:         56%
    WHO GI-AI4H:         48%
    ISO/IEC 42001:       71%
    IMDRF GMLP:          72%

Usage::

    python mapping/compute_coverage.py
    python mapping/compute_coverage.py --sheet mapping/coding_sheet.csv
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from collections import defaultdict


FRAMEWORKS = [
    "FDA",
    "EU_AI_Act",
    "Health_Canada",
    "UK_MHRA",
    "NIST_AI_RMF",
    "OWASP_AISVS",
    "WHO_GI_AI4H",
    "ISO_42001",
    "IMDRF_GMLP",
]

DISPLAY_NAMES = {
    "FDA": "FDA Digital Health",
    "EU_AI_Act": "EU AI Act",
    "Health_Canada": "Health Canada SGBA+",
    "UK_MHRA": "UK MHRA AI Airlock",
    "NIST_AI_RMF": "NIST AI RMF",
    "OWASP_AISVS": "OWASP AISVS",
    "WHO_GI_AI4H": "WHO GI-AI4H",
    "ISO_42001": "ISO/IEC 42001",
    "IMDRF_GMLP": "IMDRF GMLP",
}


def compute_coverage(sheet_path: str) -> dict[str, dict]:
    """Parse the coding sheet and compute coverage per framework.

    Returns a dict keyed by framework code with:
        em, pm, nm, total, coverage_pct
    """
    results: dict[str, dict[str, int]] = {
        fw: {"EM": 0, "PM": 0, "NM": 0, "total": 0} for fw in FRAMEWORKS
    }

    with open(sheet_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            fw = row["source_framework"]
            match = row["match_type"]
            if fw in results and match in ("EM", "PM", "NM"):
                results[fw][match] += 1
                results[fw]["total"] += 1

    output = {}
    for fw in FRAMEWORKS:
        r = results[fw]
        covered = r["EM"] + r["PM"]
        total = r["total"]
        pct = round(100 * covered / total) if total > 0 else 0
        output[fw] = {
            "display_name": DISPLAY_NAMES[fw],
            "EM": r["EM"],
            "PM": r["PM"],
            "NM": r["NM"],
            "total": total,
            "covered": covered,
            "coverage_pct": pct,
        }

    return output


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compute HAARF regulatory framework coverage percentages."
    )
    parser.add_argument(
        "--sheet",
        default="mapping/coding_sheet.csv",
        help="Path to the coding sheet CSV (default: mapping/coding_sheet.csv)",
    )
    args = parser.parse_args()

    if not os.path.exists(args.sheet):
        print(f"Error: {args.sheet} not found", file=sys.stderr)
        sys.exit(1)

    results = compute_coverage(args.sheet)

    print(f"{'Framework':<25} {'EM':>4} {'PM':>4} {'NM':>4} {'Total':>6} {'Coverage':>9}")
    print("-" * 60)
    for fw in FRAMEWORKS:
        r = results[fw]
        print(
            f"{r['display_name']:<25} {r['EM']:>4} {r['PM']:>4} {r['NM']:>4} "
            f"{r['total']:>6} {r['coverage_pct']:>8}%"
        )


if __name__ == "__main__":
    main()
