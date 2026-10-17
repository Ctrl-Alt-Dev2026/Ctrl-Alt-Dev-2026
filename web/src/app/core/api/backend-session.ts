import { Injectable, signal } from '@angular/core';
import { environment } from '../../../environments/environment';
import { DataMode } from '../models/publication';
import { ENDPOINTS } from './endpoints';

function parameters(): URLSearchParams {
  const current = new URL(window.location.href);
  const hashParams = new URLSearchParams(current.hash.split('?')[1] ?? '');
  for (const key of ['data_mode', 'snapshot_id']) {
    if (!current.searchParams.has(key) && hashParams.has(key)) current.searchParams.set(key, hashParams.get(key)!);
  }
  return current.searchParams;
}

@Injectable({ providedIn: 'root' })
export class BackendSession {
  readonly apiBase = environment.api.baseUrl.replace(/\/$/, '');
  readonly dataMode = signal<DataMode>(parameters().get('data_mode') === 'synthetic' ? 'synthetic' : 'observed');
  // An explicit URL pin is distinct from the version currently displayed.
  readonly requestedSnapshotId = signal<string | null>(parameters().get('snapshot_id'));
  readonly snapshotId = signal<string | null>(this.requestedSnapshotId());

  setDataMode(mode: DataMode): void {
    this.dataMode.set(mode);
    this.requestedSnapshotId.set(null);
    this.snapshotId.set(null);
    const url = new URL(window.location.href);
    url.searchParams.set('data_mode', mode);
    url.searchParams.delete('snapshot_id');
    const [route, query] = url.hash.split('?');
    if (query) {
      const params = new URLSearchParams(query);
      params.delete('data_mode');
      params.delete('snapshot_id');
      url.hash = route + (params.size ? '?' + params.toString() : '');
    }
    history.replaceState(history.state, '', url);
  }

  pinSnapshot(id: string): void {
    this.requestedSnapshotId.set(id);
    this.snapshotId.set(id);
    const url = new URL(window.location.href);
    url.searchParams.set('data_mode', this.dataMode());
    url.searchParams.set('snapshot_id', id);
    this.removeHashSnapshotPin(url);
    history.replaceState(history.state, '', url);
  }

  clearSnapshotPin(): void {
    this.requestedSnapshotId.set(null);
    this.snapshotId.set(null);
    const url = new URL(window.location.href);
    url.searchParams.delete('snapshot_id');
    this.removeHashSnapshotPin(url);
    history.replaceState(history.state, '', url);
  }

  private removeHashSnapshotPin(url: URL): void {
    const [route, query] = url.hash.split('?');
    if (!query) return;
    const params = new URLSearchParams(query);
    params.delete('snapshot_id');
    url.hash = route + (params.size ? '?' + params.toString() : '');
  }

  exportUrl(locationId: string, format: 'json' | 'html'): string {
    const snapshot = this.snapshotId();
    if (!snapshot) return '';
    const query = new URLSearchParams({ data_mode: this.dataMode(), snapshot_id: snapshot, format });
    return `${this.apiBase}${ENDPOINTS.locationExport.http(locationId)}?${query}`;
  }
}
