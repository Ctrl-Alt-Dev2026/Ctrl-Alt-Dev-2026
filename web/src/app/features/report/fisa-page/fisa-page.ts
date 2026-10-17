import { ChangeDetectionStrategy, Component, computed, inject, input, signal } from '@angular/core';
import { BackendSession } from '../../../core/api/backend-session';
import { CAUZA, dateRo, lei } from '../../../core/format/labels';
import { NullLabelPipe } from '../../../core/format/null-label.pipe';
import { Accident } from '../../../core/models/contract';
import { DataStore } from '../../../core/state/data.store';

// The server exports the complete dossier from the same immutable publication as this summary.
@Component({
  selector: 'app-fisa-page',
  imports: [NullLabelPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './fisa-page.html',
  styleUrl: './fisa-page.scss',
})
export class FisaPage {
  protected readonly store = inject(DataStore);
  private readonly session = inject(BackendSession);
  readonly ids = input<string>();
  private readonly chosen = signal<string[] | null>(null);
  protected readonly dateRo = dateRo;
  protected readonly publication = this.store.publication;
  protected readonly selectedIds = computed(() => this.chosen() ??
    (this.ids()?.split(',').filter(Boolean) ?? this.store.locations().map((location) => location.location_id)));
  protected readonly publishedRows = computed(() => {
    const publication = this.publication();
    if (!publication) return [];
    const wanted = new Set(this.selectedIds());
    return publication.locations.filter((location) => wanted.has(location.location_id)).map((location) => ({
      location,
      events: publication.events.filter((event) => location.event_ids.includes(event.event_id)),
      jsonExport: this.session.exportUrl(location.location_id, 'json'),
      htmlExport: this.session.exportUrl(location.location_id, 'html'),
    }));
  });
  protected readonly publishedArticleCount = computed(() =>
    new Set(this.publication()?.events.flatMap((event) => event.article_ids) ?? []).size);
  protected readonly unknownRequestedIds = computed(() =>
    this.selectedIds().filter((id) => !this.store.locationById().has(id)));

  // Explicit static demo mode keeps its original read-only sheet.
  protected readonly rows = computed(() => {
    const wanted = this.ids()?.split(',').filter(Boolean);
    return this.store.ranked().map((h, i) => ({ h, rank: i + 1 }))
      .filter(({ h }) => !wanted?.length || wanted.includes(h.id))
      .map(({ h, rank }) => ({
        h, rank,
        events: h.event_ids.map((id) => this.store.accidentById().get(id)).filter((event) => !!event),
        measures: h.masuri.map((measure) => {
          const def = this.store.measureById().get(measure.measure_id);
          const cost = def && def.cost_lei_min !== null && def.cost_lei_max !== null
            ? `${lei(def.cost_lei_min)} – ${lei(def.cost_lei_max)}` : null;
          return { ...measure, name: def?.nume ?? measure.measure_id, cost };
        }),
      }));
  });

  protected included(id: string): boolean {
    return this.selectedIds().includes(id);
  }

  protected toggle(id: string): void {
    const selected = new Set(this.selectedIds());
    if (selected.has(id)) selected.delete(id);
    else selected.add(id);
    this.chosen.set([...selected]);
  }

  protected selectAll(): void {
    this.chosen.set(this.store.locations().map((location) => location.location_id));
  }

  protected selectNone(): void {
    this.chosen.set([]);
  }

  protected safeUrl(value: string): string | null {
    try {
      const url = new URL(value);
      return ['https:', 'http:'].includes(url.protocol) && !url.username && !url.password ? value : null;
    } catch { return null; }
  }

  protected sourceDate(value: string | null): string {
    return value ? dateRo(value.slice(0, 10)) : 'dată necunoscută';
  }

  protected cause(value: Accident['cauza_raportata']): string | null {
    return value ? CAUZA[value] : null;
  }

  protected print(): void {
    window.print();
  }
}
