import {
  afterNextRender,
  ChangeDetectionStrategy,
  Component,
  computed,
  DestroyRef,
  ElementRef,
  inject,
  input,
  output,
  signal,
  viewChild,
} from '@angular/core';
import type Hls from 'hls.js';
import { Camera } from '../../../core/models/camera';
import {
  DARK_CELL,
  detect,
  Detection,
  GRID_COLS,
  GRID_ROWS,
  LABEL_RO,
  LightReport,
  loadDetector,
  measureLight,
  Signal,
  SignalRules,
  VEHICLES,
} from './vision';

const DETECT_EVERY_MS = 600;
const LIGHT_EVERY_MS = 2000;
const MAX_SIGNALS = 20;

// Canvas colours mirror the tokens in styles.scss (canvas can't read CSS variables cheaply).
const C_VEHICLE = '#e8edf4';
const C_PERSON = '#ffb347';
const C_SIGNAL = '#e8414b';
const C_DARK = 'rgba(242, 200, 107, 0.85)';

type ModelState = 'off' | 'loading' | 'ready' | 'error';

interface ShownSignal extends Signal {
  thumb: string | null;
}

/**
 * Plays a camera's HLS stream in our own <video> so frames can be analysed in the browser:
 * COCO-SSD boxes, a dark-zone grid, and rule-based signals for an operator. Full screen keeps the overlay.
 */
@Component({
  selector: 'app-camera-stage',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './camera-stage.html',
  styleUrl: './camera-stage.scss',
  host: { '[class.full]': 'fullscreen()' },
})
export class CameraStage {
  readonly camera = input.required<Camera>();
  readonly streamUrl = input.required<string>();
  // The stream can't be played (network, CORS, codec): the viewer falls back to the provider's player.
  readonly failed = output<void>();

  private readonly hostEl = inject(ElementRef<HTMLElement>);
  private readonly video = viewChild.required<ElementRef<HTMLVideoElement>>('video');
  private readonly overlay = viewChild.required<ElementRef<HTMLCanvasElement>>('overlay');
  private readonly scratch = document.createElement('canvas');

  protected readonly playing = signal(false);
  protected readonly analysing = signal(true);
  protected readonly model = signal<ModelState>('off');
  protected readonly detections = signal<Detection[]>([]);
  protected readonly light = signal<LightReport | null>(null);
  protected readonly signals = signal<ShownSignal[]>([]);
  protected readonly fullscreen = signal(false);
  protected readonly roundMs = signal<number | null>(null);

  protected readonly vehicles = computed(() => this.detections().filter((d) => VEHICLES.has(d.label)).length);
  protected readonly people = computed(() => this.detections().filter((d) => d.label === 'person').length);
  protected readonly darkPct = computed(() => Math.round((this.light()?.darkShare ?? 0) * 100));

  private hls?: Hls;
  private rules = new SignalRules();
  private stopped = false;
  private lastLight = 0;
  private timer?: ReturnType<typeof setTimeout>;

  constructor() {
    afterNextRender(() => {
      this.startStream();
      this.loop();
    });
    const onFs = () => this.fullscreen.set(document.fullscreenElement === this.hostEl.nativeElement);
    document.addEventListener('fullscreenchange', onFs);

    inject(DestroyRef).onDestroy(() => {
      this.stopped = true;
      clearTimeout(this.timer);
      document.removeEventListener('fullscreenchange', onFs);
      if (this.fullscreen()) document.exitFullscreen().catch(() => undefined);
      this.hls?.destroy();
    });
  }

  protected toggleAnalysis(): void {
    this.analysing.update((v) => !v);
    if (!this.analysing()) {
      this.detections.set([]);
      this.draw();
    }
  }

  protected toggleFullscreen(): void {
    if (this.fullscreen()) document.exitFullscreen().catch(() => undefined);
    else this.hostEl.nativeElement.requestFullscreen().catch(() => undefined);
  }

  protected dismiss(id: string): void {
    this.signals.update((list) => list.filter((s) => s.id !== id));
  }

  protected retryModel(): void {
    this.model.set('off');
  }

  protected labelRo(l: string): string {
    return LABEL_RO[l] ?? l;
  }

