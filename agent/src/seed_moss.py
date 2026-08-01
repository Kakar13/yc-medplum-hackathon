"""Seed Moss long-term index from data/sample_history.json.

Follows https://github.com/usemoss/moss best practices:
  create_index / add_docs(upsert=True) → load_index → query with hybrid alpha.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from rich.console import Console

from .config import get_settings
from .moss_retriever import SAMPLE_PATH, MossService

console = Console()


async def main() -> None:
    settings = get_settings()
    docs = json.loads(Path(SAMPLE_PATH).read_text())
    console.print(f"Loaded {len(docs)} docs from {SAMPLE_PATH}")
    console.print(f"index={settings.moss_index_name} keys={bool(settings.moss_project_id)}")

    moss = MossService(settings)
    if not moss.live:
        console.print("[yellow]No Moss keys — listing docs only (mock)[/yellow]")
        for d in docs:
            console.print(f"  • {d['id']}: {d['text'][:80]}...")
        return

    info = await moss.ensure_index()
    console.print(f"[green]Index ready:[/green] {info}")

    for query in (
        "eczema flare itch topical steroid",
        "asthma inhaler wheeze",
        "insurance coverage telehealth",
    ):
        # Protocol-only filter demo
        hits = await moss.search_text(query, top_k=2)
        console.print(f"\n[bold]query:[/bold] {query}")
        console.print(hits[:500])

    proto = await moss.search_text(
        "when to escalate rash", top_k=2, metadata_type="Protocol"
    )
    console.print("\n[bold]metadata filter type=Protocol[/bold]")
    console.print(proto[:500])


if __name__ == "__main__":
    asyncio.run(main())
