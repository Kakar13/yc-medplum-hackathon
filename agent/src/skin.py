"""Body-region mapping for skin complaints: where it is, and what the record holds there.

The dental equivalent of this module is `perio`. Same idea, different anatomy: a patient says
"the insides of my elbows" and the clinician needs a body site plus every prior flare, treatment
and swab recorded at that site.

Region names follow the plain-language terms patients use, mapped to the anatomical site so the
FHIR Observation carries a real body site rather than a phrase.
"""

from __future__ import annotations

from typing import Any

# key, patient words that mean it, anatomical site, and where it sits on the body diagram
_REGIONS: list[tuple[str, tuple[str, ...], str, str, float, float]] = [
    ("face", ("face", "cheek", "forehead", "chin"), "Face", "front", 50, 7),
    ("neck", ("neck", "throat"), "Neck", "front", 50, 15),
    ("chest", ("chest", "breast", "sternum"), "Anterior chest", "front", 50, 25),
    ("abdomen", ("stomach", "belly", "abdomen", "tummy"), "Abdomen", "front", 50, 38),
    ("left_antecubital", ("inside of my left elbow", "left elbow crease"), "Left antecubital fossa", "front", 30, 33),
    ("right_antecubital", ("inside of my right elbow", "right elbow crease"), "Right antecubital fossa", "front", 70, 33),
    ("antecubital", ("inside of my elbows", "elbow crease", "elbow creases", "inner elbow", "insides of my elbows", "crook of my arm"), "Antecubital fossae, bilateral", "front", 30, 33),
    ("hands", ("hand", "hands", "fingers", "knuckles", "palm"), "Hands, bilateral", "front", 20, 48),
    ("wrists", ("wrist", "wrists"), "Wrists, bilateral", "front", 23, 44),
    ("knees", ("knee", "knees", "behind my knees", "back of my knees"), "Popliteal fossae, bilateral", "back", 40, 62),
    ("feet", ("foot", "feet", "ankle", "ankles", "toes"), "Feet, bilateral", "front", 44, 90),
    ("scalp", ("scalp", "head", "hairline"), "Scalp", "back", 50, 5),
    ("back", ("back", "shoulder blades", "upper back"), "Upper back", "back", 50, 26),
]

REGION_BY_KEY = {k: {"key": k, "site": site, "view": view, "x": x, "y": y} for k, _, site, view, x, y in _REGIONS}


def locate_region(description: str) -> dict[str, Any]:
    """Turn "the insides of my elbows" into a body site.

    Longest match wins, so "inside of my left elbow" beats the bilateral "inner elbow" and the
    chart records one side rather than both. Getting laterality wrong is a charting error the
    clinician has to unpick in the room.
    """
    text = description.lower()
    hits: list[tuple[int, str]] = []
    for key, words, _site, _view, _x, _y in _REGIONS:
        for w in words:
            if w in text:
                hits.append((len(w), key))
    if not hits:
        return {
            "resolved": False,
            "regions": [],
            "question": "Whereabouts is it — hands, elbows, behind the knees, face, or somewhere else?",
        }
    # Eczema is rarely in one place — "my elbows and my hands" is two sites and charting one of
    # them loses half the distribution. Keep every distinct area, and only collapse within an
    # area: a named side supersedes the bilateral term for the same body part.
    keys = list(dict.fromkeys(k for _l, k in sorted(hits, reverse=True)))
    for key in list(keys):
        if key.startswith(("left_", "right_")):
            bilateral = key.split("_", 1)[1]
            if bilateral in keys:
                keys.remove(bilateral)
    return {"resolved": True, "regions": keys, "question": ""}


# This patient's recorded skin history, by site. Mirrors what a dermatology record actually
# holds: when it flared, what was tried, and whether it worked.
_HISTORY: dict[str, list[dict[str, str]]] = {
    "antecubital": [
        {
            "date": "2024-03-11",
            "event": "Atopic dermatitis flare",
            "detail": "Lichenified plaques both antecubital fossae. Betamethasone valerate 0.1% for two weeks.",
            "provider": "Dr. P. Almeida, Dermatology",
        },
        {
            "date": "2025-01-22",
            "event": "Recurrence",
            "detail": "Stepped down to tacrolimus 0.1% ointment to spare the skin. Good response by week three.",
            "provider": "Dr. P. Almeida, Dermatology",
        },
    ],
    "hands": [
        {
            "date": "2025-06-04",
            "event": "Hand dermatitis",
            "detail": "Fissuring at the finger webs. Patch testing positive to fragrance mix I.",
            "provider": "Dr. P. Almeida, Dermatology",
        },
        {
            "date": "2025-06-04",
            "event": "Allergy recorded",
            "detail": "Fragrance mix I — avoid scented emollients and detergents.",
            "provider": "Dr. P. Almeida, Dermatology",
        },
    ],
    "knees": [
        {
            "date": "2024-03-11",
            "event": "Atopic dermatitis flare",
            "detail": "Popliteal involvement noted alongside antecubital disease.",
            "provider": "Dr. P. Almeida, Dermatology",
        }
    ],
}

_SEVERITY = {"antecubital": "moderate", "hands": "active", "knees": "mild"}


def skin_map(focus: list[str] | None = None) -> dict[str, Any]:
    """The body map, shaped for rendering and for reading aloud."""
    focus = focus or []
    regions = []
    for key, _words, site, view, x, y in _REGIONS:
        history = _HISTORY.get(key, [])
        if not history and key not in focus:
            continue
        regions.append(
            {
                "key": key,
                "site": site,
                "view": view,
                "x": x,
                "y": y,
                "severity": _SEVERITY.get(key, "reported"),
                "history": history,
                "prior_events": len(history),
                "focus": key in focus,
                "new_site": key in focus and not history,
            }
        )

    focused = [r for r in regions if r["focus"]]
    alert = None
    if focused:
        r = focused[0]
        known = (
            f"{r['prior_events']} prior episodes recorded at this site, most recently "
            f"{r['history'][-1]['date']}."
            if r["history"]
            else "No previous disease recorded at this site — new distribution."
        )
        alert = {
            "site": r["site"],
            "headline": f"Patient reports a flare at {r['site'].lower()}.",
            "known_history": known,
            "prior_events": r["prior_events"],
            "status": "watch" if r["history"] else "urgent",
        }

    return {
        "coding": "Body site, patient-reported and clinician-confirmed history",
        "regions": regions,
        "alert": alert,
        "allergies": ["Fragrance mix I (patch tested 2025-06-04)"],
        "summary": {
            "affected_now": [r["site"] for r in focused],
            "previously_affected": [r["site"] for r in regions if r["history"]],
        },
    }


def skin_map_for_voice(focus: list[str] | None = None) -> str:
    """Same map, said out loud: no coordinates, no site codes."""
    data = skin_map(focus)
    lines = []
    if data["alert"]:
        lines.append(f"{data['alert']['headline']} {data['alert']['known_history']}")
    prior = data["summary"]["previously_affected"]
    if prior:
        lines.append("Previously affected: " + ", ".join(p.lower() for p in prior) + ".")
    if data["allergies"]:
        lines.append("On record: allergic to " + ", ".join(data["allergies"]) + ".")
    return " ".join(lines)
