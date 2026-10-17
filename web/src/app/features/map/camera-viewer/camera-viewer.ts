import { ChangeDetectionStrategy, Component, computed, inject, input, linkedSignal, output } from '@angular/core';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { Camera } from '../../../core/models/camera';
import { CameraStage } from '../camera-stage/camera-stage';

// Only providers we have checked; anything else is neither framed nor streamed.
const TRUSTED_HOST = /(^|\.)webcamromania\.ro$/;

function trusted(url: string | null): string | null {
  if (!url) return null;
  try {
    const u = new URL(url);
    return u.protocol === 'https:' && TRUSTED_HOST.test(u.hostname) ? u.href : null;
  } catch {
    return null;
  }
}

// One camera: its stream analysed live in the browser, or the provider's own player when the stream can't be read.
@Component({
  selector: 'app-camera-viewer',
  imports: [CameraStage],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="head">
      <div>
        <p class="kicker">{{ camera().sursa === 'public' ? 'Cameră publică' : 'Cameră a primăriei' }}</p>
        <h2>{{ camera().nume }}</h2>
      </div>
      <button type="button" class="close" (click)="close.emit()" aria-label="Închide camera">×</button>
    </div>

    @if (stream() && !streamFailed()) {
      @for (c of [camera()]; track c.id) {
        <app-camera-stage [camera]="c" [streamUrl]="stream()!" (failed)="streamFailed.set(true)" />
      }
    } @else {
    <div class="frame">
      @if (src(); as s) {
        <iframe
          [src]="s"
          [title]="'Transmisie de la camera ' + camera().nume"
          allow="autoplay; fullscreen; picture-in-picture"
          referrerpolicy="strict-origin-when-cross-origin"
        ></iframe>
      } @else {
        <p class="muted">Sursa acestei camere nu e pe lista furnizorilor verificați, așa că nu o afișăm.</p>
      }
    </div>
    @if (streamFailed()) {
      <p class="meta">Fluxul direct nu poate fi citit acum, așa că afișăm playerul furnizorului, fără analiză.</p>
    }
    }

    <p class="meta">
      Imagine de la <a [href]="camera().pagina_url" target="_blank" rel="noopener">{{ camera().furnizor }}</a>
      @if (camera().sursa === 'public') {, cameră publică, nu a primăriei.}
      Poziția pe hartă vine din {{ camera().sursa_coordonate }}; direcția camerei e necunoscută.
    </p>
  `,
  styles: `
    :host {
      display: flex;
      flex-direction: column;
      gap: var(--space-3);
      padding: var(--space-3) var(--space-4) var(--space-4);
      font-size: var(--step--1);
    }
    .head {
      display: flex;
      justify-content: space-between;
      align-items: start;
      gap: var(--space-3);
    }
    .kicker {
      margin: 0;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.06em;
      font-size: 0.75rem;
    }
    h2 {
      margin: 0;
      font-size: var(--step-1);
    }
    .close {
      border: var(--hair) solid var(--line);
      background: transparent;
      color: var(--ink);
      border-radius: var(--radius-s);
      width: 2rem;
      height: 2rem;
      font-size: var(--step-1);
      line-height: 1;
      cursor: pointer;
      &:hover {
        background: var(--night-800);
      }
    }
    :host > * {
      flex: none;
    }
    .frame {
      aspect-ratio: 16 / 9;
      border-radius: var(--radius-s);
      overflow: hidden;
      background: var(--night-950);
      border: var(--hair) solid var(--line);
      display: grid;
      place-items: center;
    }
    iframe {
      width: 100%;
      height: 100%;
      border: 0;
      display: block;
    }
    .frame p {
      margin: 0;
      padding: var(--space-3);
      text-align: center;
    }
    p {
      margin: 0;
    }
    .meta {
      color: var(--muted);
    }
    a {
      color: var(--accent);
    }
  `,
})
export class CameraViewer {
  private readonly sanitizer = inject(DomSanitizer);

  readonly camera = input.required<Camera>();
  readonly close = output<void>();

  protected readonly stream = computed(() => trusted(this.camera().stream_url));
  // Resets when another camera is opened.
  protected readonly streamFailed = linkedSignal({ source: this.camera, computation: () => false });

  protected readonly src = computed<SafeResourceUrl | null>(() => {
    const url = trusted(this.camera().embed_url);
    return url ? this.sanitizer.bypassSecurityTrustResourceUrl(url) : null;
  });
}
