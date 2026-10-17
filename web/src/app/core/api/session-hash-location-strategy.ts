import { APP_BASE_HREF, HashLocationStrategy, PlatformLocation } from '@angular/common';
import { inject, Injectable } from '@angular/core';

/** Keeps the explicit dataset/version selection when a hash route changes. */
@Injectable()
export class SessionHashLocationStrategy extends HashLocationStrategy {
  private readonly platform = inject(PlatformLocation);

  constructor() {
    super(inject(PlatformLocation), inject(APP_BASE_HREF, { optional: true }) ?? undefined);
  }

  override prepareExternalUrl(internal: string): string {
    const query = new URLSearchParams(this.platform.search);
    const hashQuery = new URLSearchParams(this.platform.hash.split('?')[1] ?? '');
    const sessionQuery = new URLSearchParams();
    for (const key of ['data_mode', 'snapshot_id']) {
      const value = query.get(key) ?? hashQuery.get(key);
      if (value) sessionQuery.set(key, value);
    }

    // A fragment alone is resolved against <base href>, which drops shell query
    // parameters. Read the current selection on every navigation, including a
    // mode switch or a newly published snapshot, rather than capturing a pin.
    const search = sessionQuery.size ? `?${sessionQuery}` : '';
    return `${this.platform.pathname}${search}${super.prepareExternalUrl(internal)}`;
  }
}
