"""Explicit offline SYNTHETIC import-to-publication rehearsal, in a fresh directory.

Run with ``python -m api.demo_publication`` after installing requirements-dev.txt.
This drives the real local HTTP contracts with TestClient; it is a development
rehearsal using the deterministic rules extractor, not live model processing.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from typing import Any


REPOSITORY = Path(__file__).resolve().parents[1]
DEFAULT_DIRECTORY = REPOSITORY / "runtime" / "publication-demo"
SCHEMA_VERSION = "publication-demo-1"
OPERATOR = "Operator demo SINTETIC"
LOCATIONS = (
    {"id": "demo-crossing-01", "name": "Alfa", "coordinates": [27.580, 47.170]},
    {"id": "demo-crossing-02", "name": "Beta", "coordinates": [27.582, 47.172]},
    {"id": "demo-crossing-03", "name": "Gamma", "coordinates": [27.584, 47.174]},
)
SCENARIOS = (
    (0, "2026-09-01", "08:15", "dimineața", "Pietonul a suferit răni grave."),
    (0, "2026-09-05", "22:10", "noaptea", "Pietonul a suferit răni ușoare."),
    (1, "2026-09-10", "10:20", "dimineața", "Pietonul a suferit răni ușoare."),
    (1, "2026-09-15", "11:30", "dimineața", "Gravitatea leziunilor nu este cunoscută."),
    (2, "2026-09-20", "21:45", "noaptea", "Pietonul a murit."),
    (2, "2026-09-25", "09:40", "dimineața", "Pietonul a suferit răni grave."),
)


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def synthetic_articles() -> list[dict[str, str]]:
    """New fictional sources, separate from the team's prepared AI corpus."""
    articles = []
    for index, scenario in enumerate((*SCENARIOS, SCENARIOS[0]), start=1):
        location_index, event_date, event_time, time_description, severity = scenario
        location = LOCATIONS[location_index]
        duplicate = index == 7
        publication = date.fromisoformat(event_date) + timedelta(days=2 if duplicate else 1)
        articles.append({
            "article_id": f"publication-demo-synthetic-{index:02d}",
            "sursa": "SINTETIC",
            "url": f"https://example.invalid/safeiasi-publication-demo/{index:02d}",
            "titlu": f"[SINTETIC] {'Relatare suplimentară a scenariului 01' if duplicate else f'Scenariu fictiv {index:02d}'}",
            "text": (
                "SINTETIC: relatare inventată pentru verificarea aplicației; nu descrie un caz real. "
                "Un accident rutier a implicat un pieton și un autoturism. "
                f"Evenimentul s-a produs la data de {event_date}, la ora {event_time}, {time_description}. "
                f"Locul indicat este pe Strada Sintetică {location['name']}, la trecerea fictivă {location['name']}. "
                f"{severity} Cauza nu a fost precizată."
            ),
            "publicat_la": publication.isoformat(),
            "colectat_la": "2026-10-17",
        })
    return articles


def prepare_demo(directory: Path | str) -> Path:
    """Create a fresh dedicated tree; never replace an existing file or folder."""
    directory = Path(directory).resolve()
    if directory.is_relative_to(REPOSITORY) and not directory.is_relative_to(REPOSITORY / "runtime"):
        raise ValueError("Demo-ul poate scrie în repository numai într-un director nou din runtime/.")
    if directory.exists():
        raise ValueError("Directorul există deja; alege --directory cu un nume nou pentru a păstra toate datele.")
    directory.mkdir(parents=True, exist_ok=False)
    _write_json(directory / "demo-manifest.json", {
        "schema_version": SCHEMA_VERSION, "data_mode": "synthetic",
        "warning": "SINTETIC integral: surse, evenimente, localizări și infrastructură inventate pentru repetiție.",
        "processing_mode": "rules", "publication_scope": "local_demo_only",
    })
    context = directory / "context"
    context.mkdir()
    _write_json(context / "boundary.geojson", {
        "type": "Feature", "properties": {"sursa": "SINTETIC", "name": "Limită fictivă de demo; nu este limita administrativă Iași"},
        "geometry": {"type": "Polygon", "coordinates": [[[27.57, 47.16], [27.60, 47.16], [27.60, 47.19], [27.57, 47.19], [27.57, 47.16]]]},
    })
    features = []
    for index, location in enumerate(LOCATIONS):
        features.append({
            "type": "Feature", "geometry": {"type": "Point", "coordinates": location["coordinates"]},
            "properties": {
                "id": location["id"], "tip": "trecere", "sursa": "SINTETIC", "descarcat_la": "2026-10-17",
                "nume": f"SINTETIC · trecerea fictivă {location['name']}",
                "semafor": (False, True, None)[index], "iluminat": (None, True, False)[index],
                "scoala_150m": (True, None, False)[index], "statie_100m": (None, True, False)[index],
                "benzi": (2, 2, None)[index], "tip_strada": "SINTETIC · stradă fictivă",
            },
        })
    _write_json(context / "crossings.geojson", {"type": "FeatureCollection", "features": features})
    _write_json(context / "publication-context.json", {
        "schema_version": "publication-context-1", "data_mode": "synthetic",
        "provenance": "Fixture SINTETIC nou pentru demo: toate coordonatele și atributele sunt inventate; nu sunt observații sau import OSM și nu certifică infrastructura din Iași.",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "files": {name: _sha256(context / name) for name in ("boundary.geojson", "crossings.geojson")},
    })
    _write_json(directory / "articles.json", synthetic_articles())
    return directory


