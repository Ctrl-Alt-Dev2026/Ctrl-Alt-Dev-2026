import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { dateRo, GRAVITATE, participantLabel, PRECISE } from '../../../core/format/labels';
import { Accident } from '../../../core/models/contract';
import { SOURCE_LABEL, StreetMetric } from '../../../core/models/streets';
import { DataStore } from '../../../core/state/data.store';

// Streets ranked by one source at a time: ISU interventions, press reports, or IPJ totals from PMUD (2020–2021).
@Component({
  selector: 'app-street-panel',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './street-panel.html',
  styleUrl: './street-panel.scss',
})
export class StreetPanel {
  protected readonly store = inject(DataStore);
  protected readonly dateRo = dateRo;
  protected readonly gravitate = GRAVITATE;
  protected readonly participantLabel = participantLabel;
  protected readonly precise = PRECISE;
  protected readonly metrics: StreetMetric[] = ['isu', 'presa', 'pmud'];
  protected readonly sourceLabel = SOURCE_LABEL;

  protected readonly max = computed(() =>
    Math.max(1, ...this.store.rankedStreets().map((f) => this.store.streetValue().get(f.properties.id) ?? 0)),
  );
  protected readonly sources = computed(() => this.store.manifest()?.surse ?? []);

  protected setMetric(metric: StreetMetric): void {
    this.store.streetMetric.set(metric);
  }

  protected value(id: string): number {
    return this.store.streetValue().get(id) ?? 0;
  }

  protected count(id: string): number {
    return this.store.streetCount().get(id) ?? 0;
  }

  protected linkLabel(a: Accident, i: number): string {
    const what = a.sursa_tip === 'presa' ? 'articol' : 'comunicat';
    return a.urls.length === 1 ? `${what} (${a.sursa ?? 'sursă'})` : `${what} ${i + 1}`;
  }

  // "Posibil același accident" links point across sources; they are shown, never merged.
  protected sameAs(a: Accident): string | null {
    const other = a.posibil_acelasi_cu;
    if (!other?.length) return null;
    return a.sursa_tip === 'presa' ? 'posibil același accident ca o intervenție ISU' : 'posibil relatat și în presă';
  }
}
