# Deploying SafeIași (one image: Cloud Run or Vercel)

`deploy/api.Dockerfile` has two targets. `api` is what `docker-compose.yml` and `npm run backend` use. `cloud` (the
default) is a single public container:

- **Angular**: built in a `node:22-alpine` stage (`npm ci`, `ng build --base-href /ui/`) and served by FastAPI at
  `/ui/` (`api/frontend.py`); `/` redirects there. Same origin as `/api/v1`, so no CORS and no nginx.
- **Python**: `requirements.txt` + `isu/requirements.txt` (with `risk/requirements.txt`: pyproj, shapely, h3) +
  `scraping/requirements.txt` (the BZI / Ziarul de Iași scraper the collector runs every 30 minutes).
- **YOLO**: PyTorch CPU, Ultralytics, and the YOLO11s / YOLO-World weights downloaded at build time
  (`safecross.live_setup`, into `/app/runtime/models`). `--build-arg VISION=0` leaves them out (~2 GB smaller; the
  cameras then fall back to the provider's player).
- **Data**: everything a fresh start needs, from the checkout: `isu/seed/` (ISU release texts, press articles found
  by the live scraper, the saved Claude answers, the last dataset), `scraping/articole_extrase_accident_clean.csv`
  (2026 press sample), `isu/pmud2022_tabel_2_11.csv` (IPJ figures from PMUD), the OSM geocoder index, the OSM
  context and the measures catalog. The container shows that dataset at once, then collects what is new.
- **Access**: `SAFEIASI_PUBLIC=ui,vision` opens the read-only UI and the camera frame analysis to visitors (behind
  Cloud Run no request is local). Review, imports, publication, SafeCross and `POST /live/refresh` stay local-only.
  `SAFEIASI_PUBLIC=ui` keeps the cameras closed (the viewer then uses the provider's player).
- No secrets in the image (`.dockerignore` drops `ai/gemini.local.json`, `.env`). The Claude step (`npm run ai`)
  does not run in the cloud: articles scraped there go through the provisional rules until the next `npm run ai`
  on a laptop, commit and redeploy.

## Before building: fold in the latest data

The image carries what is in `isu/seed/` at build time. To include news fetched since the last commit:

```sh
cd web && npm run ai            # optional: Claude judges new articles and refreshes street suggestions
python -m isu --seed            # or: npm run backend:share and wait for one collection
```

## Cloud Run: build, push, deploy

```sh
PROJECT=<gcp-project-id>
REGION=europe-west1                 # any Cloud Run region
REPO=safeiasi
IMAGE=$REGION-docker.pkg.dev/$PROJECT/$REPO/safeiasi:$(git rev-parse --short HEAD)

gcloud artifacts repositories create $REPO --repository-format=docker --location=$REGION   # once
gcloud auth configure-docker $REGION-docker.pkg.dev                                        # once

docker build --platform linux/amd64 -f deploy/api.Dockerfile -t $IMAGE .   # from the repo root
docker push $IMAGE

gcloud run deploy safeiasi --image $IMAGE --region $REGION --allow-unauthenticated \
  --memory 2Gi --cpu 2 --no-cpu-throttling --cpu-boost \
  --min-instances 1 --max-instances 1 --timeout 300 --execution-environment gen2
```

On PowerShell, set the variables with `$env:PROJECT = "..."` and use `$env:PROJECT` etc. in the commands.

Why these flags:

- `--max-instances 1`: SQLite and the camera sessions live in the instance's memory. Two instances would show
  different datasets and lose camera sessions between frames.
- `--no-cpu-throttling --min-instances 1`: the collector is a background thread. With request-based billing Cloud
  Run freezes the CPU between requests and the 30-minute runs stall. This keeps one instance running, and billed,
  even without visitors. Delete the service after the demo (`gcloud run services delete safeiasi --region $REGION`).
- `--memory 2Gi --cpu 2`: measured locally, the container uses about 0.55 GiB with both YOLO models loaded; the
  rest is headroom for the collector's build and the in-memory filesystem (`/data`). Raise it if Cloud Run reports
  out-of-memory restarts.
- `--timeout 300`: the first camera frame loads the models (tens of seconds on CPU).

## Cloud Run limits

- The filesystem is in memory. A new revision or restart starts again from the image's seed, then collects again.
  Nothing collected in the cloud is written back to git.
- The ISU and press sites are fetched from Google's IP addresses. If a site blocks them, the run log
  (`GET /api/v1/live/status`, `ultima_rulare`) says so and the map keeps the last dataset.
- Cloud Run caps a request body at 32 MiB. Camera frames are at most 2 MiB; SafeCross video upload is local-only anyway.
- Camera analysis is open to anyone with the URL and uses this instance's CPU. Use `SAFEIASI_PUBLIC=ui`
  (`--set-env-vars SAFEIASI_PUBLIC=ui`) if that is a concern.

## Test the image locally

From the repo root, with Docker Desktop running:

```sh
docker build --platform linux/amd64 -f deploy/api.Dockerfile -t safeiasi:cloud .   # ~10 min the first time
docker run --rm --name safeiasi-cloud -p 127.0.0.1:8090:8080 safeiasi:cloud
```

Then, in a second terminal (the `Host` header pretends to be the cloud domain, so nothing counts as local):

```sh
H="Host: safeiasi.example.app"
curl -s -o /dev/null -w "%{http_code}
" -H "$H" localhost:8090/ui/                    # 200
curl -s -H "$H" localhost:8090/api/v1/live/status                                       # construit_la = the seed's
curl -s -H "$H" localhost:8090/api/v1/vision/status                                     # "available":true
curl -s -o /dev/null -w "%{http_code}
" -X POST -H "$H" localhost:8090/api/v1/live/refresh  # 403 (stays local)
```

Open http://localhost:8090 (it redirects to `/ui/`): the map, "Străzi de verificat", the street panel with the AI
suggestions, and "Camere live" (the first analysed frame takes ~15 s while YOLO loads). `docker stats` shows memory.
The Vercel variant: `docker build -f Dockerfile.vercel -t safeiasi:vercel .`, then
`docker run --rm -p 127.0.0.1:8092:80 safeiasi:vercel`.

## Vercel (Container Runtime, beta), from the dashboard only

Vercel runs container images as Functions and builds `Dockerfile.vercel` from the repo itself: the same image as the
`cloud` target, with the collector off (below) and port 80. No CLI, no registry. `vercel.json` sets the region
`fra1` (Frankfurt).

1. Commit and push `Dockerfile.vercel`, `vercel.json`, `.vercelignore` and the current `isu/seed/` to GitHub.
2. vercel.com → **Add New… → Project → Import Git Repository**, pick the repo. If it is not listed, its GitHub
   owner has to allow the Vercel app on it (or fork the repo to your account and import the fork).
3. **Framework Preset: Other**, **Root Directory: `./`**, leave the build and output commands empty, **Deploy**.
   The first build takes ~10-15 min (Angular, PyTorch, the YOLO weights).
4. Open `https://<project>.vercel.app`; it redirects to `/ui/`.

Vercel deploys the production branch (`main` by default; **Settings → Git → Production Branch** to change it).
Other branches become previews, whose instances stop after 30 idle seconds instead of 5 minutes. Every push
redeploys, so new data = refresh `isu/seed/` on a laptop (`python -m isu --seed`, optionally `npm run ai`), commit, push.

Differences from Cloud Run:

- **No collector**: `Dockerfile.vercel` sets `SAFEIASI_LIVE=0`. Instances stop after 5 idle minutes and several can
  run at once, so a collector would be cut off mid-run and each instance would show different data. Every instance
  serves the dataset baked into the image; the top bar says automatic collection is off.
- **Plan limits** (Vercel Functions): Hobby 2 GB / 1 vCPU, Pro up to 4 GB / 2 vCPU; 300 s per request (Hobby);
  4.5 MB request body (camera frames are at most 2 MiB). On 1 vCPU the camera analysis is slower.
- **Cold starts**: after 5 idle minutes the next visitor waits for a new instance of a 3.5 GB image; the first camera
  frame then loads YOLO again (~15 s).
- **Camera sessions** live in one instance's memory. If Vercel routes a frame to another instance the session is
  unknown there; with demo traffic there is usually one instance.
- `Dockerfile.vercel` repeats `deploy/api.Dockerfile` (Vercel builds one file, with no target): change both together.
