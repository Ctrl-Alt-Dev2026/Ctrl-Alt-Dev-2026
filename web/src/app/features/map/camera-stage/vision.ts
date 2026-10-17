import type { ObjectDetection } from '@tensorflow-models/coco-ssd';

// In-browser analysis of a camera frame: object detection (COCO-SSD, a single-shot detector like YOLO),
// image brightness, and two simple rules that raise signals for an operator to check.
// Nothing here is trained or validated on real accidents: every signal is "de verificat".

export interface Detection {
  label: string; // COCO class, e.g. 'car', 'person'
  score: number;
  box: [number, number, number, number]; // x, y, w, h in video pixels
}

export const VEHICLES = new Set(['car', 'truck', 'bus', 'motorcycle', 'bicycle']);
export const LABEL_RO: Record<string, string> = {
  car: 'autoturism',
  truck: 'camion',
  bus: 'autobuz',
  motorcycle: 'motocicletă',
  bicycle: 'bicicletă',
  person: 'persoană',
};

// ---------- Detector (lazy: TF.js + model weights load only when a camera is analysed) ----------

let detector: Promise<ObjectDetection> | null = null;

export function loadDetector(): Promise<ObjectDetection> {
  detector ??= (async () => {
    const tf = await import('@tensorflow/tfjs-core');
    // COCO-SSD runs non-max suppression on the CPU backend, the rest on WebGL.
    await Promise.all([import('@tensorflow/tfjs-backend-cpu'), import('@tensorflow/tfjs-backend-webgl')]);
    await tf.setBackend('webgl');
    await tf.ready();
    const coco = await import('@tensorflow-models/coco-ssd');
    return coco.load({ base: 'mobilenet_v2' });
  })().catch((e) => {
    detector = null; // allow a retry
    throw e;
  });
  return detector;
}

// Wide city shots have small, distant cars and the model sees a 300 px image, so the frame is cut into
// 3×2 overlapping tiles. A whole-frame pass only added huge false boxes, so there is none.
const COLS = 3;
const ROWS = 2;
const OVERLAP = 0.12;
const MAX_BOX_SHARE = 0.2; // of the frame area: bigger boxes are model noise in a street-wide shot
const tileCanvas = document.createElement('canvas');

export async function detect(model: ObjectDetection, video: HTMLVideoElement): Promise<Detection[]> {
  const vw = video.videoWidth;
  const vh = video.videoHeight;
  const sw = vw / COLS + vw * OVERLAP;
  const sh = vh / ROWS + vh * OVERLAP;
  tileCanvas.width = Math.round(Math.min(sw, 640));
  tileCanvas.height = Math.round((tileCanvas.width * sh) / sw);
  const ctx = tileCanvas.getContext('2d')!;
  const k = sw / tileCanvas.width;
  const all: Detection[] = [];
  for (let r = 0; r < ROWS; r++) {
    for (let c = 0; c < COLS; c++) {
      const sx = Math.min(vw - sw, (c * vw) / COLS - (vw * OVERLAP) / 2);
      const sy = Math.min(vh - sh, (r * vh) / ROWS - (vh * OVERLAP) / 2);
      const ox = Math.max(0, sx);
      const oy = Math.max(0, sy);
      ctx.drawImage(video, ox, oy, sw, sh, 0, 0, tileCanvas.width, tileCanvas.height);
      for (const d of await model.detect(tileCanvas, 40, 0.4)) {
        if (d.class !== 'person' && !VEHICLES.has(d.class)) continue;
        const [x, y, w, h] = d.bbox;
        const box: Detection['box'] = [ox + x * k, oy + y * k, w * k, h * k];
        if (area(box) <= MAX_BOX_SHARE * vw * vh) all.push({ label: d.class, score: d.score, box });
      }
    }
  }
  return merge(all);
}

// Drops duplicates from overlapping tiles: same group, IoU > 0.45 or mostly inside a stronger box.
function merge(dets: Detection[]): Detection[] {
  const kept: Detection[] = [];
  const group = (l: string) => (l === 'person' ? 'p' : 'v');
  for (const d of dets.sort((a, b) => b.score - a.score)) {
    const dup = kept.some(
      (k) => group(k.label) === group(d.label) && (iou(k.box, d.box) > 0.45 || intersection(k.box, d.box) / area(d.box) > 0.7),
    );
    if (!dup) kept.push(d);
  }
  return kept;
}

