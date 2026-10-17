import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { environment } from '../../../environments/environment';
import { Camera } from '../models/camera';
import { Accident, CrossingCollection, Hotspot, Manifest, Measure } from '../models/contract';
import { ExtractionResult, ExtractRequest, ReviewRequest } from '../models/extraction';
import { DataApi } from './data-api';
import { ENDPOINTS } from './endpoints';

@Injectable()
export class HttpDataApi extends DataApi {
  private readonly http = inject(HttpClient);
  private readonly base = environment.api.baseUrl;

  manifest() {
    return this.http.get<Manifest>(this.base + ENDPOINTS.manifest.http);
  }
  accidents() {
    return this.http.get<Accident[]>(this.base + ENDPOINTS.accidents.http);
  }
  hotspots() {
    return this.http.get<Hotspot[]>(this.base + ENDPOINTS.hotspots.http);
  }
  crossings() {
    return this.http.get<CrossingCollection>(this.base + ENDPOINTS.crossings.http);
  }
  measures() {
    return this.http.get<Measure[]>(this.base + ENDPOINTS.measures.http);
  }
  cameras() {
    return this.http.get<Camera[]>(this.base + ENDPOINTS.cameras.http);
  }
  extract(req: ExtractRequest) {
    return this.http.post<ExtractionResult>(this.base + ENDPOINTS.extract.http, req);
  }
  review(eventId: string, req: ReviewRequest) {
    return this.http.post<Accident>(this.base + ENDPOINTS.review.http(eventId), req);
  }
}
