import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { DataStore } from './core/state/data.store';
import { TopBar } from './shared/top-bar/top-bar';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, TopBar],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <app-top-bar />
    <main class="page">
      @switch (store.state()) {
        @case ('loading') {
          <p class="status muted">Se încarcă datele…</p>
        }
        @case ('error') {
          <div class="status" role="alert">
            <p>Datele nu s-au putut încărca: {{ store.error() }}</p>
            <p class="muted">Rulează <code>npm run sync-data</code> în <code>web/</code>, apoi reîncarcă pagina.</p>
            <button class="btn" type="button" (click)="store.load()">Încearcă din nou</button>
          </div>
        }
        @default {
          <router-outlet />
        }
      }
    </main>
  `,
  styles: `
    :host {
      display: flex;
      flex-direction: column;
      height: 100svh;
    }
    .page {
      flex: 1;
      min-height: 0;
      display: flex;
      flex-direction: column;
    }
    .status {
      margin: auto;
      max-width: 60ch;
      padding: var(--space-5);
      text-align: center;
    }
  `,
})
export class App {
  protected readonly store = inject(DataStore);

  constructor() {
    this.store.load();
  }
}
