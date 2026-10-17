import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

const BAR = 10;
const GAP = 2;
const H = 64;

// 24 bars from hotspot.pe_ore. Events with an unknown hour are reported, not placed.
@Component({
  selector: 'app-hour-chart',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './hour-chart.html',
  styleUrl: './hour-chart.scss',
})
export class HourChart {
  readonly hours = input.required<number[]>();
  readonly unknownCount = input(0);

  protected readonly width = 24 * (BAR + GAP);
  protected readonly height = H + 18;
  protected readonly ticks = [0, 6, 12, 18];

  protected readonly bars = computed(() => {
    const values = this.hours();
    const max = Math.max(1, ...values);
    return values.map((v, hour) => {
      const h = v === 0 ? 0 : Math.max(4, (v / max) * H);
      return { hour, v, x: hour * (BAR + GAP), y: H - h, h, label: `${String(hour).padStart(2, '0')}:00–${String(hour).padStart(2, '0')}:59: ${v} evenimente` };
    });
  });

  protected readonly x = (hour: number) => hour * (BAR + GAP);
  protected readonly bar = BAR;
  protected readonly base = H;
}
