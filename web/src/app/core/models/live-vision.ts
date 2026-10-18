export type Box = [number, number, number, number];
export type Point = [number, number];
export interface Detection {
  label: string; score: number; box: Box; track_id: number;
  classification?: 'open_vocabulary_proposal';
}
export interface Crosswalk { id: string; polygon: Point[] }
export interface CrosswalkLight extends Crosswalk {
  box: Box; median: number; darkShare: number; low_light: boolean; people: number;
}
export interface LightReport {
  mean: number; darkShare: number; cells: number[]; level: 'slabă' | 'medie' | 'bună'; crosswalks: CrosswalkLight[];
}
export interface VisionSignal {
  id: string; kind: 'incident' | 'blocaj' | 'iluminat'; title: string; detail: string;
  boxes: Box[]; status: 'needs_review';
}
export interface VisionFrame {
  sequence: number; media_time: number; width: number; height: number;
  detections: Detection[]; light: LightReport; signals: VisionSignal[];
  inference_ms: number; tracking_reset: boolean;
  /** Weak first observations, not shown yet. */
  pending: Detection[];
  /** False when the server instance had no previous frame of this camera (frames spread over instances). */
  tracking_history: boolean;
  model: { name: string; device: string; input_size: number; low_light_enhanced: boolean };
}
