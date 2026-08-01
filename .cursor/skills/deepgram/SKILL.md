---
name: deepgram
description: >-
  Integrate Deepgram speech-to-text (Nova/Flux), text-to-speech (Aura), and
  Voice Agent APIs. Use when building voice intake, ambient charting, STT/TTS
  pipelines, browser voice agents, function calling mid-call, or when the user
  mentions Deepgram, Nova-3, Aura, Flux, or voice agents.
---

# Deepgram

Docs: [developers.deepgram.com](https://developers.deepgram.com/home.md) · Index: [llms.txt](https://developers.deepgram.com/llms.txt) · MCP: `https://developers.deepgram.com/_mcp/server`

Append `.md` to any docs URL for clean Markdown.

Hackathon: free signup includes **$200** credit ([console](https://console.deepgram.com/signup?jump=keys)). Startup Program scales credits after the event.

## Agent instructions

1. Prefer **Voice Agent API** for end-to-end listen → think → speak over one WebSocket when building patient intake / check-in.
2. For custom pipelines (Moss retrieval, Medplum writes, Stedi eligibility): use **function calling** mid-conversation, or cascade Nova/Flux STT + your LLM + Aura TTS.
3. Chart from `ConversationText` (user + agent turns) into Medplum FHIR — do not invent transcripts.
4. On `UserStartedSpeaking`, stop playback immediately (barge-in).
5. Keep `DEEPGRAM_API_KEY` server-side; use [token-based auth](https://developers.deepgram.com/guides/fundamentals/token-based-authentication.md) for browsers (short-lived JWT).
6. Default models: STT `nova-3`, TTS `aura-2-thalia-en` (or current Aura-2 voice); consider Flux for conversational EOT when optimizing turn-taking.

## Auth & first request

```bash
export DEEPGRAM_API_KEY="your_api_key"
```

Header: `Authorization: Token YOUR_DEEPGRAM_API_KEY`

```bash
curl --request POST \
  --header "Authorization: Token $DEEPGRAM_API_KEY" \
  --header "Content-Type: application/json" \
  --data '{"url":"https://static.deepgram.com/examples/interview_speech-analytics.wav"}' \
  --url 'https://api.deepgram.com/v1/listen?model=nova-3&smart_format=true'
```

Playground (no code): [playground.deepgram.com](https://playground.deepgram.com/?smart_format=true&language=en&model=nova-3)

## Install SDKs

```bash
npm install @deepgram/sdk          # Node >= 14
pip install deepgram-sdk           # Python >= 3.10
```

Browser agent packages: `@deepgram/agents`, `@deepgram/react`, `@deepgram/ui` — see [Browser Agent SDK](https://developers.deepgram.com/docs/browser-agent-overview.md).

## Product map

| Product | Use | Entry |
|---------|-----|--------|
| **Voice Agent** | Full duplex STT + LLM + TTS on one WS | [Getting started](https://developers.deepgram.com/docs/voice-agent.md) |
| **Listen (STT)** | Pre-recorded or streaming transcription | [Pre-recorded](https://developers.deepgram.com/docs/pre-recorded-audio.md), [Streaming](https://developers.deepgram.com/docs/live-streaming-audio.md) |
| **Speak (TTS)** | Aura REST or streaming WebSocket | [TTS REST](https://developers.deepgram.com/docs/text-to-speech.md), [TTS WS](https://developers.deepgram.com/docs/tts-websocket.md) |
| **Flux** | Conversational STT / turn-taking for agents | [Flux agent](https://developers.deepgram.com/docs/flux/agent.md) |

## Voice Agent (preferred for hack)

Endpoint: `wss://agent.deepgram.com/v1/agent/converse`  
EU: `wss://api.eu.deepgram.com/v1/agent/converse` · AU: `wss://api.au.deepgram.com/v1/agent/converse`

Flow:

1. Open WebSocket (SDK or client)
2. Send `Settings` (audio + listen / think / speak)
3. Wait for `SettingsApplied`
4. Stream PCM audio; handle events
5. Optionally inject text / function-call results

### Minimal JS settings shape

```js
connection.sendSettings({
  type: "Settings",
  audio: {
    input: { encoding: "linear16", sample_rate: 24000 },
    output: { encoding: "linear16", sample_rate: 16000, container: "wav" },
  },
  agent: {
    language: "en",
    listen: { provider: { type: "deepgram", model: "nova-3" } },
    think: {
      provider: { type: "open_ai", model: "gpt-4o-mini" },
      prompt: "You are a clinical intake assistant. Be concise.",
    },
    speak: { provider: { type: "deepgram", model: "aura-2-thalia-en" } },
    greeting: "Hi — I'm here to help you check in before your visit.",
  },
});
```

Tutorials: [JS](https://developers.deepgram.com/docs/build-a-voice-agent-javascript.md) · [Python](https://developers.deepgram.com/docs/build-a-voice-agent-python.md) · [Configure](https://developers.deepgram.com/docs/configure-voice-agent.md)

### Key server events

| Event | Action |
|-------|--------|
| `Welcome` | Send `Settings` |
| `SettingsApplied` | Start streaming mic/media |
| `UserStartedSpeaking` | Stop agent audio (barge-in) |
| `ConversationText` | Persist turn (chart / UI) |
| `AgentThinking` | Optional UI state |
| binary audio | Play agent speech |
| `AgentAudioDone` | Turn complete |
| Function call request | Run tool → send function response |

Message flow: [voice-agent-message-flow](https://developers.deepgram.com/docs/voice-agent-message-flow.md)  
Function calling: [voice-agents-function-calling](https://developers.deepgram.com/docs/voice-agents-function-calling.md)

Usage billing for Agent: based on **WebSocket connection time**.

## Hackathon demos / templates

| Demo | Repo |
|------|------|
| Basic Voice Agent | [deepgram-voice-agent-demo](https://github.com/deepgram-devs/deepgram-voice-agent-demo) |
| **Medical assistant** | [voice-agent-medical-assistant-demo](https://github.com/deepgram-devs/voice-agent-medical-assistant-demo) |
| Function calling (Flask) | [flask-agent-function-calling-demo](https://github.com/deepgram-devs/flask-agent-function-calling-demo) |
| LiveKit + Deepgram | [docs](https://developers.deepgram.com/docs/build-voice-agent-with-livekit-and-deepgram.md) |
| Pipecat + Deepgram | [docs](https://developers.deepgram.com/docs/build-voice-agent-with-pipecat-and-deepgram.md) |

Agent Playground: [playground.deepgram.com/?endpoint=agent](https://playground.deepgram.com/?endpoint=agent)

## Integrate with other sponsors

- **Moss** — ambient retrieval each turn (session + long-term index); or tool that queries Moss before the LLM answers
- **Medplum** — on `ConversationText` / end-of-intake, write Encounter + Composition / DocumentReference
- **Stedi** — function call `checkEligibility` using test API key + mock fixtures (no real PHI)

## Prompting tip

Keep system prompts short and turn-taking friendly. Guide: [Prompting Voice Agents](https://developers.deepgram.com/docs/prompting-voice-agents.md). For clinical intake: confirm identity lightly, collect chief complaint, meds/allergies, insurance questions → hand off structured summary to chart + optional Stedi check.
