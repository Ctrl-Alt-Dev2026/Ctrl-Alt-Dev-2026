"""Read-only infrastructure context for explicitly associated reviewed events.

The geometry stack is optional and imported only when a publication context is
loaded. Proximity validates an operator's selected association; it never chooses
one. This adapter calls the team's existing deterministic scorer unchanged.
"""

from copy import deepcopy
from datetime import date, datetime, timezone
import hashlib
import json
import marshal
import math
from pathlib import Path
import re
import sys
from types import CodeType


SCHEMA_VERSION = "publication-context-1"
DEFAULT_CONTEXT = Path(__file__).resolve().parents[1] / "context/output/observed/iasi"
MAX_CONTEXT_BYTES = 16 * 1024 * 1024
TRISTATES = ("semafor", "iluminat", "scoala_150m", "statie_100m")


class PublicationContextError(Exception):
    def __init__(self, code, message, status_code=503):
        super().__init__(message)
        self.code, self.message = code, message
        self.status_code = self.status = status_code

    def detail(self):
        return {"code": self.code, "message": self.message}


def _invalid(message):
    raise PublicationContextError("invalid_publication_context", message)


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("Non-finite JSON constant")


def _text(value, maximum=10_000):
    return isinstance(value, str) and 0 < len(value.strip()) <= maximum


