import { ChangeDetectionStrategy, Component, computed, inject, input, output } from '@angular/core';
import { RouterLink } from '@angular/router';
import { CAUZA, COMPONENTE, dateRo, GRAVITATE, lei, PRECIZIE } from '../../../core/format/labels';
import { NullLabelPipe } from '../../../core/format/null-label.pipe';
import { Accident, Hotspot } from '../../../core/models/contract';
import { DataStore } from '../../../core/state/data.store';
import { HourChart } from '../../../shared/hour-chart/hour-chart';
import { ScoreBadge } from '../../../shared/score-badge/score-badge';

const COMPONENT_COLORS: Record<string, string> = {
  evenimente: 'var(--heat-2)', deces: 'var(--heat-4)', grav: 'var(--heat-3)', context: 'var(--muted)',
};

@Component({
  selector: 'app-location-dossier',
  imports: [RouterLink, NullLabelPipe, HourChart, ScoreBadge],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './location-dossier.html',
  styleUrl: './location-dossier.scss',
})
export class LocationDossier {
  protected readonly store = inject(DataStore);

  readonly hotspot = input.required<Hotspot>();
  readonly rank = input<number | null>(null);
  readonly close = output<void>();

  protected readonly gravitate = GRAVITATE;
  protected readonly precizie = PRECIZIE;
  protected readonly dateRo = dateRo;
  protected readonly max = computed(() => Math.max(1, ...this.store.hotspots().map((h) => h.scor)));
  protected readonly events = computed(() => this.hotspot().event_ids
    .map((id) => this.store.accidentById().get(id))
    .filter((event): event is Accident => !!event)
    .sort((a, b) => (b.data_eveniment ?? '').localeCompare(a.data_eveniment ?? '')));
  protected readonly articleCount = computed(() => new Set(this.events().flatMap((event) => event.article_ids)).size);
  protected readonly unknownHours = computed(() => this.events().filter((event) => event.ora === null).length);
  protected readonly components = computed(() => {
    const values = this.hotspot().componente_scor;
    // Percentages only size the breakdown bar; the score is the server's fixed value.
    const total = Object.values(values).reduce((sum, value) => sum + value, 0) || 1;
    return Object.entries(values).filter(([, value]) => value > 0).map(([key, value]) => ({
      key, label: COMPONENTE[key] ?? key, value, pct: (value / total) * 100, color: COMPONENT_COLORS[key],
    }));
  });
  protected readonly crossing = computed(() => this.store.crossingById().get(this.hotspot().crossing_id ?? '') ?? null);
  protected readonly measures = computed(() => this.hotspot().masuri.map((measure) => {
    const def = this.store.measureById().get(measure.measure_id);
    const cost = def && def.cost_lei_min !== null && def.cost_lei_max !== null
      ? `${lei(def.cost_lei_min)} – ${lei(def.cost_lei_max)}` : null;
    const reduction = def?.reducere_tipica != null ? `−${Math.round(def.reducere_tipica * 100)}%` : null;
    return { ...measure, def, cost, reduction };
  }));

  protected cause(event: Accident): string | null {
    return event.cauza_raportata ? CAUZA[event.cauza_raportata] : null;
  }

  protected hour(event: Accident): string {
    return event.ora ?? 'oră necunoscută';
  }

  protected night(event: Accident): string | null {
    return event.noapte === null ? null : event.noapte ? 'noaptea' : 'ziua';
  }

  protected safeUrl(value: string): string | null {
    try {
      const url = new URL(value);
      return ['https:', 'http:'].includes(url.protocol) && !url.username && !url.password ? value : null;
    } catch { return null; }
  }

  protected timestamp(value: string | null): string {
    if (!value) return 'dată necunoscută';
    if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return dateRo(value);
    const date = new Date(value);
    return Number.isNaN(date.valueOf()) ? value : new Intl.DateTimeFormat('ro-RO', {
      dateStyle: 'short', timeStyle: 'short', timeZone: 'Europe/Bucharest',
    }).format(date);
  }
}
