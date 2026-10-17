import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { DataApi } from '../../../core/api/data-api';
import { CAUZA, GRAVITATE, PRECIZIE } from '../../../core/format/labels';
import { Accident, CauzaRaportata, Gravitate, PrecizieLoc } from '../../../core/models/contract';
import { ExtractionResult } from '../../../core/models/extraction';
import { DataStore } from '../../../core/state/data.store';
import { EvidenceText } from '../evidence-text/evidence-text';

type Step = 'input' | 'extracting' | 'review' | 'saving' | 'error';

const FIELD_LABELS: Record<string, string> = {
  data_eveniment: 'data',
  ora: 'ora',
  loc_text: 'locul',
  precizie_loc: 'precizia locului',
  participanti: 'participanți',
  cauza_raportata: 'cauza relatată',
  gravitate: 'gravitatea',
  noapte: 'noaptea',
};

// Screen 3 (Planificare.md §1): article → AI extraction with evidence → human correction → map.
@Component({
  selector: 'app-import-page',
  imports: [ReactiveFormsModule, EvidenceText],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './import-page.html',
  styleUrl: './import-page.scss',
})
export class ImportPage {
  private readonly api = inject(DataApi);
  private readonly store = inject(DataStore);
  private readonly router = inject(Router);

  protected readonly step = signal<Step>('input');
  protected readonly error = signal<string | null>(null);
  protected readonly result = signal<ExtractionResult | null>(null);
  protected readonly activeField = signal<string | null>(null);

  protected readonly labels = FIELD_LABELS;
  protected readonly gravitate = Object.entries(GRAVITATE) as [Gravitate, string][];
  protected readonly precizie = Object.entries(PRECIZIE) as [PrecizieLoc, string][];
  protected readonly cauze = Object.entries(CAUZA) as [CauzaRaportata, string][];

  protected readonly source = new FormGroup({
    url: new FormControl('', { nonNullable: true }),
    text: new FormControl('', { nonNullable: true }),
  });

  // Empty string in the form means "unknown" and is saved as null.
  protected readonly fields = new FormGroup({
    data_eveniment: new FormControl('', { nonNullable: true }),
    ora: new FormControl('', { nonNullable: true }),
    loc_text: new FormControl('', { nonNullable: true }),
    precizie_loc: new FormControl<PrecizieLoc>('vag', { nonNullable: true }),
    participanti: new FormControl('', { nonNullable: true }),
    cauza_raportata: new FormControl('', { nonNullable: true }),
    gravitate: new FormControl<Gravitate>('necunoscut', { nonNullable: true }),
    noapte: new FormControl('', { nonNullable: true }),
  });

  protected readonly evidenceFor = (field: string) => this.result()?.dovezi[field] ?? null;
  protected readonly hasLocation = computed(() => this.result()?.localizare_propusa != null);

  protected extract(): void {
    const { url, text } = this.source.getRawValue();
    this.step.set('extracting');
    this.error.set(null);
    this.api.extract({ url: url || undefined, text: text || undefined }).subscribe({
      next: (r) => {
        this.result.set(r);
        const c = r.campuri;
        this.fields.setValue({
          data_eveniment: c.data_eveniment ?? '',
          ora: c.ora ?? '',
          loc_text: c.loc_text ?? '',
          precizie_loc: r.localizare_propusa?.precizie_loc ?? c.precizie_loc ?? 'vag',
          participanti: (c.participanti ?? []).join(', '),
          cauza_raportata: c.cauza_raportata ?? '',
          gravitate: c.gravitate ?? 'necunoscut',
          noapte: c.noapte === null || c.noapte === undefined ? '' : String(c.noapte),
        });
        this.step.set('review');
      },
      error: (e: Error) => this.fail(e),
    });
  }

  protected approve(): void {
    const r = this.result();
    if (!r) return;
    const f = this.fields.getRawValue();
    const loc = r.localizare_propusa;
    const event: Accident = {
      event_id: `ev-import-${this.store.accidents().length + 1}`,
      article_ids: [],
      urls: r.article.url ? [r.article.url] : [],
      data_eveniment: f.data_eveniment || null,
      ora: f.ora || null,
      loc_text: f.loc_text,
      precizie_loc: f.precizie_loc,
      lat: loc?.lat ?? null,
      lon: loc?.lon ?? null,
      in_iasi: loc ? true : null,
      participanti: f.participanti.split(',').map((p) => p.trim()).filter(Boolean),
      cauza_raportata: (f.cauza_raportata || null) as CauzaRaportata | null,
      gravitate: f.gravitate,
      noapte: f.noapte === '' ? null : f.noapte === 'true',
      dovezi: r.dovezi,
      verificat: true,
    };
    this.step.set('saving');
    this.api.review(event.event_id, { decision: 'approve', corrections: event }).subscribe({
      next: (saved) => {
        const full = { ...event, ...saved };
        this.store.upsertAccident(full);
        this.store.lastAdded.set(full);
        this.router.navigate(['/']);
      },
      error: (e: Error) => this.fail(e),
    });
  }

  protected reset(): void {
    this.result.set(null);
    this.source.reset();
    this.error.set(null);
    this.step.set('input');
  }

  private fail(e: Error): void {
    this.error.set(e.message);
    this.step.set(this.result() ? 'review' : 'error');
  }
}