def _date(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        _invalid("Data contextului trebuie să fie YYYY-MM-DD.")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise PublicationContextError("invalid_publication_context", "Dată invalidă în context.") from error


def _instant(value):
    if not _text(value, 80):
        _invalid("Lipsește momentul colectării/generării contextului.")
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if instant.tzinfo is None or instant.utcoffset() is None:
            raise ValueError("Timezone required")
        return instant
    except ValueError as error:
        raise PublicationContextError("invalid_publication_context", "Momentul contextului necesită fus orar explicit.") from error


def _coordinates(value):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return False
    lon, lat = value
    # Compare bounded ranges before float conversion: arbitrary JSON integers
    # can be finite integers while overflowing math.isfinite's float coercion.
    return (all(type(v) in (int, float) for v in value)
            and -180 <= lon <= 180 and -90 <= lat <= 90
            and all(math.isfinite(v) for v in value))


def _polygon_coordinates(geometry):
    """Validate every coordinate before GEOS can interpret malformed values."""
    coordinates = geometry.get("coordinates")
    polygons = [coordinates] if geometry.get("type") == "Polygon" else coordinates
    if not isinstance(polygons, list) or not polygons:
        _invalid("Limita administrativă nu are poligoane.")
    for polygon in polygons:
        if not isinstance(polygon, list) or not polygon:
            _invalid("Poligon administrativ incomplet.")
        for ring in polygon:
            if (not isinstance(ring, list) or len(ring) < 4 or ring[0] != ring[-1]
                    or any(not _coordinates(c) for c in ring)):
                _invalid("Inel sau coordonate invalide în limita administrativă.")


def _read_documents(directory, names):
    """Pin all files across one read; refuse path aliases and partial releases."""
    try:
        root = Path(directory).resolve(strict=True)
        if not root.is_dir():
            raise OSError("Not a directory")
        paths = {name: root / name for name in names}
        for path in paths.values():
            if path.is_symlink() or path.resolve(strict=True).parent != root:
                raise OSError("Context file must stay inside the configured directory")
        def stat(path):
            info = path.stat()
            if not path.is_file() or not 0 < info.st_size <= MAX_CONTEXT_BYTES:
                raise OSError("Invalid context file size")
            return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns
        before = {name: stat(path) for name, path in paths.items()}
        raw = {name: path.read_bytes() for name, path in paths.items()}
        after = {name: stat(path) for name, path in paths.items()}
    except OSError as error:
        raise PublicationContextError("publication_context_unavailable", "Contextul configurat lipsește sau nu poate fi citit în siguranță.") from error
    if before != after or any(len(raw[name]) != before[name][2] for name in names):
        raise PublicationContextError("publication_context_changed", "Contextul s-a modificat în timpul citirii; reîncercați.")
    documents = {}
    try:
        for name, content in raw.items():
            documents[name] = json.loads(content.decode("utf-8-sig"), object_pairs_hook=_unique_keys,
                                         parse_constant=_reject_constant)
            json.dumps(documents[name], allow_nan=False, ensure_ascii=False).encode("utf-8")
    except (ValueError, UnicodeError, RecursionError) as error:
        raise PublicationContextError("invalid_publication_context", "Contextul conține JSON invalid sau valori nefinite.") from error
    hashes = {name: hashlib.sha256(content).hexdigest() for name, content in raw.items()}
    digest = hashlib.sha256()
    for name in sorted(raw):
        digest.update(name.encode("utf-8") + b"\0" + raw[name])
    return documents, hashes, digest.hexdigest()


def _synthetic_provenance(documents, hashes):
    manifest = documents["publication-context.json"]
    if (not isinstance(manifest, dict)
            or set(manifest) != {"schema_version", "data_mode", "provenance", "generated_at", "files"}
            or manifest.get("schema_version") != SCHEMA_VERSION or manifest.get("data_mode") != "synthetic"
            or not _text(manifest.get("provenance"))):
        _invalid("Manifestul sintetic trebuie să declare schema, modul, proveniența, momentul și hash-urile fișierelor.")
    _instant(manifest["generated_at"])
    expected = {name: hashes[name] for name in ("boundary.geojson", "crossings.geojson")}
    if manifest["files"] != expected:
        _invalid("Hash-urile geometriei nu corespund manifestului sintetic.")
    return {"provenance": manifest["provenance"], "generated_at": manifest["generated_at"],
            "attribution": "DATE SINTETICE — fără dovezi despre infrastructura sau accidentele reale."}


def _observed_provenance(documents):
    report = documents["geometry_report.json"]
    if not isinstance(report, dict) or report.get("data_mode") != "observed":
        _invalid("Contextul OSM trebuie să declare data_mode observed.")
    tags = report.get("boundary_tags", {})
    if (report.get("boundary_relation_id") != 1207838 or not isinstance(tags, dict)
            or tags.get("boundary") != "administrative" or tags.get("admin_level") != "8"
            or str(tags.get("name", "")).replace("ş", "ș") != "Iași"
            or report.get("crs") != "EPSG:32635" or not _text(report.get("attribution"))):
        _invalid("Raportul nu identifică limita Municipiului Iași și proveniența OSM.")
    boundary = documents["boundary.geojson"]
    properties = boundary.get("properties", {}) if isinstance(boundary, dict) else {}
    if (not isinstance(properties, dict) or properties.get("osm_relation_id") != 1207838 or properties.get("boundary") != "administrative"
            or properties.get("admin_level") != "8" or str(properties.get("name", "")).replace("ş", "ș") != "Iași"):
        _invalid("Geometria limitei nu identifică Municipiul Iași.")
    source = report.get("boundary_source")
    collection = report.get("collection_sources")
    interval = report.get("collection_date_range")
    if (not isinstance(source, dict) or not _text(source.get("endpoint"))
            or not isinstance(collection, list) or not collection
            or not isinstance(interval, list) or len(interval) != 2):
        _invalid("Proveniența și perioada colectării OSM sunt incomplete.")
    _instant(source.get("fetched_at"))
    start, end = map(_instant, interval)
    if start > end:
        _invalid("Perioadă de colectare inversată.")
    for item in collection:
        if (not isinstance(item, dict) or not _text(item.get("endpoint"))
                or not isinstance(item.get("query_hash"), str)
                or not re.fullmatch(r"[a-f0-9]{64}", item["query_hash"])):
            _invalid("Lipsește proveniența unei colecții OSM.")
        if not start <= _instant(item.get("fetched_at")) <= end:
            _invalid("Momentul colectării nu aparține perioadei declarate.")
    _date(report.get("crossing_downloaded"))
    return {"provenance": report["area"] if _text(report.get("area")) else "Context municipal OSM Iași",
            "attribution": report["attribution"], "boundary_relation_id": 1207838,
            "boundary_source": deepcopy(source), "collection_sources": deepcopy(collection),
            "collection_date_range": deepcopy(interval)}


def _validate_observed_evidence(features, report):
    evidence = report.get("crossings")
    if not isinstance(evidence, list) or len(evidence) != len(features):
        _invalid("Raportul OSM nu acoperă toate locațiile.")
    indexed = {}
    for item in evidence:
        if not isinstance(item, dict) or not _text(item.get("id")) or item["id"] in indexed:
            _invalid("Identități lipsă sau duplicate în dovezile OSM.")
        indexed[item["id"]] = item
    for feature in features:
        p = feature["properties"]
        item = indexed.get(p["id"], {})
        tags = item.get("crossing_tags", {})
        if (p["tip"] != "trecere" or not isinstance(tags, dict) or tags.get("highway") != "crossing"
                or type(tags.get("osm_id")) is not int or p["id"] != f"osm-node-{tags['osm_id']}"):
            _invalid("Identitatea locației nu corespunde nodului OSM din dovezi.")
        if any(tags.get(field) is not None and not isinstance(tags[field], str)
               for field in ("crossing", "crossing:signals", "lit")):
            _invalid("Tag OSM invalid în dovezile locației.")
        legacy = {"traffic_signals": True, "uncontrolled": False}.get(tags.get("crossing"))
        explicit = {"yes": True, "no": False}.get(tags.get("crossing:signals"))
        signal = None if legacy is not None and explicit is not None and legacy != explicit else explicit if explicit is not None else legacy
        if p.get("semafor") is not signal or p.get("iluminat") is not {"yes": True, "no": False}.get(tags.get("lit")):
            _invalid("Semaforizarea sau iluminatul nu corespund tag-urilor explicite OSM.")
        if p.get("benzi") != item.get("road_lanes") or p.get("tip_strada") != item.get("road_type"):
            _invalid("Contextul stradal nu corespunde raportului OSM.")
        for field, evidence_key, threshold in (("scoala_150m", "schools_150m", 150), ("statie_100m", "stops_100m", 100)):
            matches = item.get(evidence_key)
            if not isinstance(matches, list):
                _invalid("Dovezi de proximitate OSM incomplete.")
            for match in matches:
                distance = match.get("distance_m") if isinstance(match, dict) else None
                if type(distance) not in (int, float) or not 0 <= distance <= threshold or not math.isfinite(distance):
                    _invalid("Distanță invalidă în dovezile OSM.")
            if p.get(field) is not (True if matches else None):
                _invalid("Absența POI din OSM trebuie să rămână necunoscută.")


class ContextDataset:
    def __init__(self, features, boundary, projector, metadata):
        self._features = {f["properties"]["id"]: deepcopy(f) for f in features}
        self._boundary, self._projector, self._metadata = boundary, projector, deepcopy(metadata)

    @property
    def metadata(self):
        return deepcopy(self._metadata)

    def feature(self, location_id):
        if not isinstance(location_id, str) or location_id not in self._features:
            raise PublicationContextError("unknown_location", "Locația selectată nu există în contextul verificat.", 404)
        return deepcopy(self._features[location_id])

    def all_features(self):
        return deepcopy(list(self._features.values()))

    def check_event(self, fields, location_id):
        from shapely.geometry import Point
        if not isinstance(fields, dict):
            return ["invalid_event_fields"]
        reasons = []
        if fields.get("data_mode", self._metadata["data_mode"]) != self._metadata["data_mode"]:
            reasons.append("data_mode_mismatch")
        if fields.get("in_iasi") is not True:
            reasons.append("in_iasi_not_confirmed")
        try:
            feature = self.feature(location_id)
        except PublicationContextError as error:
            if error.code == "unknown_location":
                return reasons + ["location_not_found"]
            raise
        if fields.get("precizie_loc") != feature["properties"]["tip"]:
            reasons.append("precision_mismatch")
        coordinates = [fields.get("lon"), fields.get("lat")]
        if any(value is None for value in coordinates):
            reasons.append("coordinates_missing")
        elif not _coordinates(coordinates):
            reasons.append("invalid_coordinates")
        else:
            if not self._boundary.covers(Point(coordinates)):
                reasons.append("outside_iasi_boundary")
                return reasons
            source = self._projector.transform(*coordinates, errcheck=True)
            target = self._projector.transform(*feature["geometry"]["coordinates"], errcheck=True)
            if math.dist(source, target) > 50:
                reasons.append("location_too_far")
        return reasons

    def score(self, feature, events_flat):
        canonical = self.feature(feature.get("properties", {}).get("id"))
        if canonical != feature:
            raise PublicationContextError("context_feature_mismatch", "Locația scorată diferă de contextul verificat.")
        scorer_provenance()
        return score_location(canonical, events_flat)

    def score_location(self, location_id, events_flat):
        return self.score(self.feature(location_id), events_flat)


def scorer_provenance():
    """Bind source provenance to the function actually executing in this process."""
    try:
        from risk.pipeline import score_location as loaded
        source = Path(loaded.__code__.co_filename).read_bytes()
        compiled = compile(source, loaded.__code__.co_filename, "exec", optimize=sys.flags.optimize)
        candidates = [constant for constant in compiled.co_consts
                      if isinstance(constant, CodeType) and constant.co_name == "score_location"]
        if len(candidates) != 1 or candidates[0] != loaded.__code__:
            raise PublicationContextError(
                "scorer_changed_restart_required",
                "Formula de pe disc diferă de funcția încărcată; reporniți serverul înainte de publicare.",
            )
        return {"source_sha256": hashlib.sha256(source).hexdigest(),
                "callable_sha256": hashlib.sha256(marshal.dumps(loaded.__code__)).hexdigest(),
                "function_name": "risk.pipeline.score_location", "python_version": sys.version.split()[0]}
    except ImportError as error:
        raise PublicationContextError("publication_dependencies_missing", "Instalați requirements-publication.txt pentru scor și geometrie.") from error
    except (OSError, SyntaxError, ValueError, TypeError, AttributeError) as error:
        raise PublicationContextError("scorer_changed_restart_required", "Formula nu poate fi verificată; reporniți serverul după verificarea fișierului risk/pipeline.py.") from error


def score_location(feature, events_flat):
    """The caller filters the selected period; the original formula stays intact."""
    try:
        from risk.pipeline import score_location as existing_score
    except ImportError as error:
        raise PublicationContextError("publication_dependencies_missing", "Instalați requirements-publication.txt pentru scor și geometrie.") from error
    try:
        if not isinstance(events_flat, list):
            raise ValueError("Expected a list")
        ids = [event.get("event_id") for event in events_flat]
        if any(not _text(identifier, 200) for identifier in ids) or len(ids) != len(set(ids)):
            raise ValueError("Events must be distinct")
        if any(event.get("gravitate") not in ("deces", "grav", "usor", "necunoscut") for event in events_flat):
            raise ValueError("Invalid severity")
        result = existing_score(deepcopy(feature), deepcopy(events_flat))
        json.dumps(result, allow_nan=False)
        return result
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        raise PublicationContextError("invalid_score_input", "Datele nu respectă contractul scorului determinist.", 422) from error


def load_context(directory=DEFAULT_CONTEXT, mode="observed"):
    if mode not in ("synthetic", "observed"):
        raise PublicationContextError("invalid_data_mode", "Modul contextului trebuie să fie synthetic sau observed.", 422)
    names = ("boundary.geojson", "crossings.geojson", "publication-context.json" if mode == "synthetic" else "geometry_report.json")
    documents, hashes, fingerprint = _read_documents(directory, names)
    provenance = _synthetic_provenance(documents, hashes) if mode == "synthetic" else _observed_provenance(documents)
    try:
        from pyproj import Transformer
        from shapely import transform
        from shapely.geometry import Point, shape
    except ImportError as error:
        raise PublicationContextError("publication_dependencies_missing", "Instalați requirements-publication.txt pentru publicarea pe hartă.") from error
    boundary_document = documents["boundary.geojson"]
    if not isinstance(boundary_document, dict):
        _invalid("Limită administrativă invalidă.")
    geometry = boundary_document.get("geometry") if boundary_document.get("type") == "Feature" else boundary_document
    if not isinstance(geometry, dict) or geometry.get("type") not in ("Polygon", "MultiPolygon"):
        _invalid("Limita administrativă trebuie să fie Polygon sau MultiPolygon.")
    _polygon_coordinates(geometry)
    try:
        boundary = shape(geometry)
        projector = Transformer.from_crs(4326, 32635, always_xy=True)
        area = transform(boundary, projector.transform, interleaved=False).area
        if boundary.is_empty or not boundary.is_valid or not math.isfinite(area) or not 10_000 <= area <= 1_000_000_000:
            _invalid("Limita administrativă este invalidă sau are o suprafață neplauzibilă.")
        west, south, east, north = boundary.bounds
        if not (27.3 <= west < east <= 27.9 and 47.0 <= south < north <= 47.4):
            _invalid("Limita nu se află în zona Municipiului Iași; verificați ordinea longitudine, latitudine.")
        if mode == "observed" and (not boundary.covers(Point(27.5877, 47.1564)) or not 50_000_000 <= area <= 150_000_000):
            _invalid("Limita observată nu este o limită municipală Iași plauzibilă.")
    except PublicationContextError:
        raise
    except (ValueError, TypeError, OverflowError) as error:
        raise PublicationContextError("invalid_publication_context", "Geometria limitei nu poate fi proiectată.") from error
    crossings = documents["crossings.geojson"]
    if (not isinstance(crossings, dict) or crossings.get("type") != "FeatureCollection"
            or not isinstance(crossings.get("features"), list) or not 0 < len(crossings["features"]) <= 50_000):
        _invalid("Contextul trebuie să conțină o colecție de locații.")
    features, seen = crossings["features"], set()
    boundary_with_roundtrip_tolerance = boundary.buffer(1e-10)
    for feature in features:
        if not isinstance(feature, dict) or feature.get("type") != "Feature":
            _invalid("Locație GeoJSON invalidă.")
        p, g = feature.get("properties"), feature.get("geometry")
        if (not isinstance(p, dict) or not isinstance(p.get("id"), str)
                or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,160}", p["id"]) or p["id"] in seen
                or p.get("tip") not in ("trecere", "intersectie") or not isinstance(g, dict)
                or g.get("type") != "Point" or not _coordinates(g.get("coordinates"))):
            _invalid("Identitate, tip sau coordonate invalide/duplicate pentru o locație.")
        seen.add(p["id"])
        if (p.get("sursa") != ("SINTETIC" if mode == "synthetic" else "OSM")
                or p.get("data_mode", mode) != mode):
            _invalid("Proveniența locației nu corespunde modului contextului.")
        _date(p.get("descarcat_la"))
        if any(p.get(field) is not None and type(p[field]) is not bool for field in TRISTATES):
            _invalid("Tag-urile infrastructurii trebuie să fie true, false sau null.")
        if p.get("benzi") is not None and (type(p["benzi"]) is not int or not 1 <= p["benzi"] <= 30):
            _invalid("Număr de benzi invalid; valoarea necunoscută rămâne null.")
        if p.get("tip_strada") is not None and not _text(p["tip_strada"], 120):
            _invalid("Tip stradal invalid.")
        if p.get("nume") is not None and not _text(p["nume"], 1000):
            _invalid("Nume de locație invalid.")
        if not boundary_with_roundtrip_tolerance.covers(Point(g["coordinates"])):
            _invalid("O locație de infrastructură se află în afara limitei Iași.")
    if mode == "observed":
        _validate_observed_evidence(features, documents["geometry_report.json"])
    metadata = {"schema_version": SCHEMA_VERSION, "data_mode": mode, "fingerprint": fingerprint,
                "file_hashes": hashes, "loaded_at": datetime.now(timezone.utc).isoformat(),
                "location_count": len(features), "boundary_area_km2": round(area / 1e6, 6),
                "association_max_distance_m": 50, "association_method": "explicit_operator_selection",
                **provenance}
    return ContextDataset(features, boundary, projector, metadata)
