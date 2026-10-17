import { Provider } from '@angular/core';
import { environment } from '../../../environments/environment';
import { DataApi } from './data-api';
import { HttpDataApi } from './http-data-api';
import { MockDataApi } from './mock-data-api';

export function provideDataApi(): Provider {
  return { provide: DataApi, useClass: environment.api.mode === 'http' ? HttpDataApi : MockDataApi };
}