  private async startStream(): Promise<void> {
    const video = this.video().nativeElement;
    video.addEventListener('playing', () => this.playing.set(true));
    video.addEventListener('waiting', () => this.playing.set(false));
    video.addEventListener('pause', () => this.playing.set(false));
    const url = this.streamUrl();
    try {
      const { default: HlsCtor } = await import('hls.js');
      if (this.stopped) return;
      if (HlsCtor.isSupported()) {
        const hls = new HlsCtor({ liveSyncDurationCount: 3 });
        this.hls = hls;
        hls.on(HlsCtor.Events.ERROR, (_e, data) => {
          if (data.fatal) this.failed.emit();
        });
        hls.loadSource(url);
        hls.attachMedia(video);
      } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
        video.src = url;
      } else {
        this.failed.emit();
        return;
      }
      await video.play();
    } catch {
      // Autoplay refusal is harmless (video is muted); anything else means no stream.
      if (!video.paused) return;
      video.play().catch(() => this.failed.emit());
    }
  }

  // One detection round at a time; never queues work if the model is slower than DETECT_EVERY_MS.
  private async loop(): Promise<void> {
    if (this.stopped) return;
    const started = performance.now();
    const video = this.video().nativeElement;
    const ready = video.readyState >= 2 && video.videoWidth > 0 && !video.paused;

    if (ready && this.analysing()) {
      try {
        if (this.model() === 'off') this.model.set('loading');
        if (this.model() !== 'error') {
          const model = await loadDetector();
          this.model.set('ready');
          const t = performance.now();
          const dets = await detect(model, video);
          this.roundMs.set(Math.round(performance.now() - t));
          if (this.stopped) return;
          const now = performance.now();
          this.detections.set(dets);
          const fresh = this.rules.update(dets, now);
          if (now - this.lastLight >= LIGHT_EVERY_MS) {
            this.lastLight = now;
            const report = this.measure(video);
            if (report) {
              this.light.set(report);
              const s = this.rules.light(report, now);
              if (s) fresh.push(s);
            }
          }
          if (fresh.length) this.push(fresh, video);
        }
      } catch {
        this.model.set('error');
      }
      this.draw();
    } else if (ready && started - this.lastLight >= LIGHT_EVERY_MS) {
      // Analysis paused: keep the lighting readout, skip detection.
      this.lastLight = started;
      const report = this.measure(video);
      if (report) this.light.set(report);
    }

    const wait = Math.max(0, DETECT_EVERY_MS - (performance.now() - started));
    this.timer = setTimeout(() => this.loop(), wait);
  }

  private measure(video: HTMLVideoElement): LightReport | null {
    try {
      return measureLight(video, this.scratch);
    } catch {
      return null; // a tainted canvas (no CORS) would throw here
    }
  }

  private push(fresh: Signal[], video: HTMLVideoElement): void {
    const shown = fresh.map((s) => ({ ...s, thumb: this.thumbnail(video, s) }));
    this.signals.update((list) => [...shown.reverse(), ...list].slice(0, MAX_SIGNALS));
  }

  // Frame at the moment of the signal, with the boxes that triggered it, for the operator.
  private thumbnail(video: HTMLVideoElement, s: Signal): string | null {
    try {
      const c = document.createElement('canvas');
      c.width = 320;
      c.height = Math.round((320 * video.videoHeight) / video.videoWidth);
      const ctx = c.getContext('2d')!;
      ctx.drawImage(video, 0, 0, c.width, c.height);
      const k = c.width / video.videoWidth;
      ctx.strokeStyle = C_SIGNAL;
      ctx.lineWidth = 2;
      for (const b of s.boxes) ctx.strokeRect(b[0] * k, b[1] * k, b[2] * k, b[3] * k);
      return c.toDataURL('image/jpeg', 0.75);
    } catch {
      return null;
    }
  }

  // Overlay canvas has the video's pixel size and the same object-fit, so boxes need no mapping.
  private draw(): void {
    const video = this.video().nativeElement;
    const canvas = this.overlay().nativeElement;
    if (!video.videoWidth) return;
    if (canvas.width !== video.videoWidth || canvas.height !== video.videoHeight) {
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
    }
    const ctx = canvas.getContext('2d')!;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const unit = canvas.width / 640;

    const light = this.light();
    if (light) {
      const cw = canvas.width / GRID_COLS;
      const ch = canvas.height / GRID_ROWS;
      ctx.strokeStyle = C_DARK;
      ctx.lineWidth = 1.5 * unit;
      ctx.setLineDash([4 * unit, 3 * unit]);
      light.cells.forEach((v, i) => {
        if (v >= DARK_CELL) return;
        const x = (i % GRID_COLS) * cw;
        const y = Math.floor(i / GRID_COLS) * ch;
        ctx.fillStyle = 'rgba(4, 7, 11, 0.35)';
        ctx.fillRect(x, y, cw, ch);
        ctx.strokeRect(x + 1, y + 1, cw - 2, ch - 2);
      });
      ctx.setLineDash([]);
    }

    if (!this.analysing()) return;
    ctx.font = `600 ${9 * unit}px Archivo, system-ui, sans-serif`;
    ctx.textBaseline = 'bottom';
    for (const d of this.detections()) {
      const [x, y, w, h] = d.box;
      const colour = d.label === 'person' ? C_PERSON : C_VEHICLE;
      ctx.strokeStyle = colour;
      ctx.lineWidth = 2 * unit;
      ctx.strokeRect(x, y, w, h);
      const text = `${this.labelRo(d.label)} ${Math.round(d.score * 100)}%`;
      const tw = ctx.measureText(text).width + 6 * unit;
      ctx.fillStyle = colour;
      ctx.fillRect(x - unit, y - 12 * unit, tw, 12 * unit);
      ctx.fillStyle = '#0b1017';
      ctx.fillText(text, x + 2 * unit, y - 2 * unit);
    }
    const recent = this.signals().find((s) => Date.now() - s.at.getTime() < 4000);
    if (recent) {
      ctx.strokeStyle = C_SIGNAL;
      ctx.lineWidth = 4 * unit;
      for (const b of recent.boxes) ctx.strokeRect(b[0] - 4 * unit, b[1] - 4 * unit, b[2] + 8 * unit, b[3] + 8 * unit);
    }
  }
}