def _request(client, method: str, path: str, *, expected=(200,), **kwargs):
    response = client.request(method, path, **kwargs)
    if response.status_code not in expected:
        raise RuntimeError(f"{method} {path}: HTTP {response.status_code}; {response.text[:1200]}")
    return response


def run_demo(directory: Path | str = DEFAULT_DIRECTORY) -> dict[str, Any]:
    """Import seven fictional sources, review six events and publish three dossiers."""
    # TestClient/httpx are intentionally development dependencies, loaded on demand.
    from fastapi.testclient import TestClient
    from api.main import create_app

    directory = prepare_demo(directory)
    app = create_app(
        snapshot_directory=directory / "unused-snapshot",
        review_directory=directory / "review",
        publication_directory=directory / "publications",
        publication_context_directory=directory / "context",
        safecross_directory=directory / "unused-safecross",
    )
    source_to_event: dict[str, str] = {}
    articles = synthetic_articles()
    with TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 51000)) as client:
        for index, article in enumerate(articles):
            imported = _request(client, "POST", "/api/v1/imports", expected=(201,), json={
                "request_id": f"publication-demo-import-{index + 1:02d}", "operator": OPERATOR,
                "data_mode": "synthetic", "pipeline": "rules", "article": article,
            }).json()["import"]
            if len(imported["candidate_ids"]) != 1 or imported["extraction"]["processing_mode"] != "rules":
                raise RuntimeError("Demo-ul necesită exact un candidat per articol, extras explicit prin reguli.")
            candidate_id = imported["candidate_ids"][0]
            location_index = SCENARIOS[index if index < 6 else 0][0]
            location = LOCATIONS[location_index]
            lon, lat = location["coordinates"]
            corrected = _request(client, "PATCH", f"/api/v1/candidates/{candidate_id}", json={
                "data_mode": "synthetic", "expected_version": 1, "operator": OPERATOR,
                "reason": "SINTETIC: coordonate din fixture-ul inventat, adăugate separat de extracția textului.",
                "changes": {
                    "lon": lon, "lat": lat, "precizie_loc": "trecere", "in_iasi": True,
                    "location_evidence": f"SINTETIC: punctul fictiv {location['id']} din context/crossings.geojson și limita inventată a fixture-ului; nu este geocodare sau confirmare reală în Iași.",
                },
            }).json()["candidate"]
            decision = {
                "data_mode": "synthetic", "expected_version": corrected["version"], "operator": OPERATOR,
                "note": "SINTETIC: sursa fictivă, data evenimentului, localizarea inventată și identitatea cazului au fost verificate în scenariul de repetiție.",
                "action": "approve", "source_checked": True, "duplicate_checked": True, "location_checked": True,
            }
            if index == 6:
                events = _request(client, "GET", "/api/v1/reviewed-events?data_mode=synthetic").json()["events"]
                canonical = next(item for item in events if articles[0]["article_id"] in item["article_ids"])
                decision.update(action="link", canonical_event_id=canonical["event_id"], expected_event_version=canonical["version"])
                decision["note"] = "SINTETIC: articolul 07 relatează același eveniment ca articolul 01; păstrăm ambele surse și un singur accident."
            event = _request(client, "POST", f"/api/v1/candidates/{candidate_id}/review", json=decision).json()["event"]
            source_to_event[article["article_id"]] = event["event_id"]

        events = _request(client, "GET", "/api/v1/reviewed-events?data_mode=synthetic").json()["events"]
        if len(events) != 6 or sum(len(event["article_ids"]) for event in events) != 7:
            raise RuntimeError("Identitatea evenimentelor sau proveniența nu corespund scenariului 7 articole / 6 accidente.")
        if any(event["fields"]["cauza_raportata"] is not None for event in events):
            raise RuntimeError("Cauza necunoscută trebuie păstrată necunoscută.")
        selections = []
        for event in events:
            article_index = next(index for index, article in enumerate(articles[:6]) if article["article_id"] in event["article_ids"])
            location = LOCATIONS[SCENARIOS[article_index][0]]
            selections.append({
                "event_id": event["event_id"], "expected_version": event["version"], "location_id": location["id"],
                "association_checked": True,
                "association_note": "SINTETIC: asociere verificată la același punct fictiv din fixture; două evenimente distincte per locație.",
            })
        request = {
            "request_id": "publication-demo-release-01", "data_mode": "synthetic", "operator": OPERATOR,
            "note": "Repetiție locală integral SINTETICĂ; fără modificarea corpusului echipei sau publicare externă.",
            "period_start": "2026-09-01", "period_end": "2026-09-30", "source_conflicts_checked": True,
            "selections": selections,
        }
        preview = _request(client, "POST", "/api/v1/publications/preview", json=request).json()
        _write_json(directory / "preview.json", preview)
        published = _request(client, "POST", "/api/v1/publications", expected=(200, 201), json=request).json()
        _write_json(directory / "published.json", published)
        latest = _request(client, "GET", "/api/v1/publications/latest?data_mode=synthetic").json()
        _write_json(directory / "latest.json", latest)
        locations = _request(client, "GET", "/api/v1/locations?data_mode=synthetic").json()
        if len(locations.get("locations", [])) != 3 or sum(row.get("event_count", 0) for row in locations["locations"]) != 6:
            raise RuntimeError("Publicarea trebuie să expună trei locații, cu șase evenimente canonice în total.")
        _write_json(directory / "locations.json", locations)
        dossier_hashes = {}
        printable_hashes = {}
        for location in LOCATIONS:
            dossier = _request(client, "GET", f"/api/v1/locations/{location['id']}?data_mode=synthetic").json()
            if len(dossier.get("events", [])) != 2:
                raise RuntimeError("Fiecare dosar sintetic trebuie să păstreze exact două evenimente distincte.")
            _write_json(directory / f"{location['id']}.json", dossier)
            exported = _request(client, "GET", f"/api/v1/locations/{location['id']}/export?data_mode=synthetic")
            suffix = ".json" if "json" in exported.headers.get("content-type", "") else ".txt"
            export_file = directory / f"{location['id']}-export{suffix}"
            export_file.write_bytes(exported.content)
            dossier_hashes[location["id"]] = _sha256(export_file)
            printable = _request(client, "GET", f"/api/v1/locations/{location['id']}/export?data_mode=synthetic&format=html")
            if "text/html" not in printable.headers.get("content-type", ""):
                raise RuntimeError("Exportul pentru imprimare trebuie să fie HTML.")
            printable_file = directory / f"{location['id']}-export.html"
            printable_file.write_bytes(printable.content)
            printable_hashes[location["id"]] = _sha256(printable_file)
        if _request(client, "GET", "/api/v1/reviewed-events?data_mode=observed").json()["events"]:
            raise RuntimeError("Repetiția sintetică nu trebuie să creeze evenimente în modul observed.")

    summary = {
        "schema_version": SCHEMA_VERSION, "data_mode": "synthetic", "processing_mode": "rules",
        "publication_scope": "local_demo_only", "directory": str(directory),
        "serve_configuration": {
            "SAFEIASI_REVIEW_DIR": str(directory / "review"),
            "SAFEIASI_PUBLICATION_DIR": str(directory / "publications"),
            "SAFEIASI_PUBLICATION_CONTEXT_DIR": str(directory / "context"),
        },
        "article_count": len(articles), "canonical_event_count": len(events), "location_count": len(LOCATIONS),
        "duplicate_linked": source_to_event[articles[0]["article_id"]] == source_to_event[articles[6]["article_id"]],
        "dossier_export_sha256": dossier_hashes,
        "printable_export_sha256": printable_hashes,
        "warning": "SINTETIC: date inventate; repetiție deterministă, fără evaluare a modelului AI sau a riscului real.",
    }
    _write_json(directory / "proof.json", summary)
    return summary


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Repetiție locală SINTETICĂ: 7 articole → 6 evenimente → 3 dosare; extractor rules, fără Ollama.")
    parser.add_argument("--directory", type=Path, default=DEFAULT_DIRECTORY, help="Director nou și separat; unul existent este refuzat.")
    arguments = parser.parse_args(argv)
    try:
        summary = run_demo(arguments.directory)
    except (ValueError, RuntimeError, OSError, ImportError) as error:
        parser.exit(1, f"Demo oprit; datele existente sunt păstrate: {error}\n")
    print(json.dumps(summary, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
