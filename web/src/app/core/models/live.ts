import { Accident, CrossingCollection, Hotspot, Manifest, Measure } from './contract';
import { StreetCollection } from './streets';

// GET /api/v1/live/dataset: the newest dataset collected by the server (isu/, every 30 minutes).
export interface LiveDataset {
  built_at: string;
  manifest: Manifest;
  accidents: Accident[];
  hotspots: Hotspot[];
  crossings: CrossingCollection;
  measures: Measure[];
  streets: StreetCollection;
}

export interface LiveRun {
  id: number;
  started_at: string;
  finished_at: string | null;
  status: 'running' | 'ok' | 'error';
  detail: Record<string, unknown> | null;
}

// GET /api/v1/live/status: cheap, polled to know when a newer dataset exists.
export interface LiveStatus {
  colectare_automata: boolean;
  interval_minute: number;
  construit_la: string | null;
  ruleaza: boolean;
  urmatoarea_rulare: string | null;
  ultima_rulare: LiveRun | null;
}
