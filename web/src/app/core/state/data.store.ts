import { computed, inject, Injectable, signal } from '@angular/core';
import { forkJoin } from 'rxjs';
import { DataApi } from '../api/data-api';
import { Camera } from '../models/camera';
import { Accident, Crossing, Hotspot, Manifest, Measure } from '../models/contract';

export type LoadState = 'loading' | 'ready' | 'error';

// Shared app state. Loaded once; components read signals and never re-fetch.
@Injectable({ providedIn: 'root' })
export class DataStore {
  private readonly api = inject(DataApi);

  readonly state = signal<LoadState>('loading');
  readonly error = signal<string | null>(null);
  readonly manifest = signal<Manifest | null>(null);
  readonly accidents = signal<Accident[]>([]);
  readonly hotspots = signal<Hotspot[]>([]);
  readonly crossings = signal<Crossing[]>([]);
  readonly crossingPoints = signal<Map<string, [number, number]>>(new Map());
  readonly measures = signal<Measure[]>([]);
  readonly selectedId = signal<string | null>(null);
  // Live cameras load on their own: if they fail, the accident map still works.
  readonly cameras = signal<Camera[]>([]);
  readonly camerasError = signal<string | null>(null);
  readonly showCameras = signal(false);
  readonly selectedCameraId = signal<string | null>(null);
  readonly selectedCamera = computed(() => this.cameras().find((c) => c.id === this.selectedCameraId()) ?? null);
  // null = all participants; otherwise e.g. 'pieton', 'autoturism'.
  readonly participant = signal<string | null>(null);

  // The UI shows the ranking as given by Person 4; it only sorts, never rescores.
  readonly ranked = computed(() => [...this.hotspots()].sort((a, b) => b.scor - a.scor));
  readonly rankOf = computed(() => new Map(this.ranked().map((h, i) => [h.id, i + 1])));

  readonly participants = computed(() => [...new Set(this.accidents().flatMap((a) => a.participanti))].sort());
  private readonly matches = (a: Accident) => {
    const p = this.participant();
    return p === null || a.participanti.includes(p);
  };
  // Hotspots keep their given rank; the filter only hides those with no matching event.
  readonly visibleHotspots = computed(() =>
    this.ranked().filter((h) => h.event_ids.some((id) => {
      const a = this.accidentById().get(id);
      return !!a && this.matches(a);
    })),
  );
  readonly selected = computed(() => this.hotspots().find((h) => h.id === this.selectedId()) ?? null);
  readonly isSynthetic = computed(() => this.manifest()?.data_mode === 'synthetic');

  readonly accidentById = computed(() => new Map(this.accidents().map((a) => [a.event_id, a])));
  readonly measureById = computed(() => new Map(this.measures().map((m) => [m.id, m])));
  readonly crossingById = computed(() => new Map(this.crossings().map((c) => [c.id, c])));

  // Events drawn on the map: inside Iași with coordinates. Approximate ones are styled differently.
  readonly mappable = computed(() =>
    this.accidents().filter((a) => a.in_iasi !== false && a.lat !== null && a.lon !== null && this.matches(a)),
  );

  load(): void {
    this.state.set('loading');
    forkJoin({
      manifest: this.api.manifest(),
      accidents: this.api.accidents(),
      hotspots: this.api.hotspots(),
      crossings: this.api.crossings(),
      measures: this.api.measures(),
    }).subscribe({
      next: (d) => {
        this.manifest.set(d.manifest);
        this.accidents.set(d.accidents);
        this.hotspots.set(d.hotspots);
        this.crossings.set(d.crossings.features.map((f) => f.properties));
        this.crossingPoints.set(new Map(d.crossings.features.map((f) => [f.properties.id, f.geometry.coordinates])));
        this.measures.set(d.measures);
        this.state.set('ready');
      },
      error: (e: Error) => {
        this.error.set(e.message);
        this.state.set('error');
      },
    });
    this.api.cameras().subscribe({
      next: (c) => this.cameras.set(c),
      error: (e: Error) => this.camerasError.set(e.message),
    });
  }

  select(id: string | null): void {
    this.selectedId.set(id);
  }

  // Last event approved in the Import screen; the map flies to it.
  readonly lastAdded = signal<Accident | null>(null);

  upsertAccident(event: Accident): void {
    this.accidents.update((list) => {
      const i = list.findIndex((a) => a.event_id === event.event_id);
      return i === -1 ? [...list, event] : list.map((a, j) => (j === i ? { ...a, ...event } : a));
    });
  }
}
