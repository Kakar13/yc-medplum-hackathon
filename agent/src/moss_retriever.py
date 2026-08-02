"""Moss retrieval — best practices from https://github.com/usemoss/moss

Pattern (live-call context):
  - Long-term: load_index once (patient history + protocols)
  - Short-term: session(encounter_id) for transcript turns
  - Each turn: query both, merge for the agent
  - End: session.push_index()

Docs: https://docs.moss.dev/docs/build/live-call-context
SDK samples: examples/python/comprehensive_sample.py
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from langchain_core.documents import Document

from .config import Settings, get_settings

logger = logging.getLogger(__name__)

SAMPLE_PATH = Path(__file__).resolve().parents[1] / "data" / "sample_history.json"

# Hybrid blend — Moss README / docs: 0.0 keyword … 1.0 semantic
DEFAULT_ALPHA = 0.6
DEFAULT_TOP_K = 4
DEFAULT_MODEL = "moss-minilm"

# Moss always returns top_k documents, with no notion of "nothing matched". Without a floor a
# knee complaint retrieves the patient's eczema history at ~0.6 and it lands in the prompt as
# if it were relevant. Genuine hits score ~0.9-1.0, so this cleanly separates them.
MIN_LONG_TERM_SCORE = 0.75

# One shared short-term index, partitioned by encounter in metadata. A per-encounter index
# exhausts the account's index quota after a couple of visits (HTTP 429
# USAGE_LIMIT_EXCEEDED), which used to fail silently at push time.
SESSION_INDEX_NAME = "preflight-session"


class MossService:
    """Sub-10ms semantic search: persistent index + per-encounter session."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._docs = self._load_sample()
        self._client = None
        self._long_term_loaded = False
        self._sessions: dict[str, Any] = {}
        # Live whenever Moss keys exist (even if Medplum is still mock)
        if self.settings.moss_project_id and self.settings.moss_project_key:
            from moss import MossClient

            self._client = MossClient(
                self.settings.moss_project_id, self.settings.moss_project_key
            )

    @property
    def live(self) -> bool:
        return self._client is not None

    def _load_sample(self) -> list[dict[str, Any]]:
        if SAMPLE_PATH.exists():
            return json.loads(SAMPLE_PATH.read_text())
        return []

    def _to_document_infos(self, rows: list[dict[str, Any]] | None = None):
        from moss import DocumentInfo

        rows = rows if rows is not None else self._docs
        return [
            DocumentInfo(
                id=str(d["id"]),
                text=d["text"],
                metadata={str(k): str(v) for k, v in (d.get("metadata") or {}).items()},
            )
            for d in rows
        ]

    async def ensure_index(self, *, force_reseed: bool = False) -> dict[str, Any]:
        """Create-or-upsert long-term index, then load locally for <10ms queries.

        Quota / index-limit failures degrade to local fixtures. Raising here used to take
        down every voice turn that touched moss_search — the patient heard silence while
        the agent looped on a 429.
        """
        if not self._client:
            return {"mode": "mock", "docs": len(self._docs)}

        from moss import MutationOptions

        name = self.settings.moss_index_name
        docs = self._to_document_infos()
        info: dict[str, Any] = {"mode": "live", "index": name, "docs": len(docs)}

        try:
            existing = await self._client.get_index(name)
            info["status_before"] = getattr(existing, "status", None)
            info["doc_count_before"] = getattr(existing, "doc_count", None)
            # Upsert fixtures so eczema/protocol updates land without recreate
            result = await self._client.add_docs(
                name, docs, MutationOptions(upsert=True)
            )
            info["upsert_job"] = getattr(result, "job_id", None)
            info["doc_count"] = getattr(result, "doc_count", None)
        except Exception as exc:
            logger.info("Moss get_index/add_docs → create_index (%s)", exc)
            try:
                created = await self._client.create_index(
                    name, docs, DEFAULT_MODEL, wait=True
                )
                info["created_job"] = getattr(created, "job_id", None)
                info["doc_count"] = getattr(created, "doc_count", len(docs))
            except Exception as create_exc:
                # USAGE_LIMIT_EXCEEDED / Index limit of 3 — keep the call alive on fixtures.
                logger.warning(
                    "Moss unavailable (%s); falling back to local fixtures", create_exc
                )
                self._client = None
                info["mode"] = "fixture-fallback"
                info["error"] = str(create_exc)
                return info

        try:
            await self._client.load_index(name)
            self._long_term_loaded = True
            info["loaded"] = True
        except Exception as load_exc:
            logger.warning("Moss load_index failed (%s); using fixtures", load_exc)
            self._client = None
            info["mode"] = "fixture-fallback"
            info["error"] = str(load_exc)
        return info

    async def get_session(self, session_id: str):
        """Short-term SessionIndex, shared across encounters and filtered by metadata."""
        if not self._client:
            return None
        if SESSION_INDEX_NAME not in self._sessions:
            self._sessions[SESSION_INDEX_NAME] = await self._client.session(
                index_name=SESSION_INDEX_NAME, model_id=DEFAULT_MODEL
            )
        return self._sessions[SESSION_INDEX_NAME]

    async def add_turn(
        self,
        session_id: str,
        *,
        turn_id: str,
        text: str,
        role: str = "patient",
    ) -> None:
        """Index a live transcript turn into the session (local, then optional push)."""
        if not self._client or not text.strip():
            return
        from moss import DocumentInfo, MutationOptions

        session = await self.get_session(session_id)
        if session is None:
            return
        await session.add_docs(
            [
                DocumentInfo(
                    id=f"{session_id}:{turn_id}",
                    text=text.strip(),
                    metadata={
                        "role": role,
                        "source": "preflight-session",
                        "encounter": session_id,
                    },
                )
            ],
            MutationOptions(upsert=True),
        )

    async def push_session(self, session_id: str) -> dict[str, Any] | None:
        """Persist the short-term index. Returns an error dict rather than raising.

        Callers treat this as best-effort, so a failure must still be visible — a silent
        `except: pass` here previously made a handoff look successful while the human
        received none of the conversation context.
        """
        if not self._client or SESSION_INDEX_NAME not in self._sessions:
            return None
        session = self._sessions[SESSION_INDEX_NAME]
        try:
            result = await session.push_index()
        except Exception as exc:  # noqa: BLE001 - surfaced to the caller, never fatal
            logger.warning("Moss push_session failed for %s: %s", session_id, exc)
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        return {
            "ok": True,
            "index_name": getattr(result, "index_name", None),
            "doc_count": getattr(result, "doc_count", None),
        }

    async def search(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        *,
        session_id: str | None = None,
        metadata_type: str | None = None,
        alpha: float = DEFAULT_ALPHA,
        min_score: float = MIN_LONG_TERM_SCORE,
    ) -> list[Document]:
        """Hybrid query over long-term index (+ session when session_id set).

        Long-term hits below `min_score` are dropped: retrieving unrelated history is worse
        than retrieving nothing, because the agent will try to use it.
        """
        if self._client:
            if not self._long_term_loaded:
                await self.ensure_index()
            # ensure_index may have disabled the client on quota; fall through to fixtures.
            if not self._client:
                pass
            else:
                return await self._search_live(
                    query,
                    top_k,
                    session_id=session_id,
                    metadata_type=metadata_type,
                    alpha=alpha,
                    min_score=min_score,
                )

        # Mock / fixture fallback: keyword rank over fixtures
        return self._search_fixtures(query, top_k, metadata_type=metadata_type)

    async def _search_live(
        self,
        query: str,
        top_k: int,
        *,
        session_id: str | None,
        metadata_type: str | None,
        alpha: float,
        min_score: float,
    ) -> list[Document]:
        assert self._client is not None
        try:
            from moss import QueryOptions

            opts_kwargs: dict[str, Any] = {"top_k": top_k, "alpha": alpha}
            if metadata_type:
                opts_kwargs["filter"] = {
                    "field": "type",
                    "condition": {"$eq": metadata_type},
                }
            options = QueryOptions(**opts_kwargs)

            knowledge = await self._client.query(
                self.settings.moss_index_name, query, options
            )
            docs: list[Document] = []
            for d in knowledge.docs:
                if float(d.score or 0) < min_score:
                    continue
                meta = dict(d.metadata or {})
                docs.append(
                    Document(
                        page_content=d.text,
                        metadata={
                            **meta,
                            "score": d.score,
                            "id": d.id,
                            "moss_lane": "long-term",
                            "time_taken_ms": getattr(knowledge, "time_taken_ms", None),
                        },
                    )
                )

            if session_id:
                session = await self.get_session(session_id)
                if session is not None:
                    # This encounter's own turns only — the index is shared.
                    recent = await session.query(
                        query,
                        QueryOptions(
                            top_k=min(3, top_k),
                            alpha=alpha,
                            filter={
                                "field": "encounter",
                                "condition": {"$eq": session_id},
                            },
                        ),
                    )
                    for d in recent.docs:
                        meta = dict(d.metadata or {})
                        docs.append(
                            Document(
                                page_content=d.text,
                                metadata={
                                    **meta,
                                    "score": d.score,
                                    "id": d.id,
                                    "moss_lane": "session",
                                    "time_taken_ms": getattr(
                                        recent, "time_taken_ms", None
                                    ),
                                },
                            )
                        )

            docs.sort(key=lambda x: float(x.metadata.get("score") or 0), reverse=True)
            return docs[: top_k + 2]
        except Exception as exc:  # noqa: BLE001 - never take the voice turn down for Moss
            logger.warning("Moss query failed (%s); using fixtures", exc)
            self._client = None
            return self._search_fixtures(query, top_k, metadata_type=metadata_type)

    def _search_fixtures(
        self,
        query: str,
        top_k: int,
        *,
        metadata_type: str | None = None,
    ) -> list[Document]:
        q = query.lower()
        scored: list[tuple[float, dict[str, Any]]] = []
        for d in self._docs:
            if metadata_type and (d.get("metadata") or {}).get("type") != metadata_type:
                continue
            text = d["text"].lower()
            score = sum(1.0 for tok in q.split() if tok in text)
            if score:
                scored.append((score, d))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            Document(
                page_content=d["text"],
                metadata={
                    "score": s,
                    "id": d["id"],
                    "source": "mock",
                    **(d.get("metadata") or {}),
                },
            )
            for s, d in scored[:top_k]
        ]

    async def search_text(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        *,
        session_id: str | None = None,
        metadata_type: str | None = None,
    ) -> str:
        docs = await self.search(
            query, top_k=top_k, session_id=session_id, metadata_type=metadata_type
        )
        if not docs:
            return (
                "No relevant history found for this query. "
                "Do not infer history that isn't here."
            )
        lines = []
        for i, d in enumerate(docs):
            lane = d.metadata.get("moss_lane") or d.metadata.get("source", "?")
            ms = d.metadata.get("time_taken_ms")
            timing = f" {ms}ms" if ms is not None else ""
            lines.append(
                f"[{d.metadata.get('id', i)}|{lane}] (score={d.metadata.get('score')}){timing}\n"
                f"{d.page_content}"
            )
        return "\n\n".join(lines)
