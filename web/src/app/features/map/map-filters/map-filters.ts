import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { participantLabel } from '../../../core/format/labels';
import { SOURCE_LABEL, StreetMetric } from '../../../core/models/streets';
import { DataStore } from '../../../core/state/data.store';

@Component({
  selector: 'app-map-filters',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './map-filters.html',
  styleUrl: './map-filters.scss',
})
export class MapFilters {
  protected readonly store = inject(DataStore);
  protected readonly metrics: StreetMetric[] = ['isu', 'presa', 'pmud'];
  protected readonly sourceLabel = SOURCE_LABEL;
  protected readonly participantLabel = participantLabel;

  protected setParticipant(event: Event): void {
    this.store.participant.set((event.target as HTMLSelectElement).value || null);
  }
}
