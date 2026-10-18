import { Injectable } from '@angular/core';
import { environment } from '../../../environments/environment';
import { Crosswalk, VisionFrame } from '../models/live-vision';
import { VISION_ENDPOINTS } from './endpoints';

export class VisionApiError extends Error {
  constructor(readonly status: number, readonly code: string, message: string) { super(message); }
}

@Injectable({ providedIn: 'root' })
export class VisionApi {
  private readonly base = environment.api.baseUrl.replace(/\/$/, '');

  async open(cameraId: string, crosswalks: Crosswalk[], signal: AbortSignal): Promise<string> {
    const result = await this.request<{ session_id: string }>(VISION_ENDPOINTS.sessions, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ camera_id: cameraId, crosswalks }), signal,
    });
    return result.session_id;
  }

  frame(session: string, jpeg: Blob, sequence: number, mediaTime: number, signal: AbortSignal): Promise<VisionFrame> {
    const query = new URLSearchParams({ sequence: String(sequence), media_time: String(mediaTime) });
    return this.request(`${VISION_ENDPOINTS.frames(session)}?${query}`, {
      method: 'POST', headers: { 'Content-Type': 'image/jpeg' }, body: jpeg, signal,
    });
  }

  close(session: string): void {
    void fetch(this.base + VISION_ENDPOINTS.session(session), { method: 'DELETE', keepalive: true }).catch(() => undefined);
  }

  private async request<T>(path: string, init: RequestInit): Promise<T> {
    const response = await fetch(this.base + path, { ...init, cache: 'no-store' });
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      if (response.status === 404 && !body?.detail?.code) {
        throw new VisionApiError(404, 'vision_endpoint_missing', 'Backend-ul pornit nu are modulul de detecție. Repornește backend-ul Python (npm run backend), apoi apasă Reîncearcă.');
      }
      throw new VisionApiError(response.status, body?.detail?.code ?? 'vision_unavailable', body?.detail?.message ?? 'Backend-ul de detecție nu este disponibil. Pornește serverul Python și verifică conexiunea.');
    }
    return response.json() as Promise<T>;
  }
}
