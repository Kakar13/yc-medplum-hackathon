"""Dental charting: tooth localization from plain speech, and a periodontal chart.

Universal Numbering System (1-32), the US convention: 1 is the upper right third molar, numbering
runs left across the maxilla to 16, drops to 17 at the lower left third molar, and runs back to 32
at the lower right third molar.

Probing depth thresholds follow standard periodontal assessment: 1-3mm healthy, 4-5mm indicates
attachment loss, 6mm and above is advanced disease. Bleeding on probing is the inflammation marker.
"""

from __future__ import annotations

import re
from typing import Any

# name, quadrant, universal number
_TEETH: list[tuple[int, str, str]] = [
    (1, "third molar", "UR"), (2, "second molar", "UR"), (3, "first molar", "UR"),
    (4, "second premolar", "UR"), (5, "first premolar", "UR"), (6, "canine", "UR"),
    (7, "lateral incisor", "UR"), (8, "central incisor", "UR"),
    (9, "central incisor", "UL"), (10, "lateral incisor", "UL"), (11, "canine", "UL"),
    (12, "first premolar", "UL"), (13, "second premolar", "UL"), (14, "first molar", "UL"),
    (15, "second molar", "UL"), (16, "third molar", "UL"),
    (17, "third molar", "LL"), (18, "second molar", "LL"), (19, "first molar", "LL"),
    (20, "second premolar", "LL"), (21, "first premolar", "LL"), (22, "canine", "LL"),
    (23, "lateral incisor", "LL"), (24, "central incisor", "LL"),
    (25, "central incisor", "LR"), (26, "lateral incisor", "LR"), (27, "canine", "LR"),
    (28, "first premolar", "LR"), (29, "second premolar", "LR"), (30, "first molar", "LR"),
    (31, "second molar", "LR"), (32, "third molar", "LR"),
]

QUADRANT_NAMES = {
    "UR": "upper right",
    "UL": "upper left",
    "LL": "lower left",
    "LR": "lower right",
}

TOOTH_BY_NUMBER = {n: {"number": n, "name": name, "quadrant": q} for n, name, q in _TEETH}

# Third molars extracted in 2015 — the common case, and it changes what "the last one" means.
# You cannot chart a tooth the patient does not have.
MISSING = {1, 16, 17, 32}
PRESENT = [n for n, _, _ in _TEETH if n not in MISSING]


def _back_to_front(quadrant: str) -> list[int]:
    """The teeth this patient has in that quadrant, ordered the way they'd count them."""
    nums = [n for n, _, q in _TEETH if q == quadrant and n in PRESENT]
    # Universal numbering starts at the back in UR and LL, and ends at the back in UL and LR.
    return sorted(nums, reverse=quadrant in ("UL", "LR"))


def _ordinal_from_back(text: str) -> int | None:
    if any(
        w in text
        for w in ("last one but one", "second to last", "next to last", "second from the back",
                  "second from back", "one before the last", "second last")
    ):
        return 2
    if any(w in text for w in ("third from the back", "third from back", "third to last")):
        return 3
    if any(
        w in text
        for w in ("very last", "last one", "right at the back", "furthest back", "all the way back")
    ):
        return 1
    return None


def tooth_label(number: int) -> str:
    t = TOOTH_BY_NUMBER.get(number)
    if not t:
        return f"tooth {number}"
    return f"{QUADRANT_NAMES[t['quadrant']]} {t['name']} (tooth {number})"


