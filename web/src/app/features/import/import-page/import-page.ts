import { JsonPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, DestroyRef, computed, effect, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { forkJoin, Subscription } from 'rxjs';
import { BackendSession } from '../../../core/api/backend-session';
import { ReviewApi, reviewError } from '../../../core/api/review-api';
import { CAUZA, GRAVITATE, PRECIZIE } from '../../../core/format/labels';
import { CauzaRaportata, Gravitate, PrecizieLoc } from '../../../core/models/contract';
import { Candidate, CandidateFields, GeocodingProposal, ImportArticleRequest, ImportRecord, PublicationContext, PublicationFeature, ReviewedEvent } from '../../../core/models/review';
import { EvidenceText } from '../evidence-text/evidence-text';
import { PublicationPanel } from '../publication-panel/publication-panel';

const control = (value = '', required = false) => new FormControl(value, { nonNullable: true, validators: required ? [Validators.required] : [] });
const FIELD_LABELS: Record<string, string> = {
  data_eveniment: 'data accidentului', ora: 'ora', loc_text: 'locul', precizie_loc: 'precizia locului',
  participanti: 'participanți', cauza_raportata: 'cauza relatată', gravitate: 'gravitatea', noapte: 'noaptea',
};

@Component({
  selector: 'app-import-page',
  imports: [ReactiveFormsModule, JsonPipe, EvidenceText, PublicationPanel],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './import-page.html',
  styleUrl: './import-page.scss',
})
export class ImportPage {
  private readonly api = inject(ReviewApi);
  protected readonly session = inject(BackendSession);
  private readonly destroyRef = inject(DestroyRef);
  protected readonly writable = this.api.writable;
  protected readonly candidates = signal<Candidate[]>([]);
  protected readonly events = signal<ReviewedEvent[]>([]);
  protected readonly selected = signal<Candidate | null>(null);
  protected readonly imported = signal<ImportRecord | null>(null);
  protected readonly proposal = signal<GeocodingProposal | null>(null);
  protected readonly manualContext = signal<PublicationContext | null>(null);
  protected readonly manualQuery = new FormControl('', { nonNullable: true });
  protected readonly busy = signal<string | null>(null);
  protected readonly error = signal<string | null>(null);
  protected readonly notice = signal<string | null>(null);
  protected readonly activeField = signal<string | null>(null);
  protected readonly labels = FIELD_LABELS;
  protected readonly gravitate = Object.entries(GRAVITATE) as [Gravitate, string][];
  protected readonly precizie = Object.entries(PRECIZIE) as [PrecizieLoc, string][];
  protected readonly cauze = Object.entries(CAUZA) as [CauzaRaportata, string][];
  protected readonly pendingCount = computed(() => this.candidates().filter((c) => c.review_status === 'pending').length);
  protected readonly evidence = computed(() => this.selected()?.original_extraction.dovezi ?? {});
  protected readonly processingLabel = computed(() => {
    const mode = this.imported()?.extraction.processing_mode;
    if (mode === 'rules') return 'Extragere prin reguli deterministe; fără model AI';
    if (mode === 'cache' || mode === 'replay') return 'Rezultat salvat (reluare); nu procesare live';
    if (mode === 'live') return 'Extragere AI live la momentul importului; acum este afișat rezultatul arhivat';
    return 'Modul de procesare nu este încă disponibil';
  });
  protected readonly source = new FormGroup({
    article_id: control('', true), sursa: control('', true), url: control('', true), titlu: control('', true),
    text: control('', true), publicat_la: control(), colectat_la: control(new Date().toISOString(), true),
    pipeline: new FormControl<'rules' | 'hybrid'>('rules', { nonNullable: true }),
  });
  protected readonly operator = new FormGroup({ operator: control('', true), note: control('', true) });
  protected readonly checks = new FormGroup({
    source: new FormControl(false, { nonNullable: true }), duplicate: new FormControl(false, { nonNullable: true }),
    location: new FormControl(false, { nonNullable: true }), geocoding: new FormControl(false, { nonNullable: true }),
    manual: new FormControl(false, { nonNullable: true }),
    canonical: control(),
  });
  protected readonly fields = new FormGroup({
    data_eveniment: control(), ora: control(), loc_text: control(), participanti: control(),
    cauza_raportata: control(), gravitate: control('necunoscut'), noapte: control(),
    lat: control(), lon: control(), precizie_loc: control(), in_iasi: control(), location_evidence: control(),
  });
  private epoch = 0;
  private selectionSequence = 0;
  private importDraft: { signature: string; body: ImportArticleRequest } | null = null;
  private importRequest: Subscription | null = null;

  constructor() {
    effect(() => {
      const mode = this.session.dataMode();
      this.importRequest?.unsubscribe(); this.importRequest = null;
      this.epoch++;
      this.selectionSequence++;
      this.selected.set(null); this.imported.set(null); this.proposal.set(null); this.manualContext.set(null);
      this.candidates.set([]); this.events.set([]); this.error.set(null); this.notice.set(null); this.busy.set(null);
      this.importDraft = null;
      this.source.reset({ article_id: '', sursa: mode === 'synthetic' ? 'SINTETIC' : '', url: '', titlu: '', text: '',
        publicat_la: '', colectat_la: new Date().toISOString(), pipeline: 'rules' });
      this.resetChecks();
      if (this.writable) this.refresh();
    });
    this.fields.controls.loc_text.valueChanges.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(() => {
      if (!this.selected()) return;
      // A location edit invalidates the former point and any proposed OSM match.
      this.fields.patchValue({ lat: '', lon: '', precizie_loc: '', in_iasi: '', location_evidence: '' }, { emitEvent: false });
      this.proposal.set(null); this.checks.controls.location.setValue(false); this.checks.controls.geocoding.setValue(false);
    });
    this.fields.valueChanges.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(() => {
      this.checks.controls.source.setValue(false, { emitEvent: false });
      this.checks.controls.duplicate.setValue(false, { emitEvent: false });
      this.checks.controls.location.setValue(false, { emitEvent: false });
      this.proposal.set(null);
    });
  }

  protected refresh(): void {
    const epoch = this.epoch;
    const mode = this.session.dataMode();
    this.busy.set('refresh'); this.error.set(null);
    forkJoin({ candidates: this.api.candidates(mode), events: this.api.events(mode) }).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (result) => {
        if (epoch !== this.epoch) return;
        this.candidates.set(result.candidates.candidates); this.events.set(result.events.events); this.busy.set(null);
      }, error: (error: unknown) => this.fail(error, epoch),
    });
  }

  protected extract(): void {
    if (!this.writable || this.busy() !== null) return;
    const problems = this.importProblems();
    if (problems.length) { this.error.set(problems.join(' ')); return; }
    const epoch = this.epoch;
    const value = this.source.getRawValue();
    const { pipeline, ...article } = value;
    const payload = { data_mode: this.session.dataMode(), operator: this.operator.controls.operator.value.trim(), pipeline, mode: 'extract' as const, article };
    const signature = JSON.stringify(payload);
    if (this.importDraft?.signature !== signature) this.importDraft = { signature, body: { ...payload, request_id: crypto.randomUUID() } };
    this.busy.set('import'); this.error.set(null); this.notice.set(null);
    this.importRequest = this.api.imports(this.importDraft!.body).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (result) => {
        if (epoch !== this.epoch) return;
        this.importRequest = null;
        this.busy.set(null);
        this.notice.set(`${result.reused ? 'Import recitit' : 'Import salvat'}: ${result.import.candidate_ids.length} candidați neaprobați. Niciun eveniment nu a fost publicat.`);
        this.refresh();
        if (result.import.candidate_ids[0]) this.open(result.import.candidate_ids[0]);
      }, error: (error: unknown) => { this.importRequest = null; this.fail(error, epoch); },
    });
  }

  protected importProblems(): string[] {
    const article = this.source.getRawValue();
    const required = { article_id: 'ID articol', sursa: 'Sursa', url: 'URL sursă', titlu: 'Titlul articolului', text: 'Textul integral', colectat_la: 'Colectat la' };
    const missing = Object.entries(required).filter(([key]) => !article[key as keyof typeof required].trim()).map(([, label]) => label);
    if (!this.operator.controls.operator.value.trim()) missing.push('Operator');
    const problems = missing.length ? [`Completează: ${missing.join(', ')}.`] : [];
    if (this.session.dataMode() === 'observed' && article.sursa === 'SINTETIC') {
      problems.push('Articolul este SINTETIC, iar modul selectat este Date observate. Copiază formularul în Demo sintetic înainte de import.');
    }
    return problems;
  }

  protected stopWaitingForImport(): void {
    if (this.busy() !== 'import') return;
    this.importRequest?.unsubscribe(); this.importRequest = null;
    this.busy.set(null);
    this.error.set('Așteptarea a fost oprită în interfață. Serverul poate încă procesa importul. Recitește lista sau reîncearcă formularul neschimbat; cheia cererii este păstrată.');
  }

  protected open(id: string): void {
    const epoch = this.epoch;
    const sequence = ++this.selectionSequence;
    const mode = this.session.dataMode();
    this.busy.set('candidate'); this.error.set(null); this.proposal.set(null); this.imported.set(null); this.manualContext.set(null); this.resetChecks();
    this.api.candidate(id, mode).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: ({ candidate }) => {
        if (epoch !== this.epoch || sequence !== this.selectionSequence) return;
        this.show(candidate); this.busy.set(null);
        this.api.import(candidate.import_id, mode).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
          next: (result) => { if (epoch === this.epoch && sequence === this.selectionSequence) this.imported.set(result.import); },
          error: (error: unknown) => { if (sequence === this.selectionSequence) this.fail(error, epoch); },
        });
      }, error: (error: unknown) => { if (sequence === this.selectionSequence) this.fail(error, epoch); },
    });
  }

  private show(candidate: Candidate): void {
    this.selected.set(candidate); this.proposal.set(null); this.resetChecks();
    const fields = candidate.fields;
    this.fields.setValue({
      data_eveniment: fields.data_eveniment ?? '', ora: fields.ora ?? '', loc_text: fields.loc_text ?? '',
      participanti: fields.participanti.join(', '), cauza_raportata: fields.cauza_raportata ?? '', gravitate: fields.gravitate,
      noapte: fields.noapte === null ? '' : String(fields.noapte), lat: fields.lat === null ? '' : String(fields.lat),
      lon: fields.lon === null ? '' : String(fields.lon), precizie_loc: fields.precizie_loc ?? '',
      in_iasi: fields.in_iasi === null ? '' : String(fields.in_iasi), location_evidence: fields.location_evidence ?? '',
    }, { emitEvent: false });
    this.fields.markAsPristine();
    if (candidate.review_status === 'pending') this.fields.enable({ emitEvent: false }); else this.fields.disable({ emitEvent: false });
  }

  protected save(): void {
    const candidate = this.selected();
    if (!candidate || candidate.review_status !== 'pending' || !this.validOperator()) return;
    const epoch = this.epoch;
    const value = this.fields.getRawValue();
    const nullable = (v: string) => v.trim() || null;
    // Angular's number inputs emit numbers (or null when cleared), even when
    // the form was populated from string values. Empty is unknown, never zero.
    const numeric = (v: string | number | null) => v === null || (typeof v === 'string' && !v.trim()) ? null : Number(v);
    const values: CandidateFields = {
      data_eveniment: nullable(value.data_eveniment), ora: nullable(value.ora), loc_text: nullable(value.loc_text),
      participanti: [...new Set(value.participanti.split(',').map((item) => item.trim()).filter(Boolean))],
      cauza_raportata: nullable(value.cauza_raportata) as CauzaRaportata | null, gravitate: value.gravitate as Gravitate,
      noapte: value.noapte === '' ? null : value.noapte === 'true', lat: numeric(value.lat), lon: numeric(value.lon),
      precizie_loc: nullable(value.precizie_loc) as PrecizieLoc | null,
      in_iasi: value.in_iasi === '' ? null : value.in_iasi === 'true', location_evidence: nullable(value.location_evidence),
    };
    if ([values.lat, values.lon].some((n) => n !== null && !Number.isFinite(n))) { this.error.set('Coordonatele trebuie să fie numere finite sau necunoscute.'); return; }
    const changes = Object.fromEntries(Object.entries(values).filter(([key, value]) => JSON.stringify(value) !== JSON.stringify(candidate.fields[key as keyof CandidateFields]))) as Partial<CandidateFields>;
    if (Object.keys(changes).length === 0) { this.fields.markAsPristine(); this.notice.set('Niciun câmp nu a fost schimbat.'); return; }
    this.busy.set('save'); this.error.set(null);
    this.api.correct(candidate.candidate_id, { data_mode: this.session.dataMode(), expected_version: candidate.version,
      operator: this.operator.controls.operator.value.trim(), reason: this.operator.controls.note.value.trim(), changes }).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: ({ candidate: saved }) => { if (epoch !== this.epoch) return; this.show({ ...saved, article: candidate.article }); this.busy.set(null); this.notice.set('Corecturile sunt salvate, cu motiv și versiune nouă. Verifică din nou înainte de aprobare.'); this.refresh(); },
      error: (error: unknown) => this.fail(error, epoch),
    });
  }

  protected geocode(): void {
    const candidate = this.selected();
    if (!candidate || this.fields.dirty || this.session.dataMode() !== 'observed') return;
    const epoch = this.epoch;
    this.busy.set('geocoding'); this.error.set(null); this.proposal.set(null); this.checks.controls.geocoding.setValue(false);
    this.api.geocodingPreview(candidate.candidate_id, this.session.dataMode(), candidate.version).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: ({ proposal }) => { if (epoch !== this.epoch || this.selected()?.candidate_id !== candidate.candidate_id) return; this.proposal.set(proposal); this.busy.set(null); },
      error: (error: unknown) => this.fail(error, epoch),
    });
  }

  protected applyGeocoding(): void {
    const candidate = this.selected(); const proposal = this.proposal();
    if (!candidate || !proposal || !this.checks.controls.geocoding.value || !this.validOperator() || this.fields.dirty) return;
    const epoch = this.epoch;
    this.busy.set('apply'); this.error.set(null);
    this.api.geocodingApply(candidate.candidate_id, this.session.dataMode(), candidate.version, proposal.suggestion_id,
      this.operator.controls.operator.value.trim(), this.operator.controls.note.value.trim()).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: ({ candidate: saved }) => { if (epoch !== this.epoch) return; this.show({ ...saved, article: candidate.article }); this.busy.set(null); this.notice.set('Localizarea confirmată și raportul OSM sunt salvate în istoric. Evenimentul nu este încă aprobat.'); this.refresh(); },
      error: (error: unknown) => this.fail(error, epoch),
    });
  }

  protected searchManualContext(): void {
    if (this.session.dataMode() !== 'synthetic' || this.selected()?.review_status !== 'pending') return;
    const epoch = this.epoch;
    this.busy.set('manual-context'); this.error.set(null); this.checks.controls.manual.setValue(false);
    this.api.context('synthetic', this.manualQuery.value).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (context) => { if (epoch !== this.epoch) return; this.manualContext.set(context); this.busy.set(null); },
      error: (error: unknown) => this.fail(error, epoch),
    });
  }

  protected useManualContext(feature: PublicationFeature): void {
    if (this.session.dataMode() !== 'synthetic' || this.selected()?.review_status !== 'pending' || !this.checks.controls.manual.value || !this.validOperator()) return;
    const id = feature.properties.id || feature.id;
    if (!id || !['trecere', 'intersectie'].includes(feature.properties.tip ?? '')) {
      this.error.set('Contextul ales nu oferă o trecere sau intersecție precisă.'); return;
    }
    // The operator intentionally selects a same-mode fixture feature. Municipality remains a separate check.
    this.fields.patchValue({ lat: String(feature.geometry.coordinates[1]), lon: String(feature.geometry.coordinates[0]),
      precizie_loc: feature.properties.tip!, location_evidence: `Context sintetic ${id}; selecție manuală de ${this.operator.controls.operator.value.trim()}: ${this.operator.controls.note.value.trim()}`,
    }, { emitEvent: false });
    this.fields.markAsDirty(); this.proposal.set(null); this.resetChecks();
    this.notice.set('Coordonatele contextului sintetic sunt în formular, încă nesalvate. Verifică separat încadrarea în municipiu și salvează corecturile.');
  }

  protected decide(action: 'approve' | 'reject' | 'link'): void {
    const candidate = this.selected();
    if (!candidate || this.fields.dirty || !this.validOperator()) return;
    const checks = this.checks.getRawValue();
    const canonical = this.events().find((item) => item.event_id === checks.canonical);
    if (action !== 'reject' && (!checks.source || !checks.duplicate)) { this.error.set('Confirmă separat sursele și verificarea duplicatelor.'); return; }
    if (action !== 'reject' && (candidate.fields.lat !== null || candidate.fields.in_iasi !== null) && !checks.location) { this.error.set('Confirmă separat verificarea localizării.'); return; }
    if (action === 'link' && !canonical) { this.error.set('Alege evenimentul canonic și verifică versiunea afișată.'); return; }
    const epoch = this.epoch;
    this.busy.set('decision'); this.error.set(null);
    this.api.decide(candidate.candidate_id, { data_mode: this.session.dataMode(), expected_version: candidate.version,
      operator: this.operator.controls.operator.value.trim(), note: this.operator.controls.note.value.trim(), action,
      source_checked: checks.source, duplicate_checked: checks.duplicate, location_checked: checks.location,
      ...(action === 'link' && canonical ? { canonical_event_id: canonical.event_id, expected_event_version: canonical.version } : {}),
    }).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: ({ candidate: saved, event }) => {
        if (epoch !== this.epoch) return;
        this.show({ ...saved, article: candidate.article }); this.busy.set(null);
        this.notice.set(event ? `Decizie salvată. Eveniment canonic ${event.event_id}, versiunea ${event.version}. Publicarea pe hartă este un pas separat mai jos.` : 'Candidatul a fost respins; articolul și istoricul sunt păstrate.'); this.refresh();
      }, error: (error: unknown) => this.fail(error, epoch),
    });
  }

  protected safeUrl(url: string): string | null {
    try { const parsed = new URL(url); return ['http:', 'https:'].includes(parsed.protocol) && !parsed.username && !parsed.password ? url : null; } catch { return null; }
  }
  private validOperator(): boolean {
    if (this.operator.invalid || !this.operator.controls.operator.value.trim() || !this.operator.controls.note.value.trim()) {
      this.error.set('Completează operatorul și motivul verificării/deciziei.'); return false;
    }
    return true;
  }
  private resetChecks(): void { this.checks.reset({ source: false, duplicate: false, location: false, geocoding: false, manual: false, canonical: '' }); }
  private fail(error: unknown, epoch: number): void { if (epoch !== this.epoch) return; this.busy.set(null); this.error.set(reviewError(error)); }
}
