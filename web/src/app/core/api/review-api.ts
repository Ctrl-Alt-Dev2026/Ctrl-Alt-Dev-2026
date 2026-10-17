import { HttpClient, HttpErrorResponse, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import {
  Candidate, CandidateCorrection, CandidateDecision, GeocodingProposal,
  ImportArticleRequest, ImportRecord, PublicationContext, PublicationPreview,
  PublicationRequest, ReviewDataMode, ReviewedEvent,
} from '../models/review';
import { BACKEND_ENDPOINTS } from './endpoints';

/** Local operator facade. These actions never fall back to fixture or mock writes. */
@Injectable({ providedIn: 'root' })
export class ReviewApi {
  private readonly http = inject(HttpClient);
  readonly writable = environment.api.mode === 'http';
  private url(path: string): string { return `${environment.api.baseUrl}${path}`; }
  private mode(mode: ReviewDataMode): HttpParams { return new HttpParams().set('data_mode', mode); }

  imports(body: ImportArticleRequest): Observable<{ import: ImportRecord; reused: boolean; persisted: boolean }> {
    return this.http.post<{ import: ImportRecord; reused: boolean; persisted: boolean }>(this.url(BACKEND_ENDPOINTS.imports), body);
  }
  import(id: string, mode: ReviewDataMode): Observable<{ import: ImportRecord }> {
    return this.http.get<{ import: ImportRecord }>(this.url(BACKEND_ENDPOINTS.import(id)), { params: this.mode(mode) });
  }
  candidates(mode: ReviewDataMode): Observable<{ candidates: Candidate[] }> {
    return this.http.get<{ candidates: Candidate[] }>(this.url(BACKEND_ENDPOINTS.candidates), { params: this.mode(mode) });
  }
  candidate(id: string, mode: ReviewDataMode): Observable<{ candidate: Candidate }> {
    return this.http.get<{ candidate: Candidate }>(this.url(BACKEND_ENDPOINTS.candidate(id)), { params: this.mode(mode) });
  }
  correct(id: string, body: CandidateCorrection): Observable<{ candidate: Candidate }> {
    return this.http.patch<{ candidate: Candidate }>(this.url(BACKEND_ENDPOINTS.candidate(id)), body);
  }
  decide(id: string, body: CandidateDecision): Observable<{ candidate: Candidate; event: ReviewedEvent | null }> {
    return this.http.post<{ candidate: Candidate; event: ReviewedEvent | null }>(this.url(BACKEND_ENDPOINTS.candidateReview(id)), body);
  }
  events(mode: ReviewDataMode): Observable<{ events: ReviewedEvent[] }> {
    return this.http.get<{ events: ReviewedEvent[] }>(this.url(BACKEND_ENDPOINTS.reviewedEvents), { params: this.mode(mode) });
  }
  geocodingPreview(id: string, mode: ReviewDataMode, version: number): Observable<{ proposal: GeocodingProposal }> {
    return this.http.post<{ proposal: GeocodingProposal }>(this.url(BACKEND_ENDPOINTS.geocodingPreview(id)), { data_mode: mode, expected_version: version });
  }
  geocodingApply(id: string, mode: ReviewDataMode, version: number, suggestionId: string, operator: string, reason: string): Observable<{ candidate: Candidate }> {
    return this.http.post<{ candidate: Candidate }>(this.url(BACKEND_ENDPOINTS.geocodingApply(id)), {
      data_mode: mode, expected_version: version, suggestion_id: suggestionId, operator, reason, location_checked: true,
    });
  }
  context(mode: ReviewDataMode, query: string, offset = 0): Observable<PublicationContext> {
    return this.http.get<PublicationContext>(this.url(BACKEND_ENDPOINTS.publicationContext), {
      params: this.mode(mode).set('q', query).set('offset', offset).set('limit', 30),
    });
  }
  preview(body: PublicationRequest): Observable<PublicationPreview> {
    return this.http.post<PublicationPreview>(this.url(BACKEND_ENDPOINTS.publicationPreview), body);
  }
  publish(body: PublicationRequest): Observable<{ snapshot: { snapshot_id: string }; reused: boolean }> {
    return this.http.post<{ snapshot: { snapshot_id: string }; reused: boolean }>(this.url(BACKEND_ENDPOINTS.publications), body);
  }
}

export function reviewError(error: unknown): string {
  if (error instanceof HttpErrorResponse) {
    const detail: unknown = error.error?.detail;
    const prefix = error.status === 409 ? 'Versiune schimbată. Recitește datele înainte de altă decizie. '
      : error.status === 503 ? 'Serviciul sau datele nu sunt disponibile; nu folosim rezultate simulate. '
      : error.status === 0 ? 'API-ul local nu răspunde. Verifică serverul și proxy-ul. ' : '';
    if (typeof detail === 'string') return prefix + detail;
    if (Array.isArray(detail)) return prefix + detail.map((item) => `${item.loc?.join('.') ?? 'cerere'}: ${item.msg ?? 'valoare invalidă'}`).join(' · ');
    if (detail && typeof detail === 'object' && 'message' in detail) return prefix + String(detail.message);
    if (error.error?.extraction?.errors) return prefix + JSON.stringify(error.error.extraction.errors);
    return prefix + `Cererea a eșuat (HTTP ${error.status}).`;
  }
  return error instanceof Error ? error.message : 'Cererea nu a putut fi finalizată.';
}
