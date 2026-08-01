/**
 * Browser half of the voice loop: capture, stream, play, and cut off cleanly on barge-in.
 *
 * Latency decisions worth knowing about, since they are the difference between a demo that
 * feels alive and one that feels like a walkie-talkie:
 *
 * - Capture runs in an AudioWorklet, not a ScriptProcessor. React re-rendering a pane cannot
 *   stall the audio thread, so mic frames keep flowing while the UI updates.
 * - The capture AudioContext is opened at 16 kHz so the browser resamples in native code and we
 *   never write a resampler in JS. If a browser refuses that rate we decimate as a fallback.
 * - Frames are 20 ms. Smaller means more messages for no perceptual gain; larger adds delay
 *   before the endpointer can even see that speech stopped.
 * - Playback appends raw PCM straight into WebAudio. The agent socket sends headerless linear16
 *   precisely so there is no decode step in the path.
 */

const CAPTURE_RATE = 16000;
const PLAYBACK_RATE = 24000;
const FRAME_SAMPLES = 320; // 20 ms at 16 kHz

// Worklet source is inlined as a Blob: it needs to ship with the bundle, and a separate public/
// file is one more thing that can 404 in a deployment.
const WORKLET_SOURCE = `
class CaptureProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._buf = new Float32Array(${FRAME_SAMPLES});
    this._n = 0;
  }
  process(inputs) {
    const ch = inputs[0] && inputs[0][0];
    if (!ch) return true;
    for (let i = 0; i < ch.length; i++) {
      this._buf[this._n++] = ch[i];
      if (this._n === ${FRAME_SAMPLES}) {
        const pcm = new Int16Array(${FRAME_SAMPLES});
        let peak = 0;
        for (let j = 0; j < ${FRAME_SAMPLES}; j++) {
          const s = Math.max(-1, Math.min(1, this._buf[j]));
          pcm[j] = s < 0 ? s * 0x8000 : s * 0x7fff;
          const a = s < 0 ? -s : s;
          if (a > peak) peak = a;
        }
        this.port.postMessage({ pcm: pcm.buffer, peak }, [pcm.buffer]);
        this._n = 0;
      }
    }
    return true;
  }
}
registerProcessor('capture-processor', CaptureProcessor);
`;

export type VoiceState = 'idle' | 'connecting' | 'listening' | 'thinking' | 'speaking';

export interface ToolCallEvent {
  name: string;
  arguments: Record<string, unknown>;
  denied: boolean;
  ms: number;
  preview: string;
}

export interface LatencySummary {
  turns: number;
  last_ms?: number;
  median_ms?: number;
  best_ms?: number;
}

export interface VoiceHandlers {
  onState?: (s: VoiceState) => void;
  onTranscript?: (role: 'user' | 'assistant', text: string) => void;
  onToolCall?: (t: ToolCallEvent) => void;
  onLatency?: (firstAudioMs: number, summary: LatencySummary) => void;
  onBound?: (info: Record<string, unknown>) => void;
  onReady?: (info: Record<string, unknown>) => void;
  onLevel?: (peak: number) => void;
  onError?: (message: string) => void;
  onNotice?: (message: string) => void;
  onClosed?: () => void;
}

/** Schedules incoming PCM back-to-back and can drop everything instantly for barge-in. */
class PcmPlayer {
  private ctx: AudioContext | null = null;
  private playAt = 0;
  private live = new Set<AudioBufferSourceNode>();

  async resume(): Promise<void> {
    if (!this.ctx) {
      this.ctx = new AudioContext({ sampleRate: PLAYBACK_RATE });
    }
    if (this.ctx.state === 'suspended') await this.ctx.resume();
  }

  enqueue(bytes: ArrayBuffer): void {
    if (!this.ctx) return;
    const pcm = new Int16Array(bytes);
    if (!pcm.length) return;

    const buffer = this.ctx.createBuffer(1, pcm.length, PLAYBACK_RATE);
    const channel = buffer.getChannelData(0);
    for (let i = 0; i < pcm.length; i++) channel[i] = pcm[i] / 0x8000;

    const src = this.ctx.createBufferSource();
    src.buffer = buffer;
    src.connect(this.ctx.destination);

    // A small floor keeps the first chunk from being scheduled in the past, which some browsers
    // render as a click. Beyond that we chain each chunk to the end of the last.
    const now = this.ctx.currentTime;
    this.playAt = Math.max(this.playAt, now + 0.02);
    src.start(this.playAt);
    this.playAt += buffer.duration;

    this.live.add(src);
    src.onended = () => this.live.delete(src);
  }

  /** Barge-in. The patient talking over the agent must win, immediately. */
  flush(): void {
    for (const src of this.live) {
      try {
        src.stop();
      } catch {
        /* already finished */
      }
    }
    this.live.clear();
    this.playAt = this.ctx ? this.ctx.currentTime : 0;
  }

  async close(): Promise<void> {
    this.flush();
    if (this.ctx) {
      await this.ctx.close().catch(() => undefined);
      this.ctx = null;
    }
  }
}

export class VoiceClient {
  private ws: WebSocket | null = null;
  private captureCtx: AudioContext | null = null;
  private stream: MediaStream | null = null;
  private node: AudioWorkletNode | null = null;
  private player = new PcmPlayer();
  private muted = false;
  private closing = false;

  constructor(private url: string, private handlers: VoiceHandlers = {}) {}

