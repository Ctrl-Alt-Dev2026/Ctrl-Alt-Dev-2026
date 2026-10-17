import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';
import { dateRo, lei } from '../../../core/format/labels';
import { NullLabelPipe } from '../../../core/format/null-label.pipe';
import { DataStore } from '../../../core/state/data.store';

// Printable verification sheet. Stands in for GET /api/report until Person 5's PDF generator exists.
@Component({
  selector: 'app-fisa-page',
  imports: [NullLabelPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './fisa-page.html',
  styleUrl: './fisa-page.scss',
})
export class FisaPage {
  protected readonly store = inject(DataStore);

  // ?ids=h-1,h-2 ; empty = every ranked location.
  readonly ids = input<string>();

  protected readonly dateRo = dateRo;

  protected readonly rows = computed(() => {
    const wanted = this.ids()?.split(',').filter(Boolean);
    const ranked = this.store.ranked();
    return ranked
      .map((h, i) => ({ h, rank: i + 1 }))
      .filter(({ h }) => !wanted?.length || wanted.includes(h.id))
      .map(({ h, rank }) => ({
        h,
        rank,
        events: h.event_ids.map((id) => this.store.accidentById().get(id)).filter((a) => !!a),
        measures: h.masuri.map((m) => {
          const def = this.store.measureById().get(m.measure_id);
          const cost =
            def && def.cost_lei_min !== null && def.cost_lei_max !== null
              ? `${lei(def.cost_lei_min)} – ${lei(def.cost_lei_max)}`
              : null;
          return { ...m, name: def?.nume ?? m.measure_id, cost };
        }),
      }));
  });

  protected print(): void {
    window.print();
  }
}
