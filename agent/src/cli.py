"""CLI entrypoint: text voice loop backed by LangGraph + Moss + Medplum."""

from __future__ import annotations

import asyncio
import uuid

import typer
from rich.console import Console

from .config import get_settings
from .graph import build_graph, run_turn
from .voice_deepgram import run_text_session, smoke_deepgram_key

app = typer.Typer(add_completion=False)
console = Console()

DEFAULT_WEARABLE = (
    "Resting HR elevated to 92 bpm overnight (baseline 62-68); "
    "recovery score 28 (baseline 55-70) for 2 nights. Suspected asthma-related stress."
)


@app.command()
def chat(
    wearable: str = typer.Option(DEFAULT_WEARABLE, help="Wearable alert context"),
    thread: str = typer.Option("", help="LangGraph thread id"),
):
    """Interactive text session (Deepgram optional later)."""

    async def _main():
        settings = get_settings()
        console.print(f"[dim]AGENT_MODE={settings.agent_mode} model={settings.openai_model}[/dim]")
        agent, _moss, medplum = build_graph()
        tid = thread or str(uuid.uuid4())

        async def turn(user_text: str, ctx: str | None = None):
            return await run_turn(agent, tid, user_text, wearable_context=ctx)

        async def turn_fn(user_text: str):
            return await turn(user_text, None)

        # First message includes wearable via wrapper in run_text_session
        first = True

        async def wrapped(user_text: str):
            nonlocal first
            ctx = wearable if first else None
            first = False
            return await turn(user_text, ctx)

        await run_text_session(wrapped, wearable_context=wearable)
        if settings.use_mock:
            console.print("\n[bold]Mock Medplum store[/bold]")
            console.print(medplum.dump_mock())

    asyncio.run(_main())


@app.command()
def doctor():
    """Smoke-check integrations (keys, Deepgram projects)."""

    async def _main():
        from .stedi_client import StediService

        settings = get_settings()
        console.print(f"mode={settings.agent_mode}")
        console.print(f"openai_key_set={bool(settings.openai_api_key)}")
        console.print(f"medplum_client_set={bool(settings.medplum_client_id)}")
        console.print(f"moss_set={bool(settings.moss_project_id)}")
        console.print(f"stedi_key_set={bool(settings.stedi_api_key)}")
        console.print(f"open_wearables_key_set={bool(settings.open_wearables_api_key)}")
        console.print(await smoke_deepgram_key())
        agent, moss, medplum = build_graph()
        patient = medplum.ensure_demo_patient()
        console.print(f"demo_patient={patient.get('id')}")
        hits = await moss.search_text("asthma inhaler flare")
        console.print(f"moss_sample_hits:\n{hits[:500]}")
        console.print(await StediService(settings).check_text("urgent telehealth"))
        from .open_wearables import OpenWearablesService

        risk = await OpenWearablesService(settings).risk_snapshot()
        console.print(f"wearable_risk={risk['level']} triggered={risk['triggered']}")
        console.print(risk["context"])

    asyncio.run(_main())


@app.command()
def once(
    message: str = typer.Argument(..., help="Single patient utterance"),
    wearable: str = typer.Option(DEFAULT_WEARABLE),
):
    """One-shot turn (good for scripts / CI)."""

    async def _main():
        agent, _, _ = build_graph()
        out = await run_turn(agent, str(uuid.uuid4()), message, wearable_context=wearable)
        console.print(out["reply"])
        if out["handoff"]:
            console.print("[magenta]HANDOFF[/magenta]")

    asyncio.run(_main())


if __name__ == "__main__":
    app()