  get connected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  async start(): Promise<void> {
    this.closing = false;
    this.handlers.onState?.('connecting');

    // Playback context must be created during the user gesture that started the call, or
    // autoplay policy leaves it suspended and the agent is silent with no error.
    await this.player.resume();
    await this.openSocket();
    await this.openMic();
    this.handlers.onState?.('listening');
  }

  private openSocket(): Promise<void> {
    return new Promise((resolve, reject) => {
      const ws = new WebSocket(this.url);
      ws.binaryType = 'arraybuffer';
      this.ws = ws;

      ws.onopen = () => resolve();
      ws.onerror = () => reject(new Error('Could not reach the voice service'));
      ws.onclose = () => {
        if (!this.closing) this.handlers.onError?.('Voice connection closed');
        this.handlers.onClosed?.();
      };
      ws.onmessage = (evt) => {
        if (evt.data instanceof ArrayBuffer) {
          this.player.enqueue(evt.data);
          return;
        }
        let msg: Record<string, unknown>;
        try {
          msg = JSON.parse(evt.data as string);
        } catch {
          return;
        }
        this.dispatch(msg);
      };
    });
  }

  private dispatch(msg: Record<string, unknown>): void {
    switch (msg.type) {
      case 'Bound':
        this.handlers.onBound?.(msg);
        break;
      case 'Ready':
        this.handlers.onReady?.(msg);
        break;
      case 'Transcript': {
        const role = msg.role === 'user' ? 'user' : 'assistant';
        this.handlers.onTranscript?.(role, String(msg.text ?? ''));
        break;
      }
      case 'State':
        this.handlers.onState?.(msg.value as VoiceState);
        break;
      case 'BargeIn':
        this.player.flush();
        this.handlers.onState?.('listening');
        break;
      case 'ToolCall':
        this.handlers.onToolCall?.(msg as unknown as ToolCallEvent);
        break;
      case 'Latency':
        this.handlers.onLatency?.(
          Number(msg.first_audio_ms ?? 0),
          (msg.summary ?? { turns: 0 }) as LatencySummary,
        );
        break;
      case 'Notice':
        this.handlers.onNotice?.(String(msg.message ?? ''));
        break;
      case 'Error':
        this.handlers.onError?.(String(msg.message ?? 'Voice error'));
        break;
      default:
        break;
    }
  }

  private async openMic(): Promise<void> {
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        // Browser-native cleanup is better than anything we would bolt on, and the agent's own
        // audio leaking back into the mic would trigger endless false barge-ins.
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    });

    let ctx: AudioContext;
    try {
      ctx = new AudioContext({ sampleRate: CAPTURE_RATE });
    } catch {
      ctx = new AudioContext();
    }
    this.captureCtx = ctx;

    const blob = new Blob([WORKLET_SOURCE], { type: 'application/javascript' });
    const workletUrl = URL.createObjectURL(blob);
    try {
      await ctx.audioWorklet.addModule(workletUrl);
    } finally {
      URL.revokeObjectURL(workletUrl);
    }

    const source = ctx.createMediaStreamSource(this.stream);
    const node = new AudioWorkletNode(ctx, 'capture-processor');
    this.node = node;

    // Decimation factor for browsers that would not honour a 16 kHz context.
    const ratio = Math.max(1, Math.round(ctx.sampleRate / CAPTURE_RATE));

    node.port.onmessage = (evt) => {
      const { pcm, peak } = evt.data as { pcm: ArrayBuffer; peak: number };
      this.handlers.onLevel?.(peak);
      if (this.muted || !this.connected) return;
      this.ws!.send(ratio === 1 ? pcm : decimate(pcm, ratio));
    };

    source.connect(node);
    // Worklets need a sink to be pulled, but routing mic audio to the speakers would echo, so
    // terminate the graph in a silent gain node.
    const sink = ctx.createGain();
    sink.gain.value = 0;
    node.connect(sink);
    sink.connect(ctx.destination);
  }

  /** Type instead of talk — accessibility, and a reliable path on a noisy demo floor. */
  say(text: string): void {
    if (!this.connected || !text.trim()) return;
    this.ws!.send(JSON.stringify({ type: 'InjectUserMessage', content: text }));
  }

  setMuted(muted: boolean): void {
    this.muted = muted;
    if (muted) this.player.flush();
  }

  async stop(): Promise<void> {
    this.closing = true;
    if (this.connected) {
      try {
        this.ws!.send(JSON.stringify({ type: 'Stop' }));
      } catch {
        /* socket already gone */
      }
    }
    this.node?.port.close();
    this.node?.disconnect();
    this.stream?.getTracks().forEach((t) => t.stop());
    if (this.captureCtx) await this.captureCtx.close().catch(() => undefined);
    await this.player.close();
    this.ws?.close();
    this.ws = null;
    this.captureCtx = null;
    this.node = null;
    this.stream = null;
    this.handlers.onState?.('idle');
  }
}

function decimate(buf: ArrayBuffer, ratio: number): ArrayBuffer {
  const input = new Int16Array(buf);
  const out = new Int16Array(Math.floor(input.length / ratio));
  for (let i = 0; i < out.length; i++) out[i] = input[i * ratio];
  return out.buffer;
}

export function voiceUrl(apiBase: string): string {
  const base = apiBase.replace(/\/$/, '');
  const url = base.startsWith('http')
    ? base.replace(/^http/, 'ws')
    : `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}${base}`;
  return `${url}/voice/live`;
}
