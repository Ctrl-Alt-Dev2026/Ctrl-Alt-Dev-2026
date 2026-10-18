import { HttpErrorResponse } from '@angular/common/http';
import { computed, inject, Injectable, signal } from '@angular/core';
import { DataApi } from '../api/data-api';
import { Camera } from '../models/camera';
import { Accident, Crossing, Hotspot, Manifest, Measure } from '../models/contract';
import { LiveDataset, LiveStatus } from '../models/live';
import { NO_STREETS, StreetCollection, StreetMetric } from '../models/streets';
import { PRECISE } from '../format/labels';
import { H3Collection, NO_H3 } from '../models/h3';

// waiting = the server is up but its first collection has not finished yet.
export type LoadState = 'loading' | 'ready' | 'waiting' | 'error';

// How often the page asks the server whether a newer dataset exists (it collects every 30 minutes).
const POLL_READY_MS = 2 * 60_000;
const POLL_WAITING_MS = 20_000;

// Every view projects the server's newest collected dataset; all viewers see the same one.
@Injectable({ providedIn: 'root' })
export class DataStore {
  private readonly api = inject(DataApi);
  private fetching = false;
  private lastPoll = 0;

  readonly state = signal<LoadState>('loading');
  // Set when the server stops answering; data already on screen stays.
  readonly error = signal<string | null>(null);
  readonly status = signal<LiveStatus | null>(null);
  readonly builtAt = signal<string | null>(null);
  readonly manifest = signal<Manifest | null>(null);
  readonly accidents = signal<Accident[]>([]);
  readonly hotspots = signal<Hotspot[]>([]);
  readonly crossings = signal<Crossing[]>([]);
  readonly measures = signal<Measure[]>([]);
  readonly selectedId = signal<string | null>(null);
  readonly cameras = signal<Camera[]>([]);
  readonly camerasError = signal<string | null>(null);
  readonly showCameras = signal(false);
  readonly selectedCameraId = signal<string | null>(null);
  readonly selectedCamera = computed(() => this.cameras().find((c) => c.id === this.selectedCameraId()) ?? null);
  readonly participant = signal<string | null>(null);
  readonly streets = signal<StreetCollection>(NO_STREETS);
  readonly streetMetric = signal<StreetMetric>('isu');
  readonly streetRanking = signal<'events' | 'score'>('score');
  readonly h3 = signal<H3Collection>(NO_H3);
  readonly selectedStreetId = signal<string | null>(null);
  readonly selectedStreet = computed(() => this.streets().features.find((f) => f.properties.id === this.selectedStreetId()) ?? null);
  // Events of the chosen source per street, under the participant filter. PMUD totals have no
  // breakdown, so they never filter.
  readonly streetCount = computed(() => {
    const metric = this.streetMetric();
    return new Map(this.streets().features.map((f) => {
      const ids = metric === 'presa' ? f.properties.presa_event_ids : f.properties.isu_event_ids;
      return [f.properties.id, ids.filter((id) => {
        const a = this.accidentById().get(id);
        return !!a && this.matches(a);
      }).length];
    }));
  });
  // Value drawn on the map and used for ordering; null = the street has no figure in this source.
  readonly streetValue = computed(() => {
    const metric = this.streetMetric();
    const count = this.streetCount();
    return new Map(this.streets().features.map((f) => [
      f.properties.id,
      metric === 'pmud' ? f.properties.pmud_2021 : !count.get(f.properties.id) ? null :
        this.streetRanking() === 'score' ? (f.properties.analiza?.[metric].scor ?? null) : count.get(f.properties.id)!,
    ]));
  });
  readonly rankedStreets = computed(() => {
    const value = this.streetValue();
    return this.streets().features
      .filter((f) => value.get(f.properties.id) != null)
      .sort((a, b) => value.get(b.properties.id)! - value.get(a.properties.id)! || a.properties.nume.localeCompare(b.properties.nume, 'ro'));
  });
  // The fixed "look here first" list from isu/ (independent of the source switch and filters).
  readonly attentionStreets = computed(() => this.streets().features
    .filter((f) => f.properties.prioritate !== null)
    .sort((a, b) => a.properties.prioritate! - b.properties.prioritate!));
  // A street's detail lists both event sources, each labelled; only the participant filter applies.
  readonly streetEvents = computed(() => {
    const street = this.selectedStreet();
    if (!street) return [];
    const byId = this.accidentById();
    const p = this.participant();
    return [...street.properties.isu_event_ids, ...street.properties.presa_event_ids]
      .map((id) => byId.get(id))
      .filter((a): a is Accident => !!a && (p === null || a.participanti.includes(p)))
      .sort((a, b) => (b.data_eveniment ?? b.publicat_la ?? '').localeCompare(a.data_eveniment ?? a.publicat_la ?? ''));
  });

