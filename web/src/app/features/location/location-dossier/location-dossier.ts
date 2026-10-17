import { ChangeDetectionStrategy, Component, computed, inject, input, output } from '@angular/core';
import { RouterLink } from '@angular/router';
import { CAUZA, COMPONENTE, dateRo, GRAVITATE, lei, PRECIZIE } from '../../../core/format/labels';
import { NullLabelPipe } from '../../../core/format/null-label.pipe';
import { Accident, Hotspot } from '../../../core/models/contract';
import { DataStore } from '../../../core/state/data.store';
import { HourChart } from '../../../shared/hour-chart/hour-chart';
import { ScoreBadge } from '../../../shared/score-badge/score-badge';

const COMPONENT_COLORS: Record<string, string> = {
  evenimente: 'var(--heat-2)',
  deces: 'var(--heat-4)',
  grav: 'var(--heat-3)',
  context: 'var(--muted)',
};

@Component({
  selector: 'app-location-dossier',
  imports: [RouterLink, NullLabelPipe, HourChart, ScoreBadge],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './location-dossier.html',
  styleUrl: './location-dossier.scss',
})
export class LocationDossier {
  private readonly store = inject(DataStore);

  readonly hotspot = input.required<Hotspot>();
  readonly rank = input.required<number>();
  readonly close = output<void>();

  protected readonly gravitate = GRAVITATE;
  protected readonly precizie = PRECIZIE;
  protected readonly dateRo = dateRo;

  protected readonly max = computed(() => Math.max(1, ...this.store.hotspots().map((h) => h.scor)));

  protected readonly events = computed(() =>
    this.hotspot()
      .event_ids.map((id) => this.store.accidentById().get(id))
      .filter((a): a is Accident => !!a)
      .sort((a, b) => (b.data_eveniment ?? '').localeCompare(a.data_eveniment ?? '')),
  );

  protected readonly missingEventIds = computed(() =>
    this.hotspot().event_ids.filter((id) => !this.store.accidentById().has(id)),
  );

  protected readonly unknownHours = computed(() => this.events().filter((e) => e.ora === null).length);

  protected readonly components = computed(() => {
    const c = this.hotspot().componente_scor;
    const total = Object.values(c).reduce((s, v) => s + v, 0) || 1;
    return Object.entries(c)
      .filter(([, v]) => v > 0)
      .map(([key, v]) => ({ key, label: COMPONENTE[key] ?? key, value: v, pct: (v / total) * 100, color: COMPONENT_COLORS[key] }));
  });

  protected readonly crossing = computed(() => {
    const id = this.hotspot().crossing_id;
    return id ? (this.store.crossingById().get(id) ?? null) : null;
  });

  protected readonly measures = computed(() =>
    this.hotspot().masuri.map((m) => {
      const def = this.store.measureById().get(m.measure_id);
      const cost =
        def && def.cost_lei_min !== null && def.cost_lei_max !== null
          ? `${lei(def.cost_lei_min)} – ${lei(def.cost_lei_max)}`
          : null;
      const reduction = def?.reducere_tipica != null ? `−${Math.round(def.reducere_tipica * 100)}%` : null;
      return { ...m, def, cost, reduction };
    }),
  );

  protected cause(e: Accident): string | null {
    return e.cauza_raportata ? CAUZA[e.cauza_raportata] : null;
  }

  protected hour(e: Accident): string {
    return e.ora ?? 'oră necunoscută';
  }

  protected night(e: Accident): string | null {
    return e.noapte === null ? null : e.noapte ? 'noaptea' : 'ziua';
  }
}
