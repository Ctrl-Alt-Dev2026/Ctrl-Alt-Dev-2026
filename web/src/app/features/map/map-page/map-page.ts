import { ChangeDetectionStrategy, Component, computed, DestroyRef, effect, inject, input, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { lei, participantLabel, PRECISE } from '../../../core/format/labels';
import { DataStore } from '../../../core/state/data.store';
import { LocationDossier } from '../../location/location-dossier/location-dossier';
import { CameraViewer } from '../camera-viewer/camera-viewer';
import { CityMap } from '../city-map/city-map';
import { HotspotList } from '../hotspot-list/hotspot-list';

const TOUR_STEP_MS = 7000;

@Component({
  selector: 'app-map-page',
  imports: [CityMap, HotspotList, LocationDossier, CameraViewer, RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './map-page.html',
  styleUrl: './map-page.scss',
  host: { '(document:keydown.escape)': 'onEscape()' },
})
export class MapPage {
  protected readonly store = inject(DataStore);
  private readonly router = inject(Router);

  // Bound from the route /locatie/:id.
  readonly id = input<string>();

  protected readonly applied = signal(false);
  protected readonly touring = signal(false);
  protected readonly basemapFailed = signal(false);
  protected readonly panelOpen = signal(true);
  private tourTimer?: ReturnType<typeof setTimeout>;

  protected readonly participantLabel = participantLabel;
  protected readonly added = computed(() => {
    const a = this.store.lastAdded();
    return a && a.lat !== null && a.lon !== null ? a : null;
  });
  protected readonly addedPoint = computed<[number, number] | null>(() => {
    const a = this.added();
    return a ? [a.lon!, a.lat!] : null;
  });
  protected readonly rank = computed(() => this.store.rankOf().get(this.store.selectedId() ?? '') ?? 0);
  protected readonly approxCount = computed(
    () => this.store.mappable().filter((a) => !PRECISE.has(a.precizie_loc)).length,
  );
  protected readonly hasMeasures = computed(() => this.store.visibleHotspots().some((row) => row.masuri.length > 0));

  // Panel width in px for the map's fly-to padding; 0 when the panel stacks under the map.
  protected readonly rightInset = signal(0);

  // "Aplică măsurile" counter: only documented numbers; unknown costs are counted, not guessed.
  protected readonly counter = computed(() => {
    const targeted = this.store.visibleHotspots().filter((h) => h.masuri.length > 0);
    let min = 0;
    let max = 0;
    let unknown = 0;
    for (const h of targeted) {
      for (const m of h.masuri) {
        const def = this.store.measureById().get(m.measure_id);
        if (def?.cost_lei_min != null && def.cost_lei_max != null) {
          min += def.cost_lei_min;
          max += def.cost_lei_max;
        } else {
          unknown++;
        }
      }
    }
    return {
      locations: targeted.length,
      events: targeted.reduce((s, h) => s + h.nr_evenimente, 0),
      cost: min || max ? `${lei(min)} – ${lei(max)}` : null,
      unknown,
    };
  });

  constructor() {
    effect(() => {
      this.store.state();
      this.store.select(this.id() ?? null);
    });
    effect(() => {
      this.store.session.dataMode();
      this.applied.set(false);
      this.stopTour();
    });

    const wide = matchMedia('(min-width: 56rem)');
    const measure = () => {
      const rem = parseFloat(getComputedStyle(document.documentElement).fontSize);
      this.rightInset.set(wide.matches ? Math.min(Math.max(20 * rem, innerWidth * 0.28), 27 * rem) + 2 * rem : 0);
    };
    measure();
    addEventListener('resize', measure);
    inject(DestroyRef).onDestroy(() => {
      removeEventListener('resize', measure);
      clearTimeout(this.tourTimer);
    });
  }

  protected open(id: string): void {
    this.store.lastAdded.set(null);
    this.router.navigate(['/locatie', id]);
  }

  protected dismissAdded(): void {
    this.store.lastAdded.set(null);
  }

  protected close(): void {
    this.stopTour();
    this.router.navigate(['/']);
  }

  protected setParticipant(p: string | null): void {
    this.store.participant.set(p);
  }

  protected toggleApplied(): void {
    this.applied.update((v) => !v);
  }

  protected startTour(): void {
    const ids = this.store.visibleHotspots().map((h) => h.id);
    if (!ids.length) return;
    this.touring.set(true);
    this.panelOpen.set(true);
    const step = (i: number) => {
      if (!this.touring()) return;
      if (i >= ids.length) {
        this.stopTour();
        this.router.navigate(['/']);
        return;
      }
      this.open(ids[i]);
      this.tourTimer = setTimeout(() => step(i + 1), TOUR_STEP_MS);
    };
    step(0);
  }

  protected toggleCameras(): void {
    this.store.showCameras.update((v) => !v);
    if (!this.store.showCameras()) this.store.selectedCameraId.set(null);
  }

  protected onEscape(): void {
    if (this.store.selectedCameraId()) this.store.selectedCameraId.set(null);
    else this.stopTour();
  }

  protected stopTour(): void {
    this.touring.set(false);
    clearTimeout(this.tourTimer);
  }
}
