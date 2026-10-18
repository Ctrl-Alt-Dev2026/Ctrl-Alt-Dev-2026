# FastAPI + the 30-minute collector (isu/, scraping/). Data lives in the /data volume (SQLite + scraper queue).
# Every dependency is installed here, so nobody installs requirements by hand: `npm run backend` (web/) builds this.
# VISION=1 (the default) also bakes in the live-camera stack: PyTorch CPU, Ultralytics and the prepared weights
# (safecross.live_setup). VISION=0 gives a small image whose cameras fall back to the provider's player.
FROM python:3.12-slim
ARG VISION=1
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONUTF8=1 \
    SAFEIASI_LIVE=1 \
    SAFEIASI_DB=/data/safeiasi.sqlite3 \
    SAFEIASI_PRESS_DIR=/data/presa
COPY requirements.txt requirements-safecross.txt requirements-vision.txt ./
COPY isu/requirements.txt isu/requirements.txt
COPY scraping/requirements.txt scraping/requirements.txt
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
