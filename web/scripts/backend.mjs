// `npm run backend`: the FastAPI backend in Docker (deploy/api.Dockerfile) on 127.0.0.1:8000, with every Python
// dependency and the live-camera models already in the image. The first build takes several minutes; later
// starts reuse it and rebuild only what changed. Data persists in the compose `data` volume, seeded from isu/seed/.
//   --share       also rewrite isu/seed/ after each collection, to commit (deploy/compose.share.yml)
//   --no-vision   small image without the camera stack (cameras fall back to the provider's player)
// Without Docker: `npm run backend:local` (Python .venv, scripts/backend.py).
import { spawnSync } from 'node:child_process';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const flags = new Set(process.argv.slice(2));
const files = ['-f', 'docker-compose.yml', ...(flags.has('--share') ? ['-f', 'deploy/compose.share.yml'] : [])];
const environment = {
  ...process.env,
  SAFEIASI_VISION: flags.has('--no-vision') ? '0' : (process.env.SAFEIASI_VISION ?? '1'),
  // The host reaches the published port through the Docker gateway; local-only routes must accept it.
  SAFEIASI_TRUST_DOCKER: '1',
};

if (spawnSync('docker', ['info'], { stdio: 'ignore' }).status !== 0) {
  console.error('backend: Docker nu rulează. Pornește Docker Desktop și încearcă din nou, sau folosește `npm run backend:local`.');
  process.exit(1);
}
if (flags.has('--share')) {
  console.log('backend: --share: isu/seed/ se rescrie după fiecare colectare; fă commit ca să ajungă la colegi.');
}
console.log('backend: http://127.0.0.1:8000, colectare la 30 de minute; apoi `npm start` -> http://localhost:4200');
const result = spawnSync('docker', ['compose', ...files, 'up', '--build', 'api'], { cwd: root, env: environment, stdio: 'inherit' });
process.exit(result.status ?? 1);
