---
name: moss-dev
description: >-
  Integrate Moss real-time semantic search (sub-10ms) for voice agents and
  copilots. Use when grounding agents with local/cloud indexes, live-call
  context, sessions, hybrid search, LiveKit/Pipecat/LangChain retrieval, or
  when the user mentions Moss, moss.dev, usemoss/moss, or real-time semantic search.
---

# Moss (moss.dev)

- GitHub (source of truth for SDK samples): [usemoss/moss](https://github.com/usemoss/moss)
- Docs: [docs.moss.dev](https://docs.moss.dev/docs) · [llms.txt](https://docs.moss.dev/llms.txt)

Moss is a **search runtime** (not a remote vector DB): load an index into your process, query in **<10 ms**. Hybrid semantic + keyword, built-in embeddings (`moss-minilm` / `moss-mediumlm`), metadata filters, sessions for live calls.

## Agent instructions (best practices)

1. **Live-call pattern** — every FlareCheck / voice turn:
   - Long-term: `load_index("patient-history")` once (conditions, meds, protocols)
   - Short-term: `client.session(f"flare-{encounter_id}")` — `add_docs` each transcript turn
   - Query **both** each turn; `session.push_index()` at handoff / end
   - Ref: [Live-Call Context](https://docs.moss.dev/docs/build/live-call-context) · repo examples under `examples/python/`
2. Prefer **`DocumentInfo(id, text, metadata)`** with string metadata values; upsert via `MutationOptions(upsert=True)`.
3. Default model **`moss-minilm`**; use `moss-mediumlm` only if accuracy > latency.
4. Hybrid **`QueryOptions(top_k=…, alpha=0.6)`** — `0.0` keyword, `1.0` semantic.
5. Metadata filters: `QueryOptions(filter={"field": "type", "condition": {"$eq": "Protocol"}})`.
6. Log / surface `results.time_taken_ms` when debugging latency.
7. Do **not** add Pinecone/Chroma for this hack — Moss is the retrieval layer.
8. This repo: [`agent/src/moss_retriever.py`](../../agent/src/moss_retriever.py), seed with `python -m src.seed_moss`.

## Portal setup

1. Sign up at [moss.dev](https://moss.dev), create project
2. Copy **Project ID** + **Project Key** → `MOSS_PROJECT_ID` / `MOSS_PROJECT_KEY`
3. Discord: [Moss Discord](https://moss.link/discord)

```bash
pip install moss   # Python 3.10+
# or: npm install @moss-dev/moss
```

## Canonical Python flow (from usemoss/moss README)

```python
from moss import MossClient, DocumentInfo, QueryOptions, MutationOptions

client = MossClient(project_id, project_key)
await client.create_index("patient-history", docs, "moss-minilm", wait=True)
# later updates:
await client.add_docs("patient-history", docs, MutationOptions(upsert=True))
await client.load_index("patient-history")
results = await client.query(
    "patient-history",
    "eczema flare itch",
    QueryOptions(top_k=3, alpha=0.6),
)
print(results.time_taken_ms, results.docs[0].text)
```

## Live session (short-term)

```python
session = await client.session(index_name=f"flare-{encounter_id}")
await session.add_docs([DocumentInfo(id="turn-1", text="...", metadata={"role": "patient"})])
recent = await session.query(query, QueryOptions(top_k=3, alpha=0.6))
await session.push_index()
```

## Hackathon wiring (FlareCheck)

Deepgram (or text) → each turn `moss_search` (long-term + session) → LangGraph → Medplum chart → `add_turn` into session. Keep retrieval in-process so voice stays snappy.
