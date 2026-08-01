"""Deep research for any presenting complaint, grounded in real literature.

Europe PMC REST API — open, no key, covers PubMed/MEDLINE plus preprints:
https://europepmc.org/RestfulWebService

Design constraints for clinical safety:
  - Citations are fetched, never generated. A claim without a retrieved source is dropped.
  - Output is evidence *for a clinician to review*, not a diagnosis for the patient.
  - Queries are built from the complaint text only; no patient identifiers ever leave here.
"""

from __future__ import annotations

import re
from typing import Any

import httpx

SEARCH_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

# Terms that make a query clinically useful rather than a general web search
_EVIDENCE_HINTS = "(guideline OR management OR treatment OR randomized OR review)"

_STOPWORDS = {
    "the", "and", "with", "have", "has", "for", "was", "are", "been", "that", "this",
    "from", "about", "very", "just", "really", "since", "when", "what", "there", "here",
    "some", "much", "more", "than", "then", "them", "they", "i've", "i'm", "it's",
    "my", "me", "im", "ive", "feel", "feeling", "felt", "get", "getting", "got",
    "day", "days", "week", "weeks", "also", "like", "any", "all", "can", "cant",
    # Time, degree and narrative filler. Left in, these dominate an AND query and pull back
    # whatever famous paper happens to match — the cause of citations about heart disease
    # statistics being attached to a knee complaint.
    "after", "before", "during", "while", "most", "mornings", "morning", "evening",
    "night", "nights", "today", "yesterday", "started", "starting", "start", "began",
    "three", "four", "five", "several", "couple", "month", "months", "year", "years",
    "hour", "hours", "minute", "minutes", "time", "times", "still", "even", "much",
    "worse", "better", "little", "bit", "lot", "sometimes", "always", "never", "often",
    "going", "walking", "used", "makes", "make", "made", "think", "know", "thing",
    "please", "thanks", "hello", "doctor", "help", "need", "want", "would", "could",
}

# Lay vocabulary → the terms clinical literature actually indexes on. Keeping this explicit
# beats hoping an AND of conversational words lands on the right MeSH heading.
_SYNONYMS = {
    "shortness": "dyspnea",
    "breath": "dyspnea",
    "breathless": "dyspnea",
    "winded": "dyspnea",
    "throwing": "vomiting",
    "throw": "vomiting",
    "puking": "vomiting",
    "dizzy": "dizziness",
    "lightheaded": "dizziness",
    "itchy": "pruritus",
    "itch": "pruritus",
    "tired": "fatigue",
    "exhausted": "fatigue",
    "swollen": "swelling",
    "runny": "rhinorrhea",
    "stuffy": "congestion",
    "sore": "pain",
    "hurts": "pain",
    "hurting": "pain",
    "aches": "pain",
    "aching": "pain",
    "achy": "pain",
    "numb": "numbness",
    "tingling": "paresthesia",
}

_ANATOMY = {
    "knee", "shoulder", "hip", "ankle", "elbow", "wrist", "back", "neck", "chest",
    "abdomen", "stomach", "head", "throat", "ear", "eye", "sinus", "foot", "hand",
    "leg", "arm", "jaw", "tooth", "skin", "scalp", "elbows", "knees", "hands",
}

_SYMPTOMS = {
    "pain", "swelling", "rash", "cough", "fever", "headache", "headaches", "nausea",
    "vomiting", "diarrhea", "constipation", "dyspnea", "wheeze", "wheezing", "fatigue",
    "dizziness", "pruritus", "bleeding", "numbness", "paresthesia", "stiffness",
    "eczema", "psoriasis", "migraine", "insomnia", "palpitations", "rhinorrhea",
    "congestion", "photophobia", "weakness", "cramping", "burning", "discharge",
}


def _clinical_terms(text: str) -> tuple[list[str], list[str]]:
    """Split a complaint into (anatomy, symptom) terms, normalised to literature vocabulary."""
    words = re.findall(r"[a-zA-Z][a-zA-Z\-']{2,}", (text or "").lower())
    anatomy: list[str] = []
    symptoms: list[str] = []
    other: list[str] = []
    for w in words:
        w = _SYNONYMS.get(w, w)
        if w in _STOPWORDS or len(w) < 3:
            continue
        bucket = anatomy if w in _ANATOMY else symptoms if w in _SYMPTOMS else other
        if w not in bucket:
            bucket.append(w)
    # Unrecognised words are weak evidence; keep a couple as a fallback only.
    return anatomy[:2], (symptoms or other[:2])[:3]


# Named conditions are already the indexed concept; pairing them with anatomy ("elbows
# eczema") produces a phrase no paper uses, and zero results.
_CONDITIONS = {
    "eczema", "psoriasis", "migraine", "asthma", "insomnia", "dermatitis", "urticaria",
    "bronchiectasis", "sinusitis", "pharyngitis", "cellulitis", "gout", "tendinitis",
    "bursitis", "osteoarthritis",
}

# Reviews and guidelines are what a clinician wants; case reports are noise here.
_REVIEW_FILTER = '(PUB_TYPE:"review" OR PUB_TYPE:"guideline" OR PUB_TYPE:"practice guideline")'
_CASE_REPORT_TITLE = re.compile(r"\bcase (reports?|series)\b", re.I)


