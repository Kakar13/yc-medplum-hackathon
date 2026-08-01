"""Moss retrieval — live SDK or local JSON fixtures (LangChain-compatible)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from langchain_core.documents import Document

from .config import Settings, get_settings

SAMPLE_PATH = Path(__file__).resolve().parents[1] / "data" / "sample_history.json"


class MossService:
    """Sub-10ms semantic search over patient history / protocols.

    Live path follows Moss + LangChain cookbook patterns:
    https://docs.moss.dev/docs/integrations/langchain
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._docs = self._load_sample()
        self._client = None
        self._loaded = False
        if not self.settings.use_mock and self.settings.moss_project_id:
            from moss import MossClient

            self._client = MossClient(
                self.settings.moss_project_id, self.settings.moss_project_key
            )

    def _load_sample(self) -> list[dict[str, Any]]:
        if SAMPLE_PATH.exists():
            return json.loads(SAMPLE_PATH.read_text())
        return []

    async def ensure_index(self) -> None:
        """Optionally upsert sample docs into Moss (live mode)."""
        if not self._client or self._loaded:
            return
        from moss import DocumentInfo

        docs = [
            DocumentInfo(id=d["id"], text=d["text"], metadata=d.get("metadata") or {})
            for d in self._docs
        ]
        name = self.settings.moss_index_name
        try:
            await self._client.create_index(name, docs, "moss-minilm")
        except Exception:
            # Index may already exist — try load + add
            pass
        await self._client.load_index(name)
        self._loaded = True

    async def search(self, query: str, top_k: int = 3) -> list[Document]:
        if self._client:
            await self.ensure_index()
            from moss import QueryOptions

            results = await self._client.query(
                self.settings.moss_index_name,
                query,
                QueryOptions(top_k=top_k, alpha=0.6),
            )
            return [
                Document(
                    page_content=d.text,
                    metadata={"score": d.score, "id": d.id},
                )
                for d in results.docs
            ]

        # Mock: naive keyword rank
        q = query.lower()
        scored: list[tuple[float, dict[str, Any]]] = []
        for d in self._docs:
            text = d["text"].lower()
            score = sum(1.0 for tok in q.split() if tok in text)
            if score:
                scored.append((score, d))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            Document(
                page_content=d["text"],
                metadata={"score": s, "id": d["id"], **(d.get("metadata") or {})},
            )
            for s, d in scored[:top_k]
        ]

    async def search_text(self, query: str, top_k: int = 3) -> str:
        docs = await self.search(query, top_k=top_k)
        if not docs:
            return "No relevant history found."
        return "\n\n".join(
            f"[{d.metadata.get('id', i)}] (score={d.metadata.get('score')})\n{d.page_content}"
            for i, d in enumerate(docs)
        )
