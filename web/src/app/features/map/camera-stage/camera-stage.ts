import {
  afterNextRender, ChangeDetectionStrategy, Component, computed, DestroyRef,
  ElementRef, inject, input, output, signal, viewChild,
} from '@angular/core';
import type Hls from 'hls.js';
import { VisionApi, VisionApiError } from '../../../core/api/vision-api';
import { Camera } from '../../../core/models/camera';
import { Box, Crosswalk, Detection, LightReport, Point, VisionSignal } from '../../../core/models/live-vision';
import { LABEL_RO, VEHICLES } from './vision';

const DETECT_EVERY_MS = 250;
const MAX_ANNOTATION_AGE_S = 1.5;
const MAX_SIGNALS = 20;
interface ShownSignal extends VisionSignal { at: Date; thumb: string | null }

// The server's anti-flicker rule (safecross/live_analytics.py): a weak detection is shown once it matches an object
// of the same label in the previous frame. Applied here only when the server instance had no history of this camera.
function sameObject(current: Detection, previous: Detection): boolean {
  if (current.label !== previous.label) return false;
  const [ax, ay, aw, ah] = current.box, [bx, by, bw, bh] = previous.box;
  const common = Math.max(0, Math.min(ax + aw, bx + bw) - Math.max(ax, bx)) * Math.max(0, Math.min(ay + ah, by + bh) - Math.max(ay, by));
  const iou = common / Math.max(1, aw * ah + bw * bh - common);
  const distance = Math.hypot(ax + aw / 2 - bx - bw / 2, ay + ah / 2 - by - bh / 2) / Math.max(8, Math.hypot(bw, bh));
  return iou >= .15 || distance < .65;
}

