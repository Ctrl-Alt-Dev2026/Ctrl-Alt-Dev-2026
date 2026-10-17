// Copies the team's contract files into public/data so the UI can serve them.
// Source: ../data if it exists (real pipeline output), else ../false_data (synthetic fixtures).
import { cpSync, existsSync, mkdirSync, readdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const source = ['data', 'false_data'].map((d) => join(root, d)).find(existsSync);
const target = join(root, 'web', 'public', 'data');

if (!source) {
  console.error('sync-data: neither ../data nor ../false_data exists');
  process.exit(1);
}

// Contract name differences between the fixtures and Planificare.md §4.
const RENAME = { 'measure.json': 'measures.json' };

mkdirSync(target, { recursive: true });
for (const file of readdirSync(source)) {
  if (!/\.(geo)?json$/.test(file)) continue;
  cpSync(join(source, file), join(target, RENAME[file] ?? file));
  console.log(`sync-data: ${file} -> public/data/${RENAME[file] ?? file}`);
}
