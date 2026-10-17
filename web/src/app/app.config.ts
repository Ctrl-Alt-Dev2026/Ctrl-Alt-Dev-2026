import { provideHttpClient } from '@angular/common/http';
import { LocationStrategy } from '@angular/common';
import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideRouter, withComponentInputBinding, withHashLocation } from '@angular/router';

import { routes } from './app.routes';
import { provideDataApi } from './core/api/provide-data-api';
import { SessionHashLocationStrategy } from './core/api/session-hash-location-strategy';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    // Hash routing: GitHub Pages serves static files only.
    provideRouter(routes, withComponentInputBinding(), withHashLocation()),
    { provide: LocationStrategy, useClass: SessionHashLocationStrategy },
    provideHttpClient(),
    provideDataApi(),
  ],
};
