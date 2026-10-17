import { ChangeDetectionStrategy, Component, DestroyRef, effect, inject, input, output, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { BackendSession } from '../../../core/api/backend-session';
import { ReviewApi, reviewError } from '../../../core/api/review-api';
import { PublicationContext, PublicationFeature, PublicationPreview, PublicationRequest, ReviewedEvent } from '../../../core/models/review';
import { DataStore } from '../../../core/state/data.store';

interface Association { location_id: string; note: string; checked: boolean }
const field = () => new FormControl('', { nonNullable: true, validators: [Validators.required] });

@Component({
  selector: 'app-publication-panel', imports: [ReactiveFormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './publication-panel.html', styleUrl: './publication-panel.scss',
})
export class PublicationPanel {
  readonly events = input.required<ReviewedEvent[]>();
  readonly refreshRequested = output<void>();
  protected readonly session = inject(BackendSession);
  private readonly api = inject(ReviewApi);
  private readonly store = inject(DataStore);
  private readonly destroyRef = inject(DestroyRef);
  protected readonly selections = signal<Record<string, Association>>({});
  protected readonly context = signal<PublicationContext | null>(null);
  protected readonly preview = signal<PublicationPreview | null>(null);
  protected readonly error = signal<string | null>(null);
  protected readonly contextError = signal<string | null>(null);
  protected readonly notice = signal<string | null>(null);
  protected readonly busy = signal<string | null>(null);
  protected readonly query = new FormControl('', { nonNullable: true });
  protected readonly form = new FormGroup({
    operator: field(), note: field(), period_start: field(), period_end: field(),
    source_conflicts_checked: new FormControl(false, { nonNullable: true }),
  });
  private epoch = 0;
  private revision = 0;
  private requestDraft: { signature: string; body: PublicationRequest } | null = null;
  private previewSignature: string | null = null;

  constructor() {
    effect(() => {
      this.session.dataMode();
      this.events();
      this.epoch++;
      this.selections.set({}); this.context.set(null); this.preview.set(null); this.error.set(null); this.contextError.set(null); this.notice.set(null); this.busy.set(null);
      this.requestDraft = null; this.previewSignature = null;
      this.form.controls.source_conflicts_checked.setValue(false, { emitEvent: false });
    });
    this.form.valueChanges.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(() => this.invalidate());
  }

  protected selected(id: string): Association | undefined { return this.selections()[id]; }
  protected toggle(id: string, event: Event): void {
    const checked = (event.target as HTMLInputElement).checked;
    this.selections.update((items) => {
      const next = { ...items };
      if (checked) next[id] = { location_id: '', note: '', checked: false }; else delete next[id];
      return next;
    });
    this.invalidate();
  }
  protected change(id: string, key: 'location_id' | 'note', event: Event): void {
    const value = (event.target as HTMLInputElement).value;
    this.selections.update((items) => ({ ...items, [id]: { ...items[id], [key]: value, checked: false } }));
    this.invalidate();
  }
  protected confirm(id: string, event: Event): void {
    const checked = (event.target as HTMLInputElement).checked;
    this.selections.update((items) => ({ ...items, [id]: { ...items[id], checked } })); this.invalidate();
  }
  protected contextId(feature: PublicationFeature): string { return feature.properties.id || feature.id || ''; }
  protected contextLabel(feature: PublicationFeature): string {
    return `${this.contextId(feature)} · ${feature.properties.nume || 'Nume necunoscut'} · ${feature.geometry.coordinates[1]}, ${feature.geometry.coordinates[0]}`;
  }
  protected searchContext(offset = 0): void {
    const epoch = this.epoch;
    this.busy.set('context'); this.contextError.set(null);
    this.api.context(this.session.dataMode(), this.query.value, offset).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (context) => { if (epoch !== this.epoch) return; this.context.set(context); this.busy.set(null); },
      error: (error: unknown) => { if (epoch !== this.epoch) return; this.contextError.set(reviewError(error)); this.context.set(null); this.busy.set(null); },
    });
  }

  protected checkPublication(): void {
    const body = this.body();
    if (!body) return;
    const epoch = this.epoch; const revision = this.revision; const signature = this.requestDraft!.signature;
    this.busy.set('preview'); this.error.set(null); this.preview.set(null); this.previewSignature = null;
    this.api.preview(body).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (preview) => {
        if (epoch !== this.epoch || revision !== this.revision) return;
        this.busy.set(null); this.preview.set(preview); this.previewSignature = signature;
      }, error: (error: unknown) => this.fail(error, epoch),
    });
  }

  protected publish(): void {
    const body = this.body(); const preview = this.preview();
    if (!body || !preview || preview.excluded_event_count !== 0 || preview.eligible_event_count < 1 || this.previewSignature !== this.requestDraft?.signature) {
      this.error.set('Rulează un preview eligibil pentru exact această selecție înainte de publicare.'); return;
    }
    const epoch = this.epoch;
    this.busy.set('publish'); this.error.set(null);
    this.api.publish(body).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (result) => {
        if (epoch !== this.epoch) return;
        this.busy.set(null); this.notice.set(`${result.reused ? 'Publicație recitită' : 'Publicație salvată'}: ${result.snapshot.snapshot_id}. Harta și exportul folosesc această versiune.`);
        this.session.pinSnapshot(result.snapshot.snapshot_id);
        this.store.load();
      }, error: (error: unknown) => this.fail(error, epoch),
    });
  }

  protected canPublish(): boolean {
    const preview = this.preview();
    return !!preview && preview.excluded_event_count === 0 && preview.eligible_event_count > 0 && this.previewSignature === this.requestDraft?.signature;
  }
  private body(): PublicationRequest | null {
    const values = this.form.getRawValue();
    const rows = Object.entries(this.selections());
    if (this.form.invalid || !values.operator.trim() || !values.note.trim() || !values.source_conflicts_checked || !rows.length || rows.length > 200) {
      this.error.set('Completează operatorul, nota, perioada, verificarea conflictelor și selectează 1–200 de evenimente.'); return null;
    }
    const selections = rows.map(([event_id, association]) => {
      const event = this.events().find((item) => item.event_id === event_id);
      if (!event || !association.location_id.trim() || !association.note.trim() || !association.checked) return null;
      return { event_id, expected_version: event.version, location_id: association.location_id.trim(), association_note: association.note.trim(), association_checked: true as const };
    });
    if (selections.some((selection) => selection === null)) { this.error.set('Pentru fiecare eveniment ales, completează ID-ul locației, motivul asocierii și confirmă verificarea.'); return null; }
    const payload = { data_mode: this.session.dataMode(), operator: values.operator.trim(), note: values.note.trim(),
      period_start: values.period_start, period_end: values.period_end, source_conflicts_checked: true as const,
      selections: selections.filter((selection) => selection !== null),
    };
    const signature = JSON.stringify(payload);
    if (this.requestDraft?.signature !== signature) this.requestDraft = { signature, body: { ...payload, request_id: crypto.randomUUID() } };
    return this.requestDraft!.body;
  }
  private invalidate(): void { this.revision++; this.preview.set(null); this.previewSignature = null; this.notice.set(null); }
  private fail(error: unknown, epoch: number): void { if (epoch !== this.epoch) return; this.busy.set(null); this.error.set(reviewError(error)); }
}
