import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

// Colour shows the score relative to the highest one; the number is always printed.
export function severityVar(score: number, max: number): string {
  const r = max > 0 ? score / max : 0;
  return r > 0.6 ? 'var(--heat-4)' : r > 0.3 ? 'var(--heat-3)' : 'var(--heat-2)';
}

@Component({
  selector: 'app-score-badge',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<span class="badge" [style.background]="color()"><span class="sr-only">scor </span>{{ score() }}</span>`,
  styles: `
    .badge {
      display: inline-block;
      min-width: 2.2em;
      padding: 0.1em 0.45em;
      border-radius: var(--radius-s);
      text-align: center;
      font-size: var(--step-1);
      font-weight: 700;
      font-stretch: 75%;
      color: #100c06;
    }
  `,
})
export class ScoreBadge {
  readonly score = input.required<number>();
  readonly max = input.required<number>();
  protected readonly color = computed(() => severityVar(this.score(), this.max()));
}
