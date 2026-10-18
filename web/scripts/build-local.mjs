// Keep local builds usable on laptops with limited memory; no global settings change.
import { spawnSync } from 'node:child_process';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const directory = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const environment = {
  ...process.env,
  CI: process.env.CI ?? 'true',
  GOMAXPROCS: process.env.GOMAXPROCS ?? '2',
  NG_BUILD_MAX_WORKERS: process.env.NG_BUILD_MAX_WORKERS ?? '1',
  NG_BUILD_PARALLEL_TS: process.env.NG_BUILD_PARALLEL_TS ?? 'false',
};

for (const arguments_ of [
  ['node_modules/@angular/cli/bin/ng.js', 'build', ...process.argv.slice(2)],
]) {
  const result = spawnSync(process.execPath, arguments_, { cwd: directory, env: environment, stdio: 'inherit' });
  if (result.error) {
    console.error(result.error.message);
    process.exit(1);
  }
  if (result.status !== 0) process.exit(result.status ?? 1);
}
