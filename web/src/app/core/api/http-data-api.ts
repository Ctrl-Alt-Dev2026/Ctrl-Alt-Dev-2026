import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { map, throwError } from 'rxjs';
import { environment } from '../../../environments/environment';
import { Camera } from '../models/camera';
import { ExtractRequest, ReviewRequest } from '../models/extraction';
import { LocationDossierPayload, projectPublication, PublicationSnapshot } from '../models/publication';
import { BackendSession } from './backend-session';
import { DataApi } from './data-api';
import { ENDPOINTS } from './endpoints';

@Injectable()
export class HttpDataApi extends DataApi {
  private readonly http = inject(HttpClient);
  private readonly base = environment.api.baseUrl;
  private readonly session = inject(BackendSession);

  loadDataset() {
    const mode = this.session.dataMode();
    const snapshotId = this.session.requestedSnapshotId();
    const path = snapshotId ? ENDPOINTS.publication.http(snapshotId) : ENDPOINTS.publicationLatest.http;
    return this.http.get<PublicationSnapshot>(this.base + path, { params: { data_mode: mode } }).pipe(
      map((snapshot) => {
        if (snapshot.schema_version !== 'publication-1' || snapshot.data_mode !== mode ||
            (snapshotId !== null && snapshot.snapshot_id !== snapshotId)) {
          throw new Error('Publicația primită nu corespunde modului sau versiunii solicitate.');
        }
        return projectPublication(snapshot);
      }),
    );
  }

  dossier(locationId: string) {
    const snapshotId = this.session.snapshotId();
    if (!snapshotId) return throwError(() => new Error('Nu există o versiune publicată selectată.'));
    return this.http.get<LocationDossierPayload>(this.base + ENDPOINTS.locationDossier.http(locationId), {
      params: { data_mode: this.session.dataMode(), snapshot_id: snapshotId },
    });
  }

  manifest() {
    return this.loadDataset().pipe(map((data) => data.manifest));
  }
  accidents() {
    return this.loadDataset().pipe(map((data) => data.accidents));
  }
  hotspots() {
    return this.loadDataset().pipe(map((data) => data.hotspots));
  }
  crossings() {
    return this.loadDataset().pipe(map((data) => data.crossings));
  }
  measures() {
    return this.loadDataset().pipe(map((data) => data.measures));
  }
  cameras() {
    // Public camera metadata is a separate static source, never an accident-data fallback.
    return this.http.get<Camera[]>(ENDPOINTS.cameras.mock);
  }
  extract(_req: ExtractRequest) {
    return throwError(() => new Error('Folosește importul cu verificare și proveniență al backend-ului.'));
  }
  review(_eventId: string, _req: ReviewRequest) {
    return throwError(() => new Error('Aprobarea se face pe candidatul versionat; publicarea este un pas separat.'));
  }
}
