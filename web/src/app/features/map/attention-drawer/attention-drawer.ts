import { afterNextRender, ChangeDetectionStrategy, Component, ElementRef, inject, output, viewChild } from '@angular/core';
import { DataStore } from '../../../core/state/data.store';

// "Look here first": the fixed street list from isu/ with the facts behind each entry and the field checks
// from Planificare §7. The order comes from the data build, not from the UI.
@Component({
  selector: 'app-attention-drawer',
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './attention-drawer.html',
  styleUrl: './attention-drawer.scss',
})
export class AttentionDrawer {
  protected readonly store = inject(DataStore);
  private readonly dialog = viewChild.required<ElementRef<HTMLDialogElement>>('dialog');

  readonly show = output<string>();
  readonly closed = output<void>();

  constructor() {
    afterNextRender(() => this.dialog().nativeElement.showModal());
  }

  protected close(): void {
    this.dialog().nativeElement.close();
  }

  protected pick(id: string): void {
    this.show.emit(id);
    this.close();
  }

  // A click on the backdrop lands on the <dialog> itself.
  protected backdrop(event: MouseEvent): void {
    if (event.target === this.dialog().nativeElement) this.close();
  }
}
