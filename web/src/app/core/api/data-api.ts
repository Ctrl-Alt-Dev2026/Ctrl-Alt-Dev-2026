import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { environment } from '../../../environments/environment';
import { Camera } from '../models/camera';
import { LiveDataset, LiveStatus } from '../models/live';
import { ENDPOINTS } from './endpoints';

// The only way components reach data: the backend's collected dataset, shared by every viewer.
@Injectable({ providedIn: 'root' })
export class DataApi {
  private readonly http = inject(HttpClient);
  private readonly base = environment.api.baseUrl;

  status() {
    return this.http.get<LiveStatus>(this.base + ENDPOINTS.liveStatus);
  }
  dataset() {
    return this.http.get<LiveDataset>(this.base + ENDPOINTS.liveDataset);
  }
  // Public webcam list: static configuration shipped with the UI, not accident data.
  cameras() {
    return this.http.get<Camera[]>(ENDPOINTS.cameras);
  }
}
