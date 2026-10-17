import { computed, effect, inject, Injectable, signal, untracked } from '@angular/core';
import { environment } from '../../../environments/environment';
import { BackendSession } from '../api/backend-session';
import { DataApi } from '../api/data-api';
import { Camera } from '../models/camera';
import { Accident, Crossing, Hotspot, Manifest, Measure } from '../models/contract';
import { DataMode, PublishedLocation, PublicationSnapshot } from '../models/publication';

export type LoadState = 'loading' | 'ready' | 'empty' | 'error';

// All public views are projections of one immutable backend publication.
@Injectable({ providedIn: 'root' })
export class DataStore {
  private readonly api = inject(DataApi);
  readonly session = inject(BackendSession);
  readonly isHttp = environment.api.mode === 'http';
  private requestVersion = 0;

  readonly state = signal<LoadState>('loading');
  readonly error = signal<string | null>(null);
  readonly manifest = signal<Manifest | null>(null);
  readonly publication = signal<PublicationSnapshot | null>(null);
  readonly locations = signal<PublishedLocation[]>([]);
  readonly locationById = computed(() => new Map(this.locations().map((row) => [row.location_id, row])));
  readonly accidents = signal<Accident[]>([]);
  readonly hotspots = signal<Hotspot[]>([]);
  readonly crossings = signal<Crossing[]>([]);
  readonly crossingPoints = signal<Map<string, [number, number]>>(new Map());
  readonly measures = signal<Measure[]>([]);
  readonly selectedId = signal<string | null>(null);
  readonly selectedLocation = computed(() => this.locationById().get(this.selectedId() ?? '') ?? null);
  readonly cameras = signal<Camera[]>([]);
  readonly camerasError = signal<string | null>(null);
  readonly showCameras = signal(false);
  readonly selectedCameraId = signal<string | null>(null);
  readonly selectedCamera = computed(() => this.cameras().find((c) => c.id === this.selectedCameraId()) ?? null);
  readonly participant = signal<string | null>(null);
  readonly lastAdded = signal<Accident | null>(null);

  // The backend rank is frozen across display filters and route changes.
  readonly ranked = computed(() => [...this.hotspots()].sort((a, b) =>
    a.rank != null && b.rank != null ? a.rank - b.rank : b.scor - a.scor,
  ));
  readonly rankOf = computed(() => new Map(this.ranked().map((h, i) => [h.id, h.rank ?? i + 1])));
  readonly participants = computed(() => [...new Set(this.accidents().flatMap((a) => a.participanti))].sort());
  private readonly matches = (a: Accident) => {
    const p = this.participant();
    return p === null || a.participanti.includes(p);
  };
  readonly visibleHotspots = computed(() =>
    this.ranked().filter((h) => h.event_ids.some((id) => {
      const a = this.accidentById().get(id);
      return !!a && this.matches(a);
    })),
  );
  readonly unrankedLocations = computed(() => this.locations().filter((row) => row.score === null));
  readonly visibleUnrankedLocations = computed(() => this.unrankedLocations().filter((row) => row.event_ids.some((id) => {
    const event = this.accidentById().get(id);
    return !!event && this.matches(event);
  })));
  readonly selected = computed(() => this.hotspots().find((h) => h.id === this.selectedId()) ?? null);
  readonly isSynthetic = computed(() => this.isHttp ? this.session.dataMode() === 'synthetic' : this.manifest()?.data_mode === 'synthetic');
  readonly accidentById = computed(() => new Map(this.accidents().map((a) => [a.event_id, a])));
  readonly measureById = computed(() => new Map(this.measures().map((m) => [m.id, m])));
  readonly crossingById = computed(() => new Map(this.crossings().map((c) => [c.id, c])));
  readonly mappable = computed(() =>
    this.accidents().filter((a) => a.in_iasi !== false && a.lat !== null && a.lon !== null && this.matches(a)),
  );

  constructor() {
    effect(() => {
      this.session.dataMode();
      untracked(() => this.load());
    });
    this.api.cameras().subscribe({
      next: (c) => this.cameras.set(c),
      error: (e: Error) => this.camerasError.set(e.message),
    });
  }

  private clearPublication(): void {
    this.manifest.set(null);
    this.publication.set(null);
    this.locations.set([]);
    this.accidents.set([]);
    this.hotspots.set([]);
    this.crossings.set([]);
    this.crossingPoints.set(new Map());
    this.measures.set([]);
    this.participant.set(null);
    this.selectedId.set(null);
    this.lastAdded.set(null);
  }

  setDataMode(mode: DataMode): void {
    if (mode === this.session.dataMode()) return;
    ++this.requestVersion;
    this.clearPublication();
    this.error.set(null);
    this.state.set('loading');
    this.session.setDataMode(mode);
  }

  // load() reads latest, unless the URL explicitly pins a historical version.
  // refresh() also clears that explicit pin.
  refresh(): void {
    this.session.clearSnapshotPin();
    this.load();
  }

  load(): void {
    const version = ++this.requestVersion;
    const mode = this.session.dataMode();
    this.clearPublication();
    this.session.snapshotId.set(null);
    this.error.set(null);
    this.state.set('loading');
    this.api.loadDataset().subscribe({
      next: (data) => {
        if (version !== this.requestVersion || mode !== this.session.dataMode()) return;
        this.manifest.set(data.manifest);
        this.publication.set(data.publication);
        this.locations.set(data.publication?.locations ?? []);
        if (data.publication) this.session.snapshotId.set(data.publication.snapshot_id);
        this.accidents.set(data.accidents);
        this.hotspots.set(data.hotspots);
        this.crossings.set(data.crossings.features.map((feature) => feature.properties));
        this.crossingPoints.set(new Map(data.crossings.features.map((feature) => [feature.properties.id, feature.geometry.coordinates])));
        this.measures.set(data.measures);
        this.state.set('ready');
      },
      error: (error: { status?: number; error?: { detail?: { code?: string; message?: string } }; message?: string }) => {
        if (version !== this.requestVersion || mode !== this.session.dataMode()) return;
        const detail = error.error?.detail;
        if (this.isHttp && error.status === 404 && detail?.code === 'publication_not_found') {
          this.state.set('empty');
          return;
        }
        this.error.set(detail?.message ?? error.message ?? 'Serviciul nu a răspuns.');
        this.state.set('error');
      },
    });
  }

  select(id: string | null): void {
    this.selectedId.set(id);
  }

  // Static prototype only: approval never changes an immutable published snapshot.
  upsertAccident(event: Accident): void {
    if (this.isHttp) return;
    this.accidents.update((list) => {
      const index = list.findIndex((a) => a.event_id === event.event_id);
      return index === -1 ? [...list, event] : list.map((a, i) => i === index ? { ...a, ...event } : a);
    });
  }
}