def locate_tooth(description: str) -> dict[str, Any]:
    """Narrow plain speech down to candidate teeth.

    Patients say "the back one on the bottom right", not "tooth 30". Arch and side are the two
    facts they can always give reliably, and those alone cut 32 teeth to 8; position words narrow
    it further. Anything still ambiguous is returned as candidates rather than guessed at, because
    charting the wrong tooth is a clinical error, not a rounding error.
    """
    text = description.lower()

    upper = any(w in text for w in ("upper", "top", "maxilla"))
    lower = any(w in text for w in ("lower", "bottom", "mandib", "jaw"))
    right = "right" in text
    left = "left" in text

    arches = ["U"] if upper and not lower else ["L"] if lower and not upper else ["U", "L"]
    sides = ["R"] if right and not left else ["L"] if left and not right else ["R", "L"]
    quadrants = [a + s for a in arches for s in sides]

    if any(w in text for w in ("wisdom", "very back", "furthest back", "all the way back")):
        wanted = ["third molar"]
    elif any(w in text for w in ("back", "molar", "chew", "grind")):
        wanted = ["first molar", "second molar", "third molar"]
    elif any(w in text for w in ("front", "incisor", "bite")):
        wanted = ["central incisor", "lateral incisor"]
    elif any(w in text for w in ("eye tooth", "canine", "fang", "pointy")):
        wanted = ["canine"]
    elif any(w in text for w in ("premolar", "bicuspid")):
        wanted = ["first premolar", "second premolar"]
    else:
        wanted = []

    explicit = re.search(r"\b(?:tooth|number)\s*#?\s*(\d{1,2})\b", text)
    if explicit and 1 <= int(explicit.group(1)) <= 32:
        n = int(explicit.group(1))
        return {
            "resolved": True,
            "tooth": TOOTH_BY_NUMBER[n],
            "label": tooth_label(n),
            "candidates": [n],
            "question": "",
        }

    candidates = [
        n
        for n, name, q in _TEETH
        if q in quadrants and n in PRESENT and (not wanted or name in wanted)
    ]

    # Patients count from the back, because that is the end they can reach with their tongue.
    # "The last one but one" is a real answer to "which one", and discarding it forces another
    # round of questions about a tooth that is currently throbbing. Counting runs over the teeth
    # this patient actually has: with the wisdom teeth out, their last tooth is the second molar.
    ordinal = _ordinal_from_back(text)
    if ordinal and len(quadrants) == 1:
        ordered = _back_to_front(quadrants[0])
        if ordinal <= len(ordered):
            n = ordered[ordinal - 1]
            return {
                "resolved": True,
                "tooth": TOOTH_BY_NUMBER[n],
                "label": tooth_label(n),
                "candidates": [n],
                "question": "",
            }

    if len(candidates) == 1:
        n = candidates[0]
        return {
            "resolved": True,
            "tooth": TOOTH_BY_NUMBER[n],
            "label": tooth_label(n),
            "candidates": candidates,
            "question": "",
        }

    # Ask for the one fact that halves the search, rather than a generic "can you be specific".
    if len(quadrants) > 1:
        question = (
            "Is it upper or lower, and on the left or the right?"
            if len(arches) > 1 and len(sides) > 1
            else "Which side is it on, left or right?"
            if len(sides) > 1
            else "Is that upper or lower?"
        )
    elif not wanted:
        question = "Is it one of the back teeth you chew with, or nearer the front?"
    elif "central incisor" in wanted:
        question = "Is it the one right at the middle, or the one just beside it?"
    elif "first premolar" in wanted:
        question = "Is it just behind your pointy canine tooth, or one further back?"
    else:
        question = "Counting from the very back, is it the last one, the second, or the third?"

    return {
        "resolved": False,
        "tooth": None,
        "label": ", ".join(tooth_label(n) for n in candidates[:6]),
        "candidates": candidates,
        "question": question,
    }


# One patient's chart. Tooth 30 carries an apical abscess: the lower first molar is the classic
# source of the deep-space infections that make dental pain an airway problem.
_FINDINGS: dict[int, dict[str, Any]] = {
    3: {
        "restoration": "Composite (Filtek Supreme Ultra, A2), placed 2017-03-08",
        "note": "Marginal breakdown at the distal edge. Replacement advised before it fails.",
        "status": "watch",
        "history": [
            {
                "date": "2017-03-08",
                "event": "Composite restoration, occlusal-distal",
                "detail": "Filtek Supreme Ultra nanocomposite, shade A2, total-etch",
                "provider": "Dr. A. Novak, DDS",
            },
            {
                "date": "2024-11-02",
                "event": "Bitewing radiograph",
                "detail": "Distal margin opening, no recurrent caries into dentine",
                "provider": "Dr. A. Novak, DDS",
            },
        ],
    },
    14: {
        "restoration": "Composite (Herculite Ultra, A3), placed 2022-06-15",
        "note": "Intact.",
        "status": "ok",
        "history": [
            {
                "date": "2022-06-15",
                "event": "Composite restoration, occlusal",
                "detail": "Herculite Ultra, shade A3, selective-etch",
                "provider": "Dr. M. Reyes, DMD",
            }
        ],
    },
    19: {
        "restoration": "Crown (monolithic zirconia), cemented 2020-09-30",
        "note": "Margins sound.",
        "status": "ok",
        "history": [
            {
                "date": "2020-08-11",
                "event": "Root canal therapy",
                "detail": "Three canals obturated, gutta-percha",
                "provider": "Dr. S. Iyer, DDS (endodontics)",
            },
            {
                "date": "2020-09-30",
                "event": "Crown cemented",
                "detail": "Monolithic zirconia, resin-modified glass ionomer cement",
                "provider": "Dr. A. Novak, DDS",
            },
        ],
    },
    30: {
        "restoration": "Deep amalgam, placed 2016-02-19",
        "note": (
            "Periapical radiolucency first seen 2024-11-02 and larger on 2026-02-14. "
            "Non-vital on cold testing. Root canal and crown pending — this is the tooth "
            "the patient reports pain in."
        ),
        "status": "urgent",
        "history": [
            {
                "date": "2016-02-19",
                "event": "Deep amalgam restoration, mesio-occlusal-distal",
                "detail": "Close to pulp horn; pulp capping with calcium hydroxide noted",
                "provider": "Dr. R. Bhatt, DDS",
            },
            {
                "date": "2024-11-02",
                "event": "Periapical radiograph",
                "detail": "Early periapical radiolucency at mesial root, approx. 2mm",
                "provider": "Dr. A. Novak, DDS",
            },
            {
                "date": "2026-02-14",
                "event": "Periapical radiograph",
                "detail": "Radiolucency enlarged to approx. 4mm. Cold test negative — non-vital",
                "provider": "Dr. A. Novak, DDS",
            },
            {
                "date": "2026-02-14",
                "event": "Endodontic referral raised",
                "detail": "Root canal then crown advised. Patient did not schedule",
                "provider": "Dr. A. Novak, DDS",
            },
        ],
    },
}

