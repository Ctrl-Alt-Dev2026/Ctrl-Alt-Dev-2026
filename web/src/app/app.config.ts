import { provideHttpClient } from '@angular/common/http';
import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideRouter, withComponentInputBinding, withHashLocation } from '@angular/router';

import { routes } from './app.routes';
import { provideDataApi } from './core/api/provide-data-api';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    // Hash routing: GitHub Pages serves static files only.
    provideRouter(routes, withComponentInputBinding(), withHashLocation()),
    provideHttpClient(),
    provideDataApi(),
  ],
};
