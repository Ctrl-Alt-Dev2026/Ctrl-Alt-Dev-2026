import { afterNextRender, afterRenderEffect, ChangeDetectionStrategy, Component, computed, DestroyRef, ElementRef, inject, signal, viewChild } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router, RouterLink, RouterLinkActive } from '@angular/router';
import { filter, map } from 'rxjs';
import { dateRo } from '../../core/format/labels';
import { DataStore } from '../../core/state/data.store';

const CLOCK = new Intl.DateTimeFormat('ro-RO', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Bucharest' });

function clock(iso: string | null): string | null {
  return iso ? CLOCK.format(new Date(iso)) : null;
}

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
  private readonly aboutDialog = viewChild.required<ElementRef<HTMLDialogElement>>('aboutDialog');

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

  // The collected dataset lists its sources in the manifest.
  protected readonly isIsu = computed(() => !!this.store.manifest()?.surse?.some((s) => s.id === 'isu'));
  protected readonly pressInCity = computed(() => {
    const stats = this.store.manifest()?.statistici;
    return stats?.['presa_municipiu'] ?? stats?.['presa_evenimente'] ?? null;
  });
  protected readonly updated = computed(() => clock(this.store.builtAt()));
  protected readonly next = computed(() => clock(this.store.status()?.urmatoarea_rulare ?? null));
  protected readonly lastRunFailed = computed(() => this.store.status()?.ultima_rulare?.status === 'error');

  constructor() {
    afterRenderEffect(() => {
      const dialog = this.aboutDialog().nativeElement;
      if (this.aboutOpen() && !dialog.open) dialog.showModal();
      else if (!this.aboutOpen() && dialog.open) dialog.close();
    });
    const host = inject(ElementRef<HTMLElement>).nativeElement;
    const destroy = inject(DestroyRef);
    afterNextRender(() => {
      const update = () => {
        const wide = matchMedia('(min-width: 56rem)').matches;
        const gutter = parseFloat(getComputedStyle(document.documentElement).fontSize);
        document.documentElement.style.setProperty('--chrome-top', wide ? `${host.offsetHeight + gutter * 2}px` : '0rem');
      };
      const observer = new ResizeObserver(update);
      observer.observe(host);
      update();
      destroy.onDestroy(() => observer.disconnect());
    });
  }

  protected backdrop(event: MouseEvent): void {
    const dialog = this.aboutDialog().nativeElement;
    if (event.target !== dialog) return;
    const rect = dialog.getBoundingClientRect();
    if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) {
      this.aboutOpen.set(false);
    }
  }
}
