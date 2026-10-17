import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router, RouterLink, RouterLinkActive } from '@angular/router';
import { filter, map } from 'rxjs';
import { dateRo } from '../../core/format/labels';
import { DataStore } from '../../core/state/data.store';

// Provisional product name (see docs/PROJECT_CONTEXT.md); change it here only.
export const APP_NAME = 'SafeIași';

@Component({
  selector: 'app-top-bar',
  imports: [RouterLink, RouterLinkActive],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './top-bar.html',
  styleUrl: './top-bar.scss',
})
export class TopBar {
  protected readonly store = inject(DataStore);
  protected readonly appName = APP_NAME;
  protected readonly aboutOpen = signal(false);

  // "Hartă" stays active on /locatie/:id too, which routerLinkActive can't express for '/'.
  private readonly url = toSignal(
    inject(Router).events.pipe(
      filter((e) => e instanceof NavigationEnd),
      map((e) => e.urlAfterRedirects),
    ),
    { initialValue: inject(Router).url },
  );
  protected readonly onMap = computed(() => {
    const u = this.url();
    return u === '/' || u.startsWith('/locatie');
  });

  protected readonly period = computed(() => {
    const p = this.store.manifest()?.perioada;
    return p ? `${dateRo(p[0])} – ${dateRo(p[1])}` : null;
  });
}
