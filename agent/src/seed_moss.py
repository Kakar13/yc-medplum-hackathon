"""Seed Moss index from data/sample_history.json (or dry-run in mock)."""

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
    console.print(f"mode={settings.agent_mode} index={settings.moss_index_name}")

    moss = MossService(settings)
    if settings.use_mock or not settings.moss_project_id:
        console.print("[yellow]Mock / missing Moss keys — listing docs only[/yellow]")
        for d in docs:
            console.print(f"  • {d['id']}: {d['text'][:80]}...")
        return

    await moss.ensure_index()
    # Verify
    sample = await moss.search_text("asthma inhaler", top_k=2)
    console.print("[green]Moss index ready. Sample query:[/green]")
    console.print(sample)


if __name__ == "__main__":
    asyncio.run(main())
