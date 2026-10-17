import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { delay, map, Observable, of, throwError } from 'rxjs';
import { environment } from '../../../environments/environment';
import { Camera } from '../models/camera';
import { Accident, CrossingCollection, Hotspot, Manifest, Measure } from '../models/contract';
import { ExtractionResult, ExtractRequest, ReviewRequest } from '../models/extraction';
import { DataApi } from './data-api';
import { ENDPOINTS } from './endpoints';

const LATENCY_MS = 1500;

@Injectable()
export class MockDataApi extends DataApi {
  private readonly http = inject(HttpClient);

  manifest() {
    return this.http.get<Manifest>(ENDPOINTS.manifest.mock);
  }
  accidents() {
    return this.http.get<Accident[]>(ENDPOINTS.accidents.mock);
  }
  hotspots() {
    return this.http.get<Hotspot[]>(ENDPOINTS.hotspots.mock);
  }
  crossings() {
    return this.http.get<CrossingCollection>(ENDPOINTS.crossings.mock);
  }
  measures() {
    return this.http.get<Measure[]>(ENDPOINTS.measures.mock);
  }
  cameras() {
    return this.http.get<Camera[]>(ENDPOINTS.cameras.mock);
  }

  // Replays a saved extraction whatever was pasted; the UI labels it as replay and shows the saved article.
  extract(_req: ExtractRequest): Observable<ExtractionResult> {
    if (environment.api.mockFail) return this.fail('Extragerea a eșuat (mock).');
    return this.http.get<ExtractionResult>(ENDPOINTS.extract.mock).pipe(
      map((r) => ({ ...r, mode: 'replay' as const })),
      delay(LATENCY_MS),
    );
  }

  // No backend: echo the corrected event back; the store applies it in memory.
  review(eventId: string, req: ReviewRequest): Observable<Accident> {
    if (environment.api.mockFail) return this.fail('Salvarea a eșuat (mock).');
    const event = { ...req.corrections, event_id: eventId, verificat: req.decision === 'approve' } as Accident;
    return of(event).pipe(delay(LATENCY_MS));
  }

  private fail(message: string): Observable<never> {
    return throwError(() => new Error(message)).pipe(delay(LATENCY_MS));
  }
}
