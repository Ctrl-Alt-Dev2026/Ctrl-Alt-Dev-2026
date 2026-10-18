import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { dateRo, GRAVITATE, lei, participantLabel } from '../../../core/format/labels';
import { NullLabelPipe } from '../../../core/format/null-label.pipe';
import { Accident } from '../../../core/models/contract';
import { DataStore } from '../../../core/state/data.store';

const CLOCK = new Intl.DateTimeFormat('ro-RO', { dateStyle: 'long', timeStyle: 'short', timeZone: 'Europe/Bucharest' });

// Printable sheet from the same collected dataset as the map: the "Străzi de verificat" list, then any scored locations.
@Component({
  selector: 'app-fisa-page',
  imports: [NullLabelPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './fisa-page.html',
  styleUrl: './fisa-page.scss',
})
export class FisaPage {
  protected readonly store = inject(DataStore);
  protected readonly dateRo = dateRo;
  protected readonly gravitate = GRAVITATE;
  protected readonly participantLabel = participantLabel;
  // null = every street on the list; a set once the user unticks one.
  private readonly chosen = signal<Set<string> | null>(null);

  protected readonly builtAt = computed(() => {
    const at = this.store.builtAt();
    return at ? CLOCK.format(new Date(at)) : null;
  });
  protected readonly period = computed(() => {
    const p = this.store.manifest()?.perioada;
    return p?.[0] && p[1] ? `${dateRo(p[0])} – ${dateRo(p[1])}` : null;
  });
  protected readonly streets = computed(() => {
    const byId = this.store.accidentById();
    return this.store.attentionStreets().map((f) => ({
      f,
      events: [...f.properties.isu_event_ids, ...f.properties.presa_event_ids]
        .map((id) => byId.get(id))
        .filter((a): a is Accident => !!a)
        .sort((a, b) => (b.data_eveniment ?? b.publicat_la ?? '').localeCompare(a.data_eveniment ?? a.publicat_la ?? '')),
    }));
  });
  protected readonly selectedStreets = computed(() => {
    const chosen = this.chosen();
    return this.streets().filter((s) => !chosen || chosen.has(s.f.properties.id));
  });
  protected readonly locations = computed(() => this.store.ranked().map((h, i) => ({
    h,
    rank: h.rank ?? i + 1,
    events: h.event_ids.map((id) => this.store.accidentById().get(id)).filter((a): a is Accident => !!a),
    measures: h.masuri.map((measure) => {
      const def = this.store.measureById().get(measure.measure_id);
      const cost = def && def.cost_lei_min !== null && def.cost_lei_max !== null
        ? `${lei(def.cost_lei_min)} – ${lei(def.cost_lei_max)}` : null;
      return { ...measure, name: def?.nume ?? measure.measure_id, cost };
    }),
  })));

  protected included(id: string): boolean {
    return this.chosen()?.has(id) ?? true;
  }

  protected toggle(id: string): void {
    const next = new Set(this.chosen() ?? this.streets().map((s) => s.f.properties.id));
    if (next.has(id)) next.delete(id);
    else next.add(id);
    this.chosen.set(next);
  }

  protected selectAll(): void {
    this.chosen.set(null);
  }

  protected selectNone(): void {
    this.chosen.set(new Set());
  }

  protected source(a: Accident): string {
    return a.sursa_tip === 'presa' ? 'Presă' : 'ISU';
  }

  protected participants(a: Accident): string {
    return a.participanti.length ? a.participanti.map(participantLabel).join(', ') : 'participanți nemenționați';
  }

  protected safeUrl(value: string): string | null {
    try {
      const url = new URL(value);
      return ['https:', 'http:'].includes(url.protocol) && !url.username && !url.password ? value : null;
    } catch { return null; }
  }

  protected print(): void {
    window.print();
  }
}
