"""Explicit local publication and read-only location dossiers from frozen releases."""

from html import escape
import json
import re
from typing import Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse

from api.publication_context import PublicationContextError, load_context
from api.publication_models import PublicationRequest
from api.publication_store import PublicationError, PublicationStore
from api.review_models import DataMode
from api.review_router import require_local
from api.review_store import ReviewStore


router = APIRouter(
    tags=["publication"], dependencies=[Depends(require_local)],
    responses={403: {"description": "Local operator access only."}, 503: {"description": "Publication or context unavailable; existing release preserved."}},
)


def store(request, mode):
    return PublicationStore(
        request.app.state.publication_directory, mode,
        ReviewStore(request.app.state.review_directory, mode),
        request.app.state.publication_context_directory,
    )


def metadata(snapshot):
    return {key: snapshot[key] for key in (
        "schema_version", "snapshot_id", "data_mode", "publication_status", "published_at",
        "period", "warnings", "eligible_event_count", "content_sha256",
    )} | {
        "response_origin": "published_snapshot", "location_count": len(snapshot["locations"]),
        "context_attribution": snapshot["provenance"]["context"]["attribution"],
        "context_fingerprint": snapshot["provenance"]["context"]["fingerprint"],
        "formula_sha256": snapshot["provenance"]["formula_sha256"],
    }


def release(request, mode, snapshot_id):
    manager = store(request, mode)
    return manager.get(snapshot_id) if snapshot_id else manager.latest()


def dossier(snapshot, location_id):
    location = next((row for row in snapshot["locations"] if row["location_id"] == location_id), None)
    if location is None:
        raise PublicationError(404, "location_not_found", "Locația nu este inclusă în versiunea publicată aleasă.")
    event_ids = set(location["event_ids"])
    return metadata(snapshot) | {
        "location": location, "events": [event for event in snapshot["events"] if event["event_id"] in event_ids],
        "provenance": snapshot["provenance"],
        "candidate_measures": [], "measures_status": "awaiting_sourced_catalog_and_applicability_review",
    }


