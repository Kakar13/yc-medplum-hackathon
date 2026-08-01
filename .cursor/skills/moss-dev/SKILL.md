---
name: moss-dev
description: >-
  Integrate Moss real-time semantic search (sub-10ms) for voice agents and
  copilots. Use when grounding agents with local/cloud indexes, live-call
  context, sessions, hybrid search, LiveKit/Pipecat/LangChain retrieval, or
  when the user mentions Moss, moss.dev, or real-time semantic search.
---

# Moss (moss.dev)

Docs: [docs.moss.dev](https://docs.moss.dev/docs) · Index: [llms.txt](https://docs.moss.dev/llms.txt)

Moss is the runtime for **real-time semantic search** in conversational apps. Sub-10 ms lookups, instant index updates, no extra infra. Runs in browser, on-device, or cloud — same API. Index lives next to the agent: retrieval is a function call, not a remote round trip.

## Agent instructions

1. Use Moss for **history-aware / knowledge-grounded** agent turns (patient FAQ, clinical protocols, prior visit notes chunks — non-PHI fixtures for the hack when possible).
2. Prefer **live-call pattern**: load long-term index once + session for short-term transcript/context; query both each turn.
3. Default model `moss-minilm`; use `moss-mediumlm` when accuracy matters more than speed.
4. Hybrid search via `alpha`: `0.0` keyword, `1.0` semantic, blend in between.
5. Do not invent a custom vector DB — Moss is the sponsored retrieval layer for this hackathon.

## Portal setup

1. Sign up at Moss, confirm email, sign in
2. **Create Index** → copy **Project ID** and **Project Key**
3. Discord onboarding: [Moss Discord](https://discord.gg/eMXExuafBR)

```bash
export MOSS_PROJECT_ID="your_project_id"
export MOSS_PROJECT_KEY="your_project_key"
```

## Install

```bash
# JavaScript (Node 18+)
npm install @moss-dev/moss

# Python (3.10+)
pip install moss
```

Samples: [github.com/usemoss/moss](https://github.com/usemoss/moss) (`javascript/*_sample.ts`, `python/*_sample.py`).

## Quickstart (JS)

```ts
import { MossClient, DocumentInfo } from '@moss-dev/moss'

const client = new MossClient(process.env.MOSS_PROJECT_ID!, process.env.MOSS_PROJECT_KEY!)
const documents: DocumentInfo[] = [
  { id: 'doc1', text: 'How do I track my order? ...', metadata: { category: 'shipping' } },
  { id: 'doc2', text: 'What is your return policy? ...', metadata: { category: 'returns' } },
]
const indexName = 'faqs'
await client.createIndex(indexName, documents, { modelId: 'moss-minilm' })
await client.loadIndex(indexName)
const results = await client.query(indexName, 'How do I return a damaged product?', { topK: 3 })
console.log(results.docs[0])
```

## Quickstart (Python)

```python
import os, asyncio
from moss import MossClient, DocumentInfo, QueryOptions

client = MossClient(os.getenv("MOSS_PROJECT_ID"), os.getenv("MOSS_PROJECT_KEY"))

async def main():
    await client.create_index("faqs", [
        DocumentInfo(id="doc1", text="How do I track my order? ...", metadata={"category": "shipping"}),
        DocumentInfo(id="doc2", text="What is your return policy? ...", metadata={"category": "returns"}),
    ], "moss-minilm")
    await client.load_index("faqs")
    results = await client.query("faqs", "How do I return a damaged product?", QueryOptions(top_k=3, alpha=0.6))
    print(results.docs[0].id, results.docs[0].text, results.docs[0].score)

asyncio.run(main())
```

## How it works

| Concept | Role |
|---------|------|
| **Index** | Packaged searchable knowledge |
| **Embeddings** | On-device (`moss-minilm` / `moss-mediumlm`) or bring-your-own |
| **Sessions** | Local real-time index during a live interaction; sync later |
| **Retrieval** | In-memory semantic / keyword / hybrid |
| **Storage** | Local persist + optional cloud sync |

## Live-call context (preferred for voice)

During a call, query two indexes:

| | Short-term | Long-term |
|--|------------|-----------|
| **What** | Live transcript / working notes | FAQs, policies, profile, history |
| **Where** | `client.session(call_id)` | `load_index("...")` once |
| **Lifetime** | This interaction (+ optional `push_index`) | Across interactions |

```python
await client.load_index("support-faqs")
session = await client.session(index_name=call_id)
await session.add_docs([DocumentInfo(id="turn-1", text="...")])
knowledge = await client.query("support-faqs", query, QueryOptions(top_k=3))
recent = await session.query(query, QueryOptions(top_k=3))
# pass both result sets into the LLM / voice agent turn
await session.push_index()
```

Docs: [Live-Call Context](https://docs.moss.dev/docs/build/live-call-context) · [Sessions](https://docs.moss.dev/docs/integrate/sessions)

## Capabilities & integrations

- [Real-Time Local Indexing](https://docs.moss.dev/docs/build/real-time-local-indexing)
- [Data Hydration & Sync](https://docs.moss.dev/docs/build/data-hydration-sync)
- [Cross-Agent Handoff](https://docs.moss.dev/docs/build/cross-agent-handoff)
- Voice: [LiveKit](https://docs.moss.dev/docs/integrations/livekit), [Pipecat](https://docs.moss.dev/docs/integrations/pipecat), [VAPI](https://docs.moss.dev/docs/integrations/vapi)
- Agents: [LangChain](https://docs.moss.dev/docs/integrations/langchain), [Vercel AI SDK](https://docs.moss.dev/docs/integrations/vercel-ai-sdk), [MCP Server](https://docs.moss.dev/docs/integrations/mcp-server)
- [Hybrid Search](https://docs.moss.dev/docs/integrate/hybrid-search) · [Metadata Filtering](https://docs.moss.dev/docs/integrate/metadata-filtering) · [Multi-Index Search](https://docs.moss.dev/docs/integrate/multi-index-search)

SDKs: JavaScript (Node), Python, Swift, Elixir, C, browser/WASM.

## Hackathon pattern

**History-aware voice intake:** Deepgram (or LiveKit) for speech → each turn Moss queries (long-term patient/education index + session transcript) → LLM reply → chart to Medplum FHIR. Keep retrieval in-process so voice latency stays under control.