def _phrases(text: str) -> tuple[list[str], list[str]]:
    """Return (specific, broad) phrase lists, kept apart so they never dilute each other.

    OR-ing `"throat pain"` with a bare `"pain"` hands back pain-management guidelines for
    unrelated body parts, which defeats the point of the specific phrase.
    """
    anatomy, symptoms = _clinical_terms(text)
    conditions = [s for s in symptoms if s in _CONDITIONS]
    if conditions:
        return [f'TITLE_ABS:"{c}"' for c in conditions], []

    specific = [f'TITLE_ABS:"{a} {s}"' for a in anatomy for s in symptoms]
    broad = [f'TITLE_ABS:"{t}"' for t in symptoms] or [f'TITLE_ABS:"{t}"' for t in anatomy]
    return (specific or broad), (broad if specific else [])


def complaint_to_query(text: str) -> str:
    """The most specific query we'd try for this complaint (kept for display and tests)."""
    return _query_ladder(text)[0]


def _query_ladder(text: str) -> list[str]:
    """Queries from most to least specific; `search` walks these until it has enough.

    A single over-constrained query is the failure mode we're avoiding: when nothing matches,
    Europe PMC returns whatever is loosely related, which is how a knee complaint ended up
    citing cardiovascular statistics.
    """
    specific_list, broad_list = _phrases(text)
    if not specific_list:
        return ['TITLE_ABS:"symptom assessment" AND HAS_ABSTRACT:Y']

    ladder = []
    specific = " OR ".join(specific_list[:3])
    ladder.append(f"({specific}) AND {_REVIEW_FILTER} AND HAS_ABSTRACT:Y")
    ladder.append(f"({specific}) AND {_EVIDENCE_HINTS} AND HAS_ABSTRACT:Y")
    if broad_list:
        broad = " OR ".join(broad_list[:3])
        ladder.append(f"({broad}) AND {_REVIEW_FILTER} AND HAS_ABSTRACT:Y")
        ladder.append(f"({broad}) AND {_EVIDENCE_HINTS} AND HAS_ABSTRACT:Y")
    return ladder


class ResearchService:
    def __init__(self, timeout: float = 20.0) -> None:
        self.timeout = timeout
        self.last_query = ""

    async def search(self, complaint: str, limit: int = 5) -> list[dict[str, Any]]:
        # No CITED sort: ranking by citation count on a loose query is what surfaced famous
        # but irrelevant papers. Relevance first, then require an abstract so the agent has
        # something to actually read.
        results: list[dict[str, Any]] = []
        used_query = ""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for query in _query_ladder(complaint):
                r = await client.get(
                    SEARCH_URL,
                    params={
                        "query": query,
                        "format": "json",
                        "pageSize": str(max(1, min(limit * 2, 25))),
                        "resultType": "lite",
                    },
                )
                r.raise_for_status()
                found = ((r.json().get("resultList") or {}).get("result")) or []
                found = [f for f in found if not _CASE_REPORT_TITLE.search(f.get("title") or "")]
                if found:
                    results, used_query = found, query
                    break

        self.last_query = used_query
        citations: list[dict[str, Any]] = []
        for item in results[:limit]:
            citations.append(
                {
                    "title": item.get("title"),
                    "authors": item.get("authorString"),
                    "journal": item.get("journalTitle") or item.get("bookOrReportDetails"),
                    "year": item.get("pubYear"),
                    "doi": item.get("doi"),
                    "pmid": item.get("pmid"),
                    "cited_by": item.get("citedByCount"),
                    "open_access": item.get("isOpenAccess") == "Y",
                    "url": (
                        f"https://doi.org/{item['doi']}"
                        if item.get("doi")
                        else f"https://europepmc.org/article/MED/{item.get('pmid')}"
                        if item.get("pmid")
                        else None
                    ),
                }
            )
        return [c for c in citations if c["title"]]

    async def brief(self, complaint: str, limit: int = 5) -> dict[str, Any]:
        """Citations plus a compact text block an LLM can quote without inventing sources."""
        try:
            citations = await self.search(complaint, limit=limit)
            error = None
        except Exception as exc:  # noqa: BLE001 - research is additive, never fatal
            citations, error = [], f"{type(exc).__name__}: {exc}"

        lines = []
        for i, c in enumerate(citations, start=1):
            meta = " ".join(
                str(x) for x in [c.get("journal"), c.get("year")] if x
            )
            cited = f", cited {c['cited_by']}x" if c.get("cited_by") else ""
            lines.append(f"[{i}] {c['title']} — {meta}{cited}" + (f" doi:{c['doi']}" if c.get("doi") else ""))

        return {
            "query": self.last_query or complaint_to_query(complaint),
            "citations": citations,
            "text": (
                "Retrieved evidence (Europe PMC). Cite only these, by number:\n"
                + "\n".join(lines)
                if lines
                else "No literature retrieved — say so rather than citing anything."
            ),
            "count": len(citations),
            "error": error,
            "source": "europepmc",
        }