@router.get("/api/v1/publication-context", summary="Inspect infrastructure for an explicit event-to-location association")
def context(request: Request, data_mode: DataMode = "observed", q: str = Query("", max_length=200), limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
    dataset = load_context(request.app.state.publication_context_directory, data_mode)
    features = dataset.all_features()
    needle = q.casefold().strip()
    filtered = [feature for feature in features if not needle or needle in json.dumps(feature, ensure_ascii=False).casefold()]
    return {"data_mode": data_mode, "context": dataset.metadata, "total": len(features), "filtered_total": len(filtered), "offset": offset, "limit": limit, "features": filtered[offset:offset + limit]}


@router.post("/api/v1/publications/preview", summary="Check eligibility and deterministic scores without publishing or changing review")
def preview(body: PublicationRequest, request: Request):
    return store(request, body.data_mode).preview(body)


@router.post("/api/v1/publications", status_code=201, summary="Freeze an explicitly selected, version-checked set of canonical events")
def publish(body: PublicationRequest, request: Request):
    snapshot, reused = store(request, body.data_mode).publish(body)
    return JSONResponse(status_code=200 if reused else 201, content={"snapshot": snapshot, "reused": reused})


@router.get("/api/v1/publications/latest", summary="Read the latest committed publication in one data mode")
def latest(request: Request, data_mode: DataMode = "synthetic"):
    return store(request, data_mode).latest()


@router.get("/api/v1/publications", summary="List committed versions without exposing uncommitted files")
def publications(request: Request, data_mode: DataMode = "synthetic"):
    return {"data_mode": data_mode, "response_origin": "published_snapshot", "publications": store(request, data_mode).list_snapshots()}


@router.get("/api/v1/publications/{snapshot_id}", summary="Read an immutable published version")
def publication(snapshot_id: str, request: Request, data_mode: DataMode = "synthetic"):
    return store(request, data_mode).get(snapshot_id)


@router.get("/api/v1/publications/{snapshot_id}/events", summary="Canonical events with sources from the exact published version")
def published_events(snapshot_id: str, request: Request, data_mode: DataMode = "synthetic"):
    snapshot = store(request, data_mode).get(snapshot_id)
    return metadata(snapshot) | {"events": snapshot["events"]}


def filtered_locations(snapshot, q, ranked_only):
    needle = q.casefold().strip()
    return [row for row in snapshot["locations"]
            if (not ranked_only or row["rank"] is not None)
            and (not needle or needle in (row["location_id"] + " " + str(row["feature"]["properties"].get("nume") or "")).casefold())]


@router.get("/api/v1/locations", summary="Location list for the frontend; scores/ranks remain those of the frozen period")
def locations(request: Request, data_mode: DataMode = "synthetic", snapshot_id: str | None = None, q: str = Query("", max_length=200), ranked_only: bool = False, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
    snapshot = release(request, data_mode, snapshot_id)
    selected = filtered_locations(snapshot, q, ranked_only)
    page = selected[offset:offset + limit]
    return metadata(snapshot) | {
        "filtered_location_count": len(selected), "returned_location_count": len(page),
        "filtered_event_count": sum(row["event_count"] for row in selected),
        "offset": offset, "limit": limit, "locations": page,
        "ranking_scope": "fixed_published_period; filters do not recompute scores or ranks",
    }


@router.get("/api/v1/locations.geojson", summary="Map points with the same snapshot, IDs, counts and scores as location dossiers")
def location_map(request: Request, data_mode: DataMode = "synthetic", snapshot_id: str | None = None, q: str = Query("", max_length=200), ranked_only: bool = False):
    snapshot = release(request, data_mode, snapshot_id)
    rows = filtered_locations(snapshot, q, ranked_only)
    features = [{"type": "Feature", "id": row["location_id"], "geometry": row["feature"]["geometry"], "properties": {
        "location_id": row["location_id"], "name": row["feature"]["properties"].get("nume"),
        "event_count": row["event_count"], "score": row["score"], "rank": row["rank"],
        "data_mode": snapshot["data_mode"], "snapshot_id": snapshot["snapshot_id"],
    }} for row in rows]
    return metadata(snapshot) | {"type": "FeatureCollection", "features": features, "filtered_location_count": len(rows), "filtered_event_count": sum(row["event_count"] for row in rows)}


@router.get("/api/v1/locations/{location_id}", summary="Location dossier: events, sources, priority explanation, context and unknowns")
def location(location_id: str, request: Request, data_mode: DataMode = "synthetic", snapshot_id: str | None = None):
    return dossier(release(request, data_mode, snapshot_id), location_id)


def _value(value):
    if value is None:
        return "necunoscut"
    if value is True:
        return "da"
    if value is False:
        return "nu"
    return escape(str(value))


def _link(url):
    try:
        parsed = urlsplit(url)
        valid = parsed.scheme in ("http", "https") and parsed.hostname and not parsed.username and not parsed.password
    except (ValueError, TypeError):
        valid = False
    return f'<a href="{escape(url, quote=True)}" rel="noreferrer noopener">{escape(url)}</a>' if valid else _value(url)


def render_dossier(payload):
    """A printable artifact, escaped throughout; no generated recommendations."""
    row = payload["location"]
    title = row["feature"]["properties"].get("nume") or row["location_id"]
    details = row.get("score_details") or {}
    components = details.get("componente_scor") or {}
    events = []
    for event in payload["events"]:
        fields = event["fields"]
        articles = []
        for article in event["source_articles"]:
            articles.append(f'<li><strong>{_value(article["titlu"])}</strong> · {_value(article["sursa"])}<br>{_link(article["url"])}<br>Publicat: {_value(article["publicat_la"])} · Colectat: {_value(article["colectat_la"])}</li>')
        evidence = []
        corrections = []
        for claim in event["source_claims"]:
            for key, quote in claim["original_extraction"].get("dovezi", {}).items():
                evidence.append(f'<li>{_value(key)} · {_value(claim["article_id"])}: <q>{_value(quote)}</q></li>')
            for entry in claim["history"]:
                if entry["action"] == "corrected":
                    changes = escape(json.dumps(entry["changes"], ensure_ascii=False, indent=2))
                    corrections.append(f'<li>{_value(claim["article_id"])} · {_value(entry["operator"])} · {_value(entry["at"])} · {_value(entry["note"])}<pre style="white-space:pre-wrap;overflow-wrap:anywhere">{changes}</pre></li>')
        history = "".join(f'<li>{_value(entry["action"])} · {_value(entry["operator"])} · {_value(entry["at"])} · {_value(entry["note"])}</li>' for entry in event["history"])
        events.append(f'<article><h3>{_value(event["event_id"])}</h3><p>Data evenimentului: {_value(fields["data_eveniment"])} · Ora: {_value(fields["ora"])} · Gravitate: {_value(fields["gravitate"])}</p><p>Participanți: {_value(", ".join(fields["participanti"]) or None)} · Cauză raportată: {_value(fields["cauza_raportata"])} · Noapte: {_value(fields["noapte"])}</p><p>Loc: {_value(fields["loc_text"])} · Precizie: {_value(fields["precizie_loc"])}</p><p>Localizare: {_value(fields["location_evidence"])}<br>Asociere la locație: {_value(event["association"]["note"])}</p><h4>Surse</h4><ul>{"".join(articles)}</ul><h4>Pasaje extrase inițial</h4><p>Câmpurile curente includ corecturile operatorului; pasajele de mai jos provin din extracția arhivată.</p><ul>{"".join(evidence)}</ul><details open><summary>Corecturi și decizii de verificare</summary><ul>{"".join(corrections)}{history}</ul></details></article>')
    warnings = "".join(f'<li>{_value(value)}</li>' for value in payload["warnings"])
    unknowns = "".join(f'<li>{_value(value)}</li>' for value in dict.fromkeys(row["unknowns"] + details.get("date_lipsa", [])))
    properties = "".join(f'<tr><th>{_value(key)}</th><td>{_value(value)}</td></tr>' for key, value in row["feature"]["properties"].items() if key in ("tip", "semafor", "benzi", "iluminat", "scoala_150m", "statie_100m", "sursa"))
    parts = "".join(f'<li>{_value(key)}: {_value(value)}</li>' for key, value in components.items())
    return f'''<!doctype html><html lang="ro"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SafeIași — {_value(title)}</title><style>body{{font:16px/1.55 system-ui,sans-serif;color:#16382f;background:#f5f8f6;margin:0;overflow-wrap:anywhere}}main{{max-width:920px;margin:2rem auto;background:white;padding:2rem;border:1px solid #dce6e1;border-radius:12px}}h1,h2,h3{{line-height:1.2}}.mode{{background:#fff4cc;padding:1rem;border-left:5px solid #a86900}}article{{border-top:1px solid #dce6e1;margin-top:1.5rem;padding-top:1rem}}table{{border-collapse:collapse;width:100%}}td,th{{text-align:left;padding:.4rem;border-bottom:1px solid #dce6e1}}a{{color:#086b56;overflow-wrap:anywhere}}small,footer{{overflow-wrap:anywhere}}q{{font-style:italic}}@media print{{body{{background:white}}main{{border:0;margin:0;padding:0}}article{{break-inside:avoid}}details{{display:block}}}}</style></head><body><main><p>SafeIași · Fișă de locație · {_value(payload["data_mode"])}</p><h1>{_value(title)}</h1><div class="mode"><ul>{warnings}</ul></div><p>Perioadă: {_value(payload["period"]["start"])} – {_value(payload["period"]["end"])}</p><p><strong>{_value(row["event_count"])} evenimente distincte · {_value(row["source_article_count"])} articole</strong><br>Scor în eșantion: {_value(row["score"])} · Poziție: {_value(row["rank"])}</p><h2>Explicația priorității</h2><p>{_value(details.get("explicatie") if details else "Date insuficiente pentru clasament: minimum două evenimente la aceeași locație.")}</p><ul>{parts}</ul><h2>Context și necunoscute</h2><table>{properties}</table><ul>{unknowns}</ul><p>Măsurile candidate așteaptă un catalog cu surse și verificarea aplicabilității; această fișă nu propune efecte sau costuri.</p><h2>Evenimente și dovezi</h2>{"".join(events)}<footer><p>Context: {_value(payload["context_attribution"])}<br>Versiune: {_value(payload["snapshot_id"])}<br>Publicat local: {_value(payload["published_at"])}<br>SHA-256: {_value(payload["content_sha256"])}</p><p>Fișă de sprijin pentru verificare, fără certificarea unui audit rutier. Tipărirea / salvarea PDF se face din browser.</p></footer></main></body></html>'''


@router.get("/api/v1/locations/{location_id}/export", summary="Export the dossier as JSON or a printable HTML sheet")
def export(location_id: str, request: Request, data_mode: DataMode = "synthetic", snapshot_id: str | None = None, format: Literal["json", "html"] = "json"):
    snapshot = release(request, data_mode, snapshot_id)
    payload = dossier(snapshot, location_id)
    filename = re.sub(r"[^A-Za-z0-9_-]", "_", location_id)[:80]
    headers = {"ETag": f'"{snapshot["content_sha256"]}"', "X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"}
    if format == "html":
        headers["Content-Disposition"] = f'inline; filename="safeiasi-{data_mode}-{filename}.html"'
        headers["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'"
        return HTMLResponse(render_dossier(payload), headers=headers)
    headers["Content-Disposition"] = f'attachment; filename="safeiasi-{data_mode}-{filename}.json"'
    return JSONResponse(payload, headers=headers)


async def error_handler(request, error):
    return JSONResponse(status_code=error.status, content={"detail": {"code": error.code, "message": error.message, "issues": getattr(error, "issues", None) or []}})


def register_publication(application):
    if not getattr(application.state, "safeiasi_publication_routes_registered", False):
        application.include_router(router)
        application.add_exception_handler(PublicationError, error_handler)
        application.add_exception_handler(PublicationContextError, error_handler)
        application.state.safeiasi_publication_routes_registered = True
        application.openapi_schema = None
    return application