_HYGIENE_HISTORY = [
    {
        "date": "2025-05-20",
        "event": "Hygiene visit (prophylaxis)",
        "detail": "Full mouth scaling, generalised marginal bleeding noted at lower right",
        "provider": "L. Chen, RDH",
    },
    {
        "date": "2024-11-02",
        "event": "Hygiene visit (prophylaxis)",
        "detail": "Scaling and polish; localised calculus lower anterior",
        "provider": "L. Chen, RDH",
    },
]

_DEPTHS: dict[int, list[int]] = {
    3: [3, 3, 4, 3, 3, 3],
    14: [2, 3, 3, 2, 2, 3],
    18: [4, 5, 5, 4, 4, 4],
    19: [3, 3, 4, 3, 3, 3],
    30: [6, 7, 8, 6, 7, 6],
    31: [4, 4, 5, 4, 4, 4],
}

_BLEEDING = {3, 18, 30, 31}


def _severity(depths: list[int]) -> str:
    worst = max(depths)
    if worst >= 6:
        return "advanced"
    if worst >= 4:
        return "early"
    return "healthy"


def periochart(focus_tooth: int | None = None) -> dict[str, Any]:
    """The patient's periodontal chart, shaped for rendering and for reading aloud."""
    teeth = []
    for number, name, quadrant in _TEETH:
        depths = _DEPTHS.get(number)
        finding = _FINDINGS.get(number)
        if not depths and not finding:
            continue
        depths = depths or [2, 2, 3, 2, 2, 2]
        teeth.append(
            {
                "number": number,
                "name": name,
                "quadrant": quadrant,
                "quadrant_name": QUADRANT_NAMES[quadrant],
                "label": tooth_label(number),
                "depths_mm": depths,
                "max_depth_mm": max(depths),
                "bleeding_on_probing": number in _BLEEDING,
                "severity": _severity(depths),
                "restoration": (finding or {}).get("restoration", ""),
                "note": (finding or {}).get("note", ""),
                "status": (finding or {}).get("status", "ok"),
                "history": (finding or {}).get("history", []),
                "focus": number == focus_tooth,
            }
        )

    advanced = [t for t in teeth if t["severity"] == "advanced"]
    early = [t for t in teeth if t["severity"] == "early"]
    focus = next((t for t in teeth if t["number"] == focus_tooth), None)
    return {
        "system": "Universal Numbering System (1-32)",
        "last_prophylaxis": "2025-05-20",
        "months_since_prophylaxis": 14,
        "hygiene_due": True,
        "hygiene_history": _HYGIENE_HISTORY,
        # One line at the top of the clinician's view, naming the tooth and what the record
        # already knew about it. A chart that makes them hunt for the relevant tooth is a chart
        # that gets skimmed.
        "alert": (
            {
                "tooth": focus["number"],
                "label": focus["label"],
                "status": focus["status"],
                "headline": (
                    f"Patient reports pain at {focus['label']}. "
                    f"Pocket depth {focus['max_depth_mm']}mm"
                    + (", bleeding on probing" if focus["bleeding_on_probing"] else "")
                    + "."
                ),
                "known_history": focus["note"],
                "prior_events": len(focus["history"]),
            }
            if focus
            else None
        ),
        "teeth": teeth,
        "summary": {
            "advanced_sites": [t["number"] for t in advanced],
            "early_sites": [t["number"] for t in early],
            "bleeding_sites": sorted(_BLEEDING),
            "pending_treatment": [
                {"tooth": 30, "plan": "Root canal then crown", "urgency": "urgent"},
                {"tooth": 3, "plan": "Replace ageing composite", "urgency": "elective"},
                {"tooth": 0, "plan": "Hygiene visit — 14 months since last", "urgency": "due"},
            ],
        },
    }


def periochart_for_voice(focus_tooth: int | None = None) -> str:
    """Same chart, said out loud: no tables, no decimals, no tooth numbers read as digits."""
    chart = periochart(focus_tooth)
    lines = []
    if focus_tooth:
        t = next((x for x in chart["teeth"] if x["number"] == focus_tooth), None)
        if t:
            lines.append(
                f"{t['label']}: pockets to {t['max_depth_mm']} millimetres, "
                f"{'bleeding on probing' if t['bleeding_on_probing'] else 'no bleeding'}. "
                f"{t['note'] or t['restoration']}"
            )
    adv = chart["summary"]["advanced_sites"]
    if adv:
        lines.append(
            "Advanced pocketing at " + ", ".join(tooth_label(n) for n in adv) + "."
        )
    if chart["hygiene_due"]:
        lines.append(
            f"Hygiene visit is due — {chart['months_since_prophylaxis']} months since the last one."
        )
    lines.append("Pending: root canal and crown on the lower right first molar.")
    return " ".join(lines)
