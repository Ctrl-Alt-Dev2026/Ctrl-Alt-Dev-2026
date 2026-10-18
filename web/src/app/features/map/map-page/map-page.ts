import { ChangeDetectionStrategy, Component, computed, DestroyRef, effect, ElementRef, inject, input, signal, untracked, viewChild } from '@angular/core';
import { Router } from '@angular/router';
import { lei, participantLabel, PRECISE } from '../../../core/format/labels';
import { StreetMetric } from '../../../core/models/streets';
import { DataStore } from '../../../core/state/data.store';
import { LocationDossier } from '../../location/location-dossier/location-dossier';
import { AttentionDrawer } from '../attention-drawer/attention-drawer';
import { CameraViewer } from '../camera-viewer/camera-viewer';
import { CityMap } from '../city-map/city-map';
import { HotspotList } from '../hotspot-list/hotspot-list';
import { StreetPanel } from '../street-panel/street-panel';

@Component({
  selector: 'app-map-page',
  imports: [CityMap, HotspotList, LocationDossier, CameraViewer, StreetPanel, AttentionDrawer],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './map-page.html',
  styleUrl: './map-page.scss',
  host: { '(document:keydown.escape)': 'onEscape()' },
})
export class MapPage {
  protected readonly store = inject(DataStore);
  private readonly router = inject(Router);
  private readonly panel = viewChild<ElementRef<HTMLElement>>('panel');
  private readonly host = inject(ElementRef<HTMLElement>).nativeElement;

  // Bound from the route /locatie/:id.
  readonly id = input<string>();

  protected readonly applied = signal(false);
  protected readonly attentionOpen = signal(false);
  protected readonly streetLegend: Record<StreetMetric, string> = {
    isu: 'stradă: intervenții ISU 2024–2026',
    presa: 'stradă: relatări în presă 2026',
    pmud: 'arteră: accidente IPJ 2021 (PMUD)',
  };
  protected readonly basemapFailed = signal(false);
  protected readonly panelOpen = signal(true);
  // Streets (ISU + PMUD layer) or scored locations; tabs only when the dataset has both.
  protected readonly view = signal<'streets' | 'locations'>('streets');
  protected readonly hasStreets = computed(() => this.store.streets().features.length > 0);
  protected readonly showStreets = computed(() => this.hasStreets() && (this.view() === 'streets' || this.store.hotspots().length === 0));

  protected readonly participantLabel = participantLabel;
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
    // A new street or location opens at the top of the panel, not at the list's scroll position.
    effect(() => {
      this.store.selectedStreetId();
      this.store.selectedId();
      untracked(() => {
        // The panel's content component (street list/detail, dossier) is the element that scrolls.
        const panel = this.panel()?.nativeElement;
        for (const el of [panel, ...Array.from(panel?.children ?? [])]) el?.scrollTo({ top: 0 });
      });
    });
    // Stacked layout: the list sits under the map, so bring the map back into view to show the camera move.
    effect(() => {
      const street = this.store.selectedStreetId();
      untracked(() => {
        if (street && !matchMedia('(min-width: 56rem)').matches) this.host.scrollTo({ top: 0, behavior: 'smooth' });
      });
    });

    const wide = matchMedia('(min-width: 56rem)');
    const measure = () => {
      const rem = parseFloat(getComputedStyle(document.documentElement).fontSize);
      this.rightInset.set(wide.matches ? Math.min(Math.max(20 * rem, innerWidth * 0.28), 27 * rem) + 2 * rem : 0);
    };
    measure();
    addEventListener('resize', measure);
    inject(DestroyRef).onDestroy(() => removeEventListener('resize', measure));
  }

  protected openStreet(id: string): void {
    this.panelOpen.set(true);
    this.view.set('streets');
    this.store.selectedStreetId.set(id);
    if (this.store.selectedId()) this.router.navigate(['/']);
  }

  protected open(id: string): void {
    this.store.selectedStreetId.set(null);
    this.router.navigate(['/locatie', id]);
  }

  protected close(): void {
    this.router.navigate(['/']);
  }

  protected setParticipant(p: string | null): void {
    this.store.participant.set(p);
  }

  protected toggleApplied(): void {
    this.applied.update((v) => !v);
  }

  protected toggleCameras(): void {
    this.store.showCameras.update((v) => !v);
    if (!this.store.showCameras()) this.store.selectedCameraId.set(null);
  }

  protected onEscape(): void {
    if (this.attentionOpen()) return; // the dialog closes itself on Escape
    if (this.store.selectedCameraId()) this.store.selectedCameraId.set(null);
    else if (this.store.selectedStreetId()) this.store.selectedStreetId.set(null);
  }
}
