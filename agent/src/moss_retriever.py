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
        """Create-or-upsert long-term index, then load locally for <10ms queries."""
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
            created = await self._client.create_index(
                name, docs, DEFAULT_MODEL, wait=True
            )
            info["created_job"] = getattr(created, "job_id", None)
            info["doc_count"] = getattr(created, "doc_count", len(docs))

        await self._client.load_index(name)
        self._long_term_loaded = True
        info["loaded"] = True
        return info

    async def get_session(self, session_id: str):
        """Short-term SessionIndex for this encounter / call (live-call pattern)."""
        if not self._client:
            return None
        if session_id in self._sessions:
            return self._sessions[session_id]
        session = await self._client.session(
            index_name=f"flare-{session_id}", model_id=DEFAULT_MODEL
        )
        self._sessions[session_id] = session
        return session

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
                    id=turn_id,
                    text=text.strip(),
                    metadata={"role": role, "source": "flarecheck-session"},
                )
            ],
            MutationOptions(upsert=True),
        )

    async def push_session(self, session_id: str) -> dict[str, Any] | None:
        if not self._client or session_id not in self._sessions:
            return None
        session = self._sessions[session_id]
        result = await session.push_index()
        return {
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
    ) -> list[Document]:
        """Hybrid query over long-term index (+ session when session_id set)."""
        if self._client:
            if not self._long_term_loaded:
                await self.ensure_index()
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
                    recent = await session.query(
                        query, QueryOptions(top_k=min(3, top_k), alpha=alpha)
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

            # Prefer higher scores; keep session + long-term mixed
            docs.sort(key=lambda x: float(x.metadata.get("score") or 0), reverse=True)
            return docs[: top_k + 2]

        # Mock: keyword rank over fixtures (+ optional in-memory session texts)
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
            return "No relevant history found."
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
