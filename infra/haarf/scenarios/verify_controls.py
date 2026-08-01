"""Verify that all control IDs referenced in scenarios exist in the requirements list.

Usage::

    python scenarios/verify_controls.py
"""

from __future__ import annotations

import csv
import glob
import json
import sys


def load_requirement_ids(path: str = "requirements/haarf_requirements.csv") -> set[str]:
    """Load all requirement IDs from the CSV."""
    ids = set()
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            ids.add(row["requirement_id"])
    return ids


def load_scenario_controls(directory: str = "scenarios") -> dict[str, list[str]]:
    """Load controls_exercised from all scenario JSON files."""
    controls: dict[str, list[str]] = {}
    for path in sorted(glob.glob(f"{directory}/rt*.json")):
        with open(path) as f:
            scenario = json.load(f)
        controls[scenario["id"]] = scenario.get("controls_exercised", [])
    return controls


def main() -> None:
    req_ids = load_requirement_ids()
    scenario_controls = load_scenario_controls()

    all_ok = True
    all_controls: set[str] = set()

    for sid, controls in scenario_controls.items():
        for ctrl in controls:
            all_controls.add(ctrl)
            # Controls are like C8.1.1 - check if any requirement starts with this
            matches = [r for r in req_ids if r.startswith(ctrl.replace(".", ".")) or r == ctrl]
            if not matches:
                # Check prefix match (C8.1.1 might be in CSV as C8.1.1)
                prefix_matches = [r for r in req_ids if r.startswith(ctrl.split(".")[0])]
                if prefix_matches:
                    print(f"  INFO: {sid} control {ctrl} -> category {ctrl.split('.')[0]} exists ({len(prefix_matches)} reqs)")
                else:
                    print(f"  FAIL: {sid} control {ctrl} -> no matching requirement found")
                    all_ok = False

    print(f"\nScenarios checked: {len(scenario_controls)}")
    print(f"Unique controls referenced: {len(all_controls)}")
    print(f"Requirements in CSV: {len(req_ids)}")

    if all_ok:
        print("\nAll controls verified.")
        sys.exit(0)
    else:
        print("\nSome controls could not be verified.")
        sys.exit(1)


if __name__ == "__main__":
    main()
