# Two images from one file, so the dependencies are written once:
# - target `api` (docker-compose.yml, `npm run backend`): FastAPI + the 30-minute collector (isu/, scraping/); the
#   compose stack serves the UI from nginx (deploy/web.Dockerfile).
# - target `cloud` (the default, for Artifact Registry / Cloud Run): the same API, also serving the Angular build
#   at /ui/, listening on $PORT, with the UI and the cameras open to visitors. Build and deploy: deploy/README.md.
# Data baked in by `COPY . .`: isu/seed/ (ISU release texts, press articles found by the live scraper, the Claude
# answers, the last dataset), the 2026 press sample (scraping/), the PMUD/IPJ table, the OSM geocoder index, the OSM
# context and the measures catalog. At run time it lives in /data (SQLite + scraper queue).
# VISION=1 (the default) also bakes in the live-camera stack: PyTorch CPU, Ultralytics and the prepared YOLO11s /
# YOLO-World weights (safecross.live_setup). VISION=0 gives a small image whose cameras fall back to the provider's player.

FROM node:22-alpine AS ui
WORKDIR /web
COPY web/package.json web/package-lock.json web/.npmrc ./
RUN npm ci
COPY web/ ./
# api/frontend.py serves the build at /ui/ and checks this base href.
RUN npx ng build --base-href /ui/

FROM python:3.12-slim AS api
ARG VISION=1
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONUTF8=1 \
    SAFEIASI_LIVE=1 \
    SAFEIASI_DB=/data/safeiasi.sqlite3 \
    SAFEIASI_PRESS_DIR=/data/presa
COPY requirements.txt requirements-safecross.txt requirements-vision.txt ./
COPY isu/requirements.txt isu/requirements.txt
COPY risk/requirements.txt risk/requirements.txt
COPY scraping/requirements.txt scraping/requirements.txt
# isu/requirements.txt pulls risk/requirements.txt (pyproj, shapely, h3 for the street analysis).
RUN pip install --no-cache-dir -r requirements.txt -r isu/requirements.txt -r scraping/requirements.txt
# Ultralytics pulls opencv-python, which needs libGL; the CPU wheel index keeps PyTorch without CUDA (~1 GB less).
RUN if [ "$VISION" = "1" ]; then \
      apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/* && \
      pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch torchvision && \
      pip install --no-cache-dir -r requirements-safecross.txt -r requirements-vision.txt; \
    fi
# Weights go to /app/runtime/models; only a safecross/ change downloads them again.
COPY safecross/ safecross/
RUN if [ "$VISION" = "1" ]; then python -m safecross.live_setup; fi
COPY . .
VOLUME /data
EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM api AS cloud
COPY --from=ui /web/dist/web/browser web/dist/web/browser
# No request is local behind Cloud Run: open the read-only UI and the camera analysis (api/review_router.py,
# SAFEIASI_PUBLIC). Review, imports, publication and refresh stay closed. "/" redirects to /ui/.
# Cloud Run sets PORT and terminates HTTPS; --proxy-headers keeps the visitor's scheme.
ENV SAFEIASI_PUBLIC=ui,vision PORT=8080
EXPOSE 8080
CMD ["sh", "-c", "exec uvicorn api.main:app --host 0.0.0.0 --port \"$PORT\" --proxy-headers --forwarded-allow-ips '*'"]
