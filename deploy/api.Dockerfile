# FastAPI + the 30-minute collector (isu/, scraping/). Data lives in the /data volume (SQLite + scraper queue).
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONUTF8=1 \
    SAFEIASI_LIVE=1 \
    SAFEIASI_DB=/data/safeiasi.sqlite3 \
    SAFEIASI_PRESS_DIR=/data/presa
COPY requirements.txt requirements.txt
COPY isu/requirements.txt isu/requirements.txt
COPY scraping/requirements.txt scraping/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt -r isu/requirements.txt -r scraping/requirements.txt
COPY . .
VOLUME /data
EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