/** Continuous HLS playback, recent backend observations, and optional exact-frame inspection. */
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
  readonly failed = output<void>();
  private readonly api = inject(VisionApi);
  private readonly hostEl = inject(ElementRef<HTMLElement>);
  private readonly video = viewChild.required<ElementRef<HTMLVideoElement>>('video');
  private readonly overlay = viewChild.required<ElementRef<HTMLCanvasElement>>('overlay');
  private readonly scratch = document.createElement('canvas');
  private readonly analysedFrame = document.createElement('canvas');

  protected readonly playing = signal(false);
  protected readonly analysing = signal(true);
  protected readonly model = signal<'off' | 'loading' | 'ready' | 'error'>('off');
  protected readonly error = signal('');
  protected readonly detections = signal<Detection[]>([]);
  protected readonly light = signal<LightReport | null>(null);
  protected readonly signals = signal<ShownSignal[]>([]);
  protected readonly fullscreen = signal(false);
  protected readonly roundMs = signal<number | null>(null);
  protected readonly latencyMs = signal<number | null>(null);
  protected readonly enhanced = signal(false);
  protected readonly drawing = signal(false);
  protected readonly drawingKind = signal<'crosswalk' | 'detection'>('crosswalk');
  protected readonly detectionRegion = signal<Crosswalk | null>(null);
  protected readonly synchronized = signal(false);
  protected readonly annotationsFresh = signal(false);
  protected readonly points = signal<Point[]>([]);
  protected readonly crosswalks = signal<Crosswalk[]>([]);
  protected readonly vehicles = computed(() => this.detections().filter((d) => VEHICLES.has(d.label)).length);
  protected readonly people = computed(() => this.detections().filter((d) => d.label === 'person').length);
  protected readonly darkPct = computed(() => Math.round((this.light()?.darkShare ?? 0) * 100));

  private hls?: Hls;
  private stopped = false;
  private timer?: ReturnType<typeof setTimeout>;
  private annotationTimer?: ReturnType<typeof setTimeout>;
  private abort?: AbortController;
  private session: string | null = null;
  private generation = 0;
  private sequence = 0;
  private lastMediaTime = -1;
  private hasFrame = false;
  private activeSignalBoxes: Box[] = [];
  private previousRaw: Detection[] = [];
  private previousRawTime = -Infinity;

  constructor() {
    afterNextRender(() => {
      this.restoreCrosswalks();
      void this.startStream();
      void this.loop();
    });
    const onFs = () => this.fullscreen.set(document.fullscreenElement === this.hostEl.nativeElement);
    document.addEventListener('fullscreenchange', onFs);
    inject(DestroyRef).onDestroy(() => {
      this.stopped = true;
      clearTimeout(this.timer);
      clearTimeout(this.annotationTimer);
      this.resetSession();
      document.removeEventListener('fullscreenchange', onFs);
      if (this.fullscreen()) void document.exitFullscreen().catch(() => undefined);
      this.hls?.destroy();
    });
  }

  protected toggleAnalysis(): void {
    this.analysing.update((v) => !v);
    this.resetSession();
  }
  protected toggleFullscreen(): void {
    if (this.fullscreen()) void document.exitFullscreen().catch(() => undefined);
    else void this.hostEl.nativeElement.requestFullscreen().catch(() => undefined);
  }
  protected dismiss(id: string): void {
    this.signals.update((list) => list.filter((s) => s.id !== id));
  }
  protected retryModel(): void { this.resetSession(); }
  protected toggleSynchronized(): void {
    this.synchronized.update((value) => !value);
    this.draw();
  }
  protected toggleDrawing(kind: 'crosswalk' | 'detection' = 'crosswalk'): void {
    this.drawing.set(!this.drawing() || this.drawingKind() !== kind);
    this.drawingKind.set(kind);
    this.points.set([]);
    this.resetSession();
  }
  protected addPoint(event: MouseEvent): void {
    if (!this.drawing() || this.points().length >= 12) return;
    const video = this.video().nativeElement;
    if (!video.videoWidth) return;
    const rect = this.overlay().nativeElement.getBoundingClientRect();
    const scale = Math.min(rect.width / video.videoWidth, rect.height / video.videoHeight);
    const x = (event.clientX - rect.left - (rect.width - video.videoWidth * scale) / 2) / (video.videoWidth * scale);
    const y = (event.clientY - rect.top - (rect.height - video.videoHeight * scale) / 2) / (video.videoHeight * scale);
    if (x < 0 || x > 1 || y < 0 || y > 1) return;
    this.points.update((points) => [...points, [x, y]]);
    this.draw();
  }
  protected saveCrosswalk(): void {
    const polygon = this.points();
    if (polygon.length < 3 || (this.drawingKind() === 'crosswalk' && this.crosswalks().length >= 8)) return;
    const area = Math.abs(polygon.reduce((sum, [x, y], i) => {
      const next = polygon[(i + 1) % polygon.length];
      return sum + x * next[1] - next[0] * y;
    }, 0)) / 2;
    if (area < .0001) return;
    if (this.drawingKind() === 'detection') this.detectionRegion.set({ id: 'detection-zone', polygon });
    else this.crosswalks.update((list) => [...list, { id: crypto.randomUUID(), polygon }]);
    this.drawing.set(false);
    this.points.set([]);
    this.persistCrosswalks();
    this.resetSession();
  }
  protected clearCrosswalks(): void {
    this.crosswalks.set([]);
    this.points.set([]);
    this.drawing.set(false);
    this.persistCrosswalks();
    this.resetSession();
  }
  protected clearDetectionRegion(): void {
    this.detectionRegion.set(null);
    this.points.set([]);
    this.drawing.set(false);
    this.persistCrosswalks();
    this.resetSession();
  }
  private persistCrosswalks(): void {
    try {
      localStorage.setItem(`safeiasi-crosswalks:${this.camera().id}`, JSON.stringify(this.crosswalks()));
      localStorage.setItem(`safeiasi-detection-region:${this.camera().id}`, JSON.stringify(this.detectionRegion()));
    } catch { /* Storage is optional. */ }
  }
  private restoreCrosswalks(): void {
    try {
      const saved: unknown = JSON.parse(localStorage.getItem(`safeiasi-crosswalks:${this.camera().id}`) ?? '[]');
      if (Array.isArray(saved) && saved.length <= 8 && saved.every((r) =>
        typeof r?.id === 'string' && /^[a-zA-Z0-9_-]{1,60}$/.test(r.id) && Array.isArray(r.polygon)
        && r.polygon.length >= 3 && r.polygon.length <= 12 && r.polygon.every((p: unknown) =>
          Array.isArray(p) && p.length === 2 && p.every((v: unknown) => typeof v === 'number' && Number.isFinite(v) && v >= 0 && v <= 1)))) {
        this.crosswalks.set(saved as Crosswalk[]);
      }
      const region = JSON.parse(localStorage.getItem(`safeiasi-detection-region:${this.camera().id}`) ?? 'null');
      if (region?.id === 'detection-zone' && Array.isArray(region.polygon) && region.polygon.length >= 3 && region.polygon.length <= 12
        && region.polygon.every((p: unknown) => Array.isArray(p) && p.length === 2 && p.every((v: unknown) => typeof v === 'number' && Number.isFinite(v) && v >= 0 && v <= 1))) {
        this.detectionRegion.set(region as Crosswalk);
      }
    } catch { /* Ignore corrupt or unavailable local storage. */ }
  }
  private resetSession(): void {
    this.generation++;
    this.abort?.abort();
    if (this.session) this.api.close(this.session);
    this.session = null;
    this.lastMediaTime = -1;
    clearTimeout(this.annotationTimer);
    this.annotationsFresh.set(false);
    this.detections.set([]);
    this.light.set(null);
    this.model.set('off');
    this.error.set('');
    this.hasFrame = false;
    this.activeSignalBoxes = [];
    this.previousRaw = [];
    if (!this.stopped) this.draw();
  }

  private async startStream(): Promise<void> {
    const video = this.video().nativeElement;
    video.addEventListener('playing', () => this.playing.set(true));
    for (const name of ['waiting', 'pause', 'ended']) video.addEventListener(name, () => {
      this.playing.set(false);
      this.annotationsFresh.set(false);
      this.hasFrame = false;
      this.detections.set([]);
      this.draw();
    });
    video.addEventListener('error', () => this.failed.emit());
    try {
      const { default: HlsCtor } = await import('hls.js');
      if (this.stopped) return;
      if (HlsCtor.isSupported()) {
        const hls = new HlsCtor({ liveSyncDurationCount: 3 });
        this.hls = hls;
        hls.on(HlsCtor.Events.ERROR, (_e, data) => { if (data.fatal) this.failed.emit(); });
        hls.loadSource(this.streamUrl());
        hls.attachMedia(video);
      } else if (video.canPlayType('application/vnd.apple.mpegurl')) video.src = this.streamUrl();
      else { this.failed.emit(); return; }
      await video.play();
    } catch {
      if (!this.stopped && video.paused) void video.play().catch(() => this.failed.emit());
    }
  }

  // One captured frame and request at a time; no stale inference backlog.
  private async loop(): Promise<void> {
    if (this.stopped) return;
    const started = performance.now();
    const video = this.video().nativeElement;
    const generation = this.generation;
    if (!document.hidden && video.readyState >= 2 && !video.paused && video.videoWidth && this.analysing() && !this.drawing() && this.model() !== 'error') {
      let timeout: ReturnType<typeof setTimeout> | undefined;
      try {
        const abort = new AbortController();
        this.abort = abort;
        timeout = setTimeout(() => abort.abort(), 90_000);
        if (!this.session) {
          this.model.set('loading');
          const session = await this.api.open(this.camera().id, this.crosswalks(), abort.signal, this.detectionRegion());
          if (this.stopped || generation !== this.generation) { this.api.close(session); return; }
          this.session = session;
        }
        const mediaTime = video.currentTime;
        if (mediaTime < this.lastMediaTime) { this.resetSession(); return; }
        if (mediaTime === this.lastMediaTime) return;
        const t = performance.now();
        const captureWidth = this.detectionRegion() ? 1600 : 1280;
        const scale = Math.min(1, captureWidth / video.videoWidth, (captureWidth * 9 / 16) / video.videoHeight);
        this.scratch.width = Math.round(video.videoWidth * scale);
        this.scratch.height = Math.round(video.videoHeight * scale);
        this.scratch.getContext('2d')!.drawImage(video, 0, 0, this.scratch.width, this.scratch.height);
        const jpeg = await new Promise<Blob>((resolve, reject) => this.scratch.toBlob((blob) => blob ? resolve(blob) : reject(new Error('Cadrul camerei nu poate fi citit.')), 'image/jpeg', .85));
        if (abort.signal.aborted) return;
        const result = await this.api.frame(this.session, jpeg, this.sequence++, mediaTime, abort.signal);
        if (this.stopped || generation !== this.generation || !this.playing()) return;
        this.lastMediaTime = mediaTime;
        this.model.set('ready');
        this.roundMs.set(result.inference_ms);
        this.latencyMs.set(Math.round(performance.now() - t));
        this.enhanced.set(result.model.low_light_enhanced);
        const pending = result.pending ?? [];
        const confirmed = result.tracking_history === false && mediaTime - this.previousRawTime <= 2.5
          ? pending.filter((d) => this.previousRaw.some((p) => sameObject(d, p))) : [];
        this.previousRaw = [...result.detections, ...pending];
        this.previousRawTime = mediaTime;
        this.detections.set([...result.detections, ...confirmed]);
        this.light.set(result.light);
        this.activeSignalBoxes = result.signals.flatMap((s) => s.boxes);
        this.analysedFrame.width = this.scratch.width;
        this.analysedFrame.height = this.scratch.height;
        this.analysedFrame.getContext('2d')!.drawImage(this.scratch, 0, 0);
        clearTimeout(this.annotationTimer);
        const age = video.currentTime - mediaTime;
        this.annotationsFresh.set(age >= 0 && age < MAX_ANNOTATION_AGE_S);
        this.annotationTimer = setTimeout(() => {
          this.annotationsFresh.set(false);
          this.draw();
        }, Math.max(0, (MAX_ANNOTATION_AGE_S - age) * 1000));
        if (result.signals.length) {
          const fresh = result.signals.map((s) => ({ ...s, at: new Date(), thumb: this.thumbnail(s) }));
          this.signals.update((list) => [...fresh.reverse(), ...list].slice(0, MAX_SIGNALS));
        }
        this.hasFrame = true;
        this.draw();
      } catch (error) {
        if (this.stopped || generation !== this.generation) return;
        if (error instanceof VisionApiError && error.code === 'vision_busy') {
          // Another viewer is using the detector. Keep this session and try a fresh frame.
        } else if (error instanceof VisionApiError && ['vision_session_expired', 'stale_frame'].includes(error.code)) {
          this.resetSession();
        } else {
          this.model.set('error');
          this.error.set(error instanceof VisionApiError ? error.message : 'Analiza nu a răspuns sau cadrul nu poate fi citit. Verifică backend-ul Python și accesul CORS la cameră.');
        }
        this.hasFrame = false;
        this.annotationsFresh.set(false);
        this.detections.set([]);
        this.light.set(null);
        this.draw();
      } finally {
        clearTimeout(timeout);
        if (!this.stopped) this.timer = setTimeout(() => void this.loop(), Math.max(40, DETECT_EVERY_MS - (performance.now() - started)));
      }
      return;
    }
    this.timer = setTimeout(() => void this.loop(), DETECT_EVERY_MS);
  }

  private thumbnail(signal: VisionSignal): string {
    const canvas = document.createElement('canvas');
    canvas.width = 320;
    canvas.height = Math.round(320 * this.scratch.height / this.scratch.width);
    const ctx = canvas.getContext('2d')!;
    ctx.drawImage(this.scratch, 0, 0, canvas.width, canvas.height);
    const scale = canvas.width / this.scratch.width;
    ctx.strokeStyle = '#e8414b';
    ctx.lineWidth = 2;
    for (const [x, y, w, h] of signal.boxes) ctx.strokeRect(x * scale, y * scale, w * scale, h * scale);
    return canvas.toDataURL('image/jpeg', .75);
  }

  private draw(): void {
    if (this.stopped) return;
    const canvas = this.overlay().nativeElement;
    const video = this.video().nativeElement;
    if (!video.videoWidth) return;
    const width = this.hasFrame ? this.analysedFrame.width : video.videoWidth;
    const height = this.hasFrame ? this.analysedFrame.height : video.videoHeight;
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext('2d')!;
    // Default: continuous HLS video. Exact sampled-frame inspection remains available.
    if (this.hasFrame && this.analysing() && this.synchronized()) ctx.drawImage(this.analysedFrame, 0, 0);
    const unit = width / 640;
    ctx.font = `600 ${10 * unit}px Archivo, system-ui, sans-serif`;
    ctx.textBaseline = 'bottom';
    const polygon = (points: Point[], colour: string, fill: boolean) => {
      if (!points.length) return;
      ctx.beginPath();
      points.forEach(([x, y], i) => i ? ctx.lineTo(x * width, y * height) : ctx.moveTo(x * width, y * height));
      if (fill) ctx.closePath();
      ctx.strokeStyle = colour;
      ctx.lineWidth = 2 * unit;
      ctx.stroke();
      if (fill) { ctx.fillStyle = colour + '24'; ctx.fill(); }
      points.forEach(([x, y]) => { ctx.beginPath(); ctx.arc(x * width, y * height, 3 * unit, 0, Math.PI * 2); ctx.fillStyle = colour; ctx.fill(); });
    };
    for (const region of this.crosswalks()) {
      const report = this.light()?.crosswalks.find((r) => r.id === region.id);
      const colour = report?.low_light ? '#f2c86b' : '#8ed8ed';
      polygon(region.polygon, colour, true);
      const [x, y] = region.polygon[0];
      ctx.fillStyle = colour;
      ctx.fillText(report ? `Trecere · ${report.low_light ? 'lumină slabă' : 'vizibilitate'} · ${report.people} pers.` : 'Trecere marcată', x * width, Math.max(14 * unit, y * height - 3 * unit));
    }
    polygon(this.points(), '#8ed8ed', false);
    const region = this.detectionRegion();
    if (region) polygon(region.polygon, '#a5b4fc', true);
    if (!this.hasFrame || !this.analysing() || (!this.synchronized() && !this.annotationsFresh())) return;
    for (const d of this.detections()) {
      const [x, y, w, h] = d.box;
      const colour = d.label === 'person' ? '#ffb347' : d.label === 'tram' ? '#8ed8ed' : '#e8edf4';
      ctx.strokeStyle = colour;
      ctx.lineWidth = 2 * unit;
      ctx.strokeRect(x, y, w, h);
      const text = `${LABEL_RO[d.label] ?? d.label}${d.classification ? '?' : ''} #${d.track_id} ${Math.round(d.score * 100)}%`;
      const tw = ctx.measureText(text).width + 6 * unit;
      const top = Math.max(0, y - 14 * unit);
      ctx.fillStyle = colour;
      ctx.fillRect(x, top, tw, 14 * unit);
      ctx.fillStyle = '#0b1017';
      ctx.fillText(text, x + 2 * unit, top + 12 * unit);
    }
    if (this.activeSignalBoxes.length) {
      ctx.strokeStyle = '#e8414b';
      ctx.lineWidth = 4 * unit;
      for (const b of this.activeSignalBoxes) ctx.strokeRect(...b);
    }
  }
}
