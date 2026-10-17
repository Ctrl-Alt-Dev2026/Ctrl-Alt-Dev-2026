import { Observable } from 'rxjs';
import { Camera } from '../models/camera';
import { Accident, CrossingCollection, Hotspot, Manifest, Measure } from '../models/contract';
import { ExtractionResult, ExtractRequest, ReviewRequest } from '../models/extraction';

// The only way components reach data. Implementations: MockDataApi, HttpDataApi.
export abstract class DataApi {
  abstract manifest(): Observable<Manifest>;
  abstract accidents(): Observable<Accident[]>;
  abstract hotspots(): Observable<Hotspot[]>;
  abstract crossings(): Observable<CrossingCollection>;
  abstract measures(): Observable<Measure[]>;
  abstract cameras(): Observable<Camera[]>;
  abstract extract(req: ExtractRequest): Observable<ExtractionResult>;
  abstract review(eventId: string, req: ReviewRequest): Observable<Accident>;
}
