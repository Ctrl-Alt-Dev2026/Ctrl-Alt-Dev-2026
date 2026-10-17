import { ChangeDetectionStrategy, Component, computed, inject, input, output } from '@angular/core';
import { Hotspot } from '../../../core/models/contract';
import { DataStore } from '../../../core/state/data.store';
import { ScoreBadge } from '../../../shared/score-badge/score-badge';

@Component({
  selector: 'app-hotspot-list',
  imports: [ScoreBadge],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './hotspot-list.html',
  styleUrl: './hotspot-list.scss',
})
export class HotspotList {
  private readonly store = inject(DataStore);

  readonly hotspots = input.required<Hotspot[]>();
  readonly excludedCount = input(0);
  readonly select = output<string>();

  protected readonly max = computed(() => Math.max(1, ...this.hotspots().map((h) => h.scor)));
  // Rank in the full ranking, so filtering by participant doesn't renumber locations.
  protected readonly rankOf = (id: string) => this.store.rankOf().get(id);
  protected readonly measureName = (id: string) => this.store.measureById().get(id)?.nume ?? id;
}