// ---------- Lighting ----------

export const GRID_COLS = 16;
export const GRID_ROWS = 9;
const CELL_PX = 10;
// Mean luma (0–255) below which a cell counts as dark, and thresholds for the whole frame.
export const DARK_CELL = 35;
const LEVEL_POOR = 55;
const LEVEL_FAIR = 100;

export type LightLevel = 'slabă' | 'medie' | 'bună';

export interface LightReport {
  mean: number; // 0–255
  darkShare: number; // 0–1, share of cells under DARK_CELL
  cells: number[]; // row-major mean luma per cell
  level: LightLevel;
}

// Brightness of the picture (depends on camera exposure), not lux on the street.
export function measureLight(video: HTMLVideoElement, scratch: HTMLCanvasElement): LightReport {
  const w = GRID_COLS * CELL_PX;
  const h = GRID_ROWS * CELL_PX;
  scratch.width = w;
  scratch.height = h;
  const ctx = scratch.getContext('2d', { willReadFrequently: true })!;
  ctx.drawImage(video, 0, 0, w, h);
  const px = ctx.getImageData(0, 0, w, h).data;
  const cells = new Array<number>(GRID_COLS * GRID_ROWS).fill(0);
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const i = (y * w + x) * 4;
      const luma = 0.2126 * px[i] + 0.7152 * px[i + 1] + 0.0722 * px[i + 2];
      cells[Math.floor(y / CELL_PX) * GRID_COLS + Math.floor(x / CELL_PX)] += luma;
    }
  }
  const per = CELL_PX * CELL_PX;
  for (let c = 0; c < cells.length; c++) cells[c] /= per;
  const mean = cells.reduce((s, v) => s + v, 0) / cells.length;
  const darkShare = cells.filter((v) => v < DARK_CELL).length / cells.length;
  const level: LightLevel = mean < LEVEL_POOR ? 'slabă' : mean < LEVEL_FAIR ? 'medie' : 'bună';
  return { mean, darkShare, cells, level };
}

// ---------- Tracking + signal rules ----------

export type SignalKind = 'contact' | 'blocaj' | 'iluminat';

export interface Signal {
  id: string;
  kind: SignalKind;
  title: string;
  detail: string;
  at: Date;
  boxes: Detection['box'][];
}

interface Track {
  id: number;
  label: string;
  box: Detection['box'];
  lastSeen: number;
  anchor: [number, number]; // centre where it stopped
  stillSince: number;
  movedOnce: boolean; // seen moving at least once (excludes cars parked since we started watching)
  lastMoved: number;
}

const MATCH_IOU = 0.3;
const TRACK_TTL_MS = 3000;
const MOVE_SHARE = 0.25; // of the box diagonal
const CONTACT_SHARE = 0.3; // of the person box covered by a vehicle box
const CONTACT_MS = 1500;
const STOP_MS = 120_000; // longer than a red light
const STOP_IOU = 0.15;
const COOLDOWN_MS = 60_000;
const LIGHT_DARK_SHARE = 0.4;
const LIGHT_COOLDOWN_MS = 10 * 60_000;

const centre = (b: Detection['box']): [number, number] => [b[0] + b[2] / 2, b[1] + b[3] / 2];
const area = (b: Detection['box']) => b[2] * b[3];

function intersection(a: Detection['box'], b: Detection['box']): number {
  const w = Math.min(a[0] + a[2], b[0] + b[2]) - Math.max(a[0], b[0]);
  const h = Math.min(a[1] + a[3], b[1] + b[3]) - Math.max(a[1], b[1]);
  return w > 0 && h > 0 ? w * h : 0;
}

function iou(a: Detection['box'], b: Detection['box']): number {
  const i = intersection(a, b);
  return i / (area(a) + area(b) - i || 1);
}

/**
 * Rules (deliberately simple, tuned on nothing):
 * - contact: a person box is ≥30% covered by a vehicle that moved in the last 2 s, for ≥1.5 s.
 * - blocaj: two vehicles that were seen moving stay stopped and overlapping for ≥2 min.
 * - iluminat: ≥40% of the frame is dark.
 * A 2D camera can't tell "in front of" from "touching", so most signals will be false; an operator decides.
 */
export class SignalRules {
  private tracks: Track[] = [];
  private nextId = 1;
  private contactSince = new Map<string, number>();
  private lastFired = new Map<string, number>();

