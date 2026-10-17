import { ChangeDetectionStrategy, Component, computed, input, output } from '@angular/core';

interface Segment {
  text: string;
  field: string | null;
}

// Article text with each field's evidence quote highlighted and tagged with the field's label.
@Component({
  selector: 'app-evidence-text',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <!-- Kept on one line: template whitespace would otherwise add spaces around the highlights. -->
    <p class="text">@for (s of segments(); track $index) {@if (s.field) {<mark [class.active]="s.field === active()" (mouseenter)="hover.emit(s.field)" (mouseleave)="hover.emit(null)">{{ s.text }}<sup>{{ labels()[s.field] || s.field }}</sup></mark>} @else {{{ s.text }}}}</p>
    @if (missing().length > 0) {
      <p class="missing">Dovezi negăsite în text pentru: {{ missing().join(', ') }}. Verifică aceste câmpuri manual.</p>
    }
  `,
  styles: `
    .text {
      margin: 0;
      font-size: var(--step-1);
      line-height: 1.7;
      max-width: 62ch;
    }
    mark {
      color: inherit;
      background: rgb(143 211 255 / 0.16);
      border-bottom: 0.125rem solid var(--accent);
      border-radius: 0.2rem;
      padding: 0 0.15em;
      transition: background 0.2s;
      &.active {
        background: rgb(143 211 255 / 0.38);
      }
    }
    sup {
      margin-left: 0.3em;
      font-size: 0.62em;
      font-weight: 700;
      color: var(--accent);
    }
    .missing {
      margin: var(--space-3) 0 0;
      font-size: var(--step--1);
      color: var(--unknown);
    }
  `,
})
export class EvidenceText {
  readonly text = input.required<string>();
  readonly evidence = input.required<Record<string, string>>();
  readonly labels = input<Record<string, string>>({});
  readonly active = input<string | null>(null);
  readonly hover = output<string | null>();

  private readonly located = computed(() => {
    const text = this.text();
    return Object.entries(this.evidence())
      .map(([field, quote]) => ({ field, start: text.indexOf(quote), end: text.indexOf(quote) + quote.length }))
      .filter((m) => m.start >= 0)
      .sort((a, b) => a.start - b.start);
  });

  protected readonly missing = computed(() => {
    const found = new Set(this.located().map((m) => m.field));
    return Object.keys(this.evidence())
      .filter((f) => !found.has(f))
      .map((f) => this.labels()[f] || f);
  });

  // Overlapping quotes keep the first one; the later field still appears in its own row on the right.
  protected readonly segments = computed<Segment[]>(() => {
    const text = this.text();
    const out: Segment[] = [];
    let at = 0;
    for (const m of this.located()) {
      if (m.start < at) continue;
      if (m.start > at) out.push({ text: text.slice(at, m.start), field: null });
      out.push({ text: text.slice(m.start, m.end), field: m.field });
      at = m.end;
    }
    if (at < text.length) out.push({ text: text.slice(at), field: null });
    return out;
  });
}