  // The backend rank is frozen across display filters and route changes.
  readonly ranked = computed(() => [...this.hotspots()].sort((a, b) =>
    a.rank != null && b.rank != null ? a.rank - b.rank : b.scor - a.scor,
  ));
  readonly rankOf = computed(() => new Map(this.ranked().map((h, i) => [h.id, h.rank ?? i + 1])));
  readonly participants = computed(() => [...new Set(this.accidents().flatMap((a) => a.participanti))].sort());
  // Source switch: every collected event carries sursa_tip (isu or presa); one without it is never filtered out.
  // "pmud" has no events, so none show.
  private readonly matches = (a: Accident) => {
    const p = this.participant();
    if (a.sursa_tip && a.sursa_tip !== this.streetMetric()) return false;
    return p === null || a.participanti.includes(p);
  };
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
  readonly mappable = computed(() =>
    this.accidents().filter((a) => a.in_iasi === true && PRECISE.has(a.precizie_loc) &&
      a.lat !== null && a.lon !== null && this.matches(a)),
  );
  readonly approximateCount = computed(() => this.accidents().filter((a) =>
    a.in_iasi === true && !PRECISE.has(a.precizie_loc) && this.matches(a)).length);
  readonly visibleH3 = computed<H3Collection>(() => {
    const ids = new Set(this.mappable().map((a) => a.event_id));
    return { type: 'FeatureCollection', features: this.h3().features.flatMap((f) => {
      const event_ids = f.properties.event_ids.filter((id) => ids.has(id));
      return event_ids.length ? [{ ...f, properties: { ...f.properties, event_ids, nr_evenimente: event_ids.length } }] : [];
    }) };
  });

  constructor() {
    this.poll();
    // One timer: it asks often while the first collection runs, rarely once data is shown.
    setInterval(() => {
      const wait = this.state() === 'ready' ? POLL_READY_MS : POLL_WAITING_MS;
      if (!document.hidden && Date.now() - this.lastPoll >= wait) this.poll();
    }, POLL_WAITING_MS);
    document.addEventListener('visibilitychange', () => {
      if (!document.hidden && Date.now() - this.lastPoll >= POLL_WAITING_MS) this.poll();
    });
    this.api.cameras().subscribe({
      next: (c) => this.cameras.set(c),
      error: (e: Error) => this.camerasError.set(e.message),
    });
  }

  // Reads the cheap status; downloads the dataset only when the server has built a newer one.
  poll(): void {
    this.lastPoll = Date.now();
    this.api.status().subscribe({
      next: (status) => {
        this.status.set(status);
        this.error.set(null);
        if (status.construit_la && status.construit_la !== this.builtAt()) this.fetchDataset();
        else if (!status.construit_la) this.state.set('waiting');
      },
      error: (error: HttpErrorResponse) => this.fail(error),
    });
  }

  private fetchDataset(): void {
    if (this.fetching) return;
    this.fetching = true;
    this.api.dataset().subscribe({
      next: (data) => {
        this.fetching = false;
        this.apply(data);
      },
      error: (error: HttpErrorResponse) => {
        this.fetching = false;
        if (error.status === 503 && error.error?.detail?.code === 'dataset_not_ready') this.state.set('waiting');
        else this.fail(error);
      },
    });
  }

  // Filters and selections survive a refresh; a selection that no longer exists simply shows nothing.
  private apply(data: LiveDataset): void {
    this.builtAt.set(data.built_at);
    this.manifest.set(data.manifest);
    this.accidents.set(data.accidents);
    this.hotspots.set(data.hotspots);
    this.crossings.set(data.crossings.features.map((feature) => feature.properties));
    this.measures.set(data.measures);
    this.streets.set(data.streets);
    this.h3.set(data.accidents_h3 ?? NO_H3);
    this.state.set('ready');
  }

  private fail(error: HttpErrorResponse): void {
    this.error.set(error.status === 0 ? 'Serverul nu răspunde.' : `Serverul a răspuns cu eroarea ${error.status}.`);
    if (this.state() !== 'ready') this.state.set('error');
  }

  select(id: string | null): void {
    this.selectedId.set(id);
  }
}
