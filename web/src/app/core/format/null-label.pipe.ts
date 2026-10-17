import { Pipe, PipeTransform } from '@angular/core';

// Renders contract values; null is "necunoscut" (or a custom text), never "nu" or blank.
@Pipe({ name: 'nullLabel' })
export class NullLabelPipe implements PipeTransform {
  transform(value: string | number | boolean | null | undefined, unknown = 'necunoscut'): string {
    if (value === null || value === undefined || value === '') return unknown;
    if (value === true) return 'da';
    if (value === false) return 'nu';
    return String(value);
  }
}