  update(dets: Detection[], now: number): Signal[] {
    this.track(dets, now);
    const out: Signal[] = [];
    const vehicles = this.tracks.filter((t) => VEHICLES.has(t.label) && t.lastSeen === now);
    const people = this.tracks.filter((t) => t.label === 'person' && t.lastSeen === now);

    const seen = new Set<string>();
    for (const p of people) {
      for (const v of vehicles) {
        const key = `c${p.id}-${v.id}`;
        const covered = intersection(p.box, v.box) / area(p.box);
        if (covered < CONTACT_SHARE || now - v.lastMoved > 2000) continue;
        seen.add(key);
        const since = this.contactSince.get(key) ?? now;
        this.contactSince.set(key, since);
        if (now - since >= CONTACT_MS && this.fire(key, now, COOLDOWN_MS))
          out.push({
            id: `${key}-${now}`,
            kind: 'contact',
            title: 'Pieton foarte aproape de un vehicul în mișcare',
            detail: `${LABEL_RO[v.label] ?? v.label} și persoană suprapuse ${((now - since) / 1000).toFixed(1)} s`,
            at: new Date(),
            boxes: [p.box, v.box],
          });
      }
    }
    for (const k of this.contactSince.keys()) if (!seen.has(k)) this.contactSince.delete(k);

    for (let i = 0; i < vehicles.length; i++) {
      for (let j = i + 1; j < vehicles.length; j++) {
        const a = vehicles[i];
        const b = vehicles[j];
        if (!a.movedOnce || !b.movedOnce || iou(a.box, b.box) < STOP_IOU) continue;
        const still = now - Math.max(a.stillSince, b.stillSince);
        const key = `b${Math.min(a.id, b.id)}-${Math.max(a.id, b.id)}`;
        if (still >= STOP_MS && this.fire(key, now, Infinity))
          out.push({
            id: `${key}-${now}`,
            kind: 'blocaj',
            title: 'Vehicule oprite în contact',
            detail: `două vehicule care circulau stau suprapuse de ${Math.round(still / 60000)} min`,
            at: new Date(),
            boxes: [a.box, b.box],
          });
      }
    }
    return out;
  }

  light(report: LightReport, now: number): Signal | null {
    if (report.darkShare < LIGHT_DARK_SHARE || !this.fire('light', now, LIGHT_COOLDOWN_MS)) return null;
    return {
      id: `light-${now}`,
      kind: 'iluminat',
      title: 'Iluminare slabă în imagine',
      detail: `${Math.round(report.darkShare * 100)}% din cadru sub pragul de întuneric (luminozitate medie ${Math.round(report.mean)}/255)`,
      at: new Date(),
      boxes: [],
    };
  }

  private fire(key: string, now: number, cooldown: number): boolean {
    const last = this.lastFired.get(key);
    if (last !== undefined && now - last < cooldown) return false;
    this.lastFired.set(key, now);
    return true;
  }

  // Greedy IoU matching, same class group; tracks survive short detection gaps.
  private track(dets: Detection[], now: number): void {
    const free = new Set(this.tracks);
    for (const d of [...dets].sort((a, b) => b.score - a.score)) {
      const group = (l: string) => (l === 'person' ? 'p' : 'v');
      let best: Track | null = null;
      let bestIou = MATCH_IOU;
      for (const t of free) {
        if (group(t.label) !== group(d.label)) continue;
        const o = iou(t.box, d.box);
        if (o > bestIou) {
          best = t;
          bestIou = o;
        }
      }
      if (best) {
        free.delete(best);
        best.box = d.box;
        best.label = d.label;
        best.lastSeen = now;
        const [cx, cy] = centre(d.box);
        const moved = Math.hypot(cx - best.anchor[0], cy - best.anchor[1]) > MOVE_SHARE * Math.hypot(d.box[2], d.box[3]);
        if (moved) {
          best.anchor = [cx, cy];
          best.stillSince = now;
          best.lastMoved = now;
          best.movedOnce = true;
        }
      } else {
        this.tracks.push({
          id: this.nextId++,
          label: d.label,
          box: d.box,
          lastSeen: now,
          anchor: centre(d.box),
          stillSince: now,
          movedOnce: false,
          lastMoved: -Infinity,
        });
      }
    }
    this.tracks = this.tracks.filter((t) => now - t.lastSeen <= TRACK_TTL_MS);
  }
}
