import { ChangeDetectionStrategy, Component, computed, inject, input, output } from '@angular/core';
import { RouterLink } from '@angular/router';
import { BackendSession } from '../../../core/api/backend-session';
import { CAUZA, COMPONENTE, dateRo, GRAVITATE, lei, PRECIZIE } from '../../../core/format/labels';
import { NullLabelPipe } from '../../../core/format/null-label.pipe';
import { Accident, Hotspot } from '../../../core/models/contract';
import { PublishedEvent } from '../../../core/models/publication';
import { DataStore } from '../../../core/state/data.store';
import { HourChart } from '../../../shared/hour-chart/hour-chart';
import { ScoreBadge } from '../../../shared/score-badge/score-badge';

const COMPONENT_COLORS: Record<string, string> = {
  evenimente: 'var(--heat-2)', deces: 'var(--heat-4)', grav: 'var(--heat-3)', context: 'var(--muted)',
};
const ACTIONS: Record<string, string> = {
  imported: 'Import', corrected: 'Corectură', approved: 'Aprobare', rejected: 'Respingere', linked: 'Asociere la eveniment',
};

function text(value: unknown): string | null {
  return typeof value === 'string' ? value : null;
}

@Component({
  selector: 'app-location-dossier',
  imports: [RouterLink, NullLabelPipe, HourChart, ScoreBadge],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './location-dossier.html',
  styleUrl: './location-dossier.scss',
})
export class LocationDossier {
  protected readonly store = inject(DataStore);
  private readonly session = inject(BackendSession);

  readonly locationId = input<string>();
  readonly hotspot = input<Hotspot | null>(null);
  readonly rank = input<number | null>(null);
  readonly close = output<void>();

  protected readonly gravitate = GRAVITATE;
  protected readonly precizie = PRECIZIE;
  protected readonly dateRo = dateRo;
  protected readonly publication = this.store.publication;
  protected readonly id = computed(() => this.locationId() ?? this.hotspot()?.id ?? '');
  protected readonly location = computed(() => this.store.locationById().get(this.id()) ?? null);
  protected readonly title = computed(() => this.location()?.feature.properties.nume || this.hotspot()?.nume || this.id());
  protected readonly givenRank = computed(() => this.location() ? this.location()!.rank : this.rank());
  protected readonly score = computed(() => this.location() ? this.location()!.score : (this.hotspot()?.scor ?? null));
  protected readonly eventIds = computed(() => this.location()?.event_ids ?? this.hotspot()?.event_ids ?? []);
  protected readonly eventCount = computed(() => this.location()?.event_count ?? this.hotspot()?.nr_evenimente ?? 0);
  protected readonly max = computed(() => Math.max(1, ...this.store.hotspots().map((h) => h.scor)));
  protected readonly publishedEvents = computed(() => {
    const wanted = new Set(this.eventIds());
    return this.publication()?.events.filter((event) => wanted.has(event.event_id)) ?? [];
  });
  protected readonly publishedById = computed(() => new Map(this.publishedEvents().map((event) => [event.event_id, event])));
  protected readonly events = computed(() => this.eventIds()
    .map((id) => this.store.accidentById().get(id))
    .filter((event): event is Accident => !!event)
    .sort((a, b) => (b.data_eveniment ?? '').localeCompare(a.data_eveniment ?? '')));
  protected readonly articleCount = computed(() => this.location()?.source_article_count ??
    new Set(this.events().flatMap((event) => event.article_ids)).size);
  protected readonly missingEventIds = computed(() => this.eventIds().filter((id) => !this.store.accidentById().has(id)));
  protected readonly unknownHours = computed(() => this.events().filter((event) => event.ora === null).length);
  protected readonly hours = computed(() => this.location()?.score_details?.pe_ore ?? this.hotspot()?.pe_ore ?? null);
  protected readonly explanation = computed(() => this.location()
    ? this.location()!.score_details?.explicatie ?? 'Date insuficiente pentru clasament: sunt necesare minimum două evenimente la aceeași locație.'
    : this.hotspot()?.explicatie ?? 'Explicația priorității nu este disponibilă.');
  protected readonly gaps = computed(() => [...new Set([
    ...(this.location()?.unknowns ?? []),
    ...(this.location()?.score_details?.date_lipsa ?? this.hotspot()?.date_lipsa ?? []),
  ])]);
  protected readonly components = computed(() => {
    const values = this.location()?.score_details?.componente_scor ?? this.hotspot()?.componente_scor;
    if (!values) return [];
    // Percentages only size the breakdown bar; the score is the server's fixed value.
    const total = Object.values(values).reduce((sum, value) => sum + value, 0) || 1;
    return Object.entries(values).filter(([, value]) => value > 0).map(([key, value]) => ({
      key, label: COMPONENTE[key] ?? key, value, pct: (value / total) * 100, color: COMPONENT_COLORS[key],
    }));
  });
  protected readonly crossing = computed(() => this.location()?.feature.properties ??
    this.store.crossingById().get(this.hotspot()?.crossing_id ?? '') ?? null);
  protected readonly measures = computed(() => (this.publication() ? [] : this.hotspot()?.masuri ?? []).map((measure) => {
    const def = this.store.measureById().get(measure.measure_id);
    const cost = def && def.cost_lei_min !== null && def.cost_lei_max !== null
      ? `${lei(def.cost_lei_min)} – ${lei(def.cost_lei_max)}` : null;
    const reduction = def?.reducere_tipica != null ? `−${Math.round(def.reducere_tipica * 100)}%` : null;
    return { ...measure, def, cost, reduction };
  }));
  protected readonly jsonExport = computed(() => this.session.exportUrl(this.id(), 'json'));
  protected readonly htmlExport = computed(() => this.session.exportUrl(this.id(), 'html'));

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

  protected evidence(event: PublishedEvent): { articleId: string | null; field: string; quote: string }[] {
    return event.source_claims.flatMap((claim) => {
      const extraction = claim['original_extraction'];
      if (!extraction || typeof extraction !== 'object') return [];
      const quotes = (extraction as Record<string, unknown>)['dovezi'];
      if (!quotes || typeof quotes !== 'object') return [];
      return Object.entries(quotes).filter((entry): entry is [string, string] => typeof entry[1] === 'string')
        .map(([field, quote]) => ({ articleId: text(claim['article_id']), field, quote }));
    });
  }

  protected audit(event: PublishedEvent) {
    const entries: Record<string, unknown>[] = event.source_claims.flatMap((claim) => {
      const history = claim['history'];
      return Array.isArray(history) ? history.filter((entry): entry is Record<string, unknown> => !!entry && typeof entry === 'object')
        .filter((entry) => entry['action'] === 'corrected')
        .map((entry) => ({ ...entry, article_id: claim['article_id'] })) : [];
    });
    return [...entries, ...event.history].map((entry) => ({
      action: ACTIONS[text(entry['action']) ?? ''] ?? text(entry['action']) ?? 'Decizie',
      operator: text(entry['operator']), at: text(entry['at']), note: text(entry['note']),
      articleId: text(entry['article_id']), changes: JSON.stringify(entry['changes'] ?? {}, null, 2),
    }));
  }
}