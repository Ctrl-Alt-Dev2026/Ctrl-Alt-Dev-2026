import { provideHttpClient } from '@angular/common/http';
import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideRouter, withComponentInputBinding, withHashLocation } from '@angular/router';

import { routes } from './app.routes';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    // Hash routing: the built UI is served as static files (nginx, FastAPI /ui/) without rewrites.
    provideRouter(routes, withComponentInputBinding(), withHashLocation()),
    provideHttpClient(),
  ],
};
