"""Read-only consistency audit for the team's synthetic schema 2.0 fixtures."""

import argparse
import json
import math
from pathlib import Path


FILES = (
    "manifest.json", "articles.json", "accidents.json",
    "crossings.geojson", "hotspots.json", "measure.json",
)
PRECISE_LOCATIONS = {"trecere", "intersectie", "segment"}
LOCATION_PRECISIONS = PRECISE_LOCATIONS | {"strada", "vag"}


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _coordinates(lon, lat):
    return _number(lon) and _number(lat) and -180 <= lon <= 180 and -90 <= lat <= 90


def audit_fixtures(directory):
    """Return diagnostics without changing files or calculating priority scores."""
    directory = Path(directory)
    issues = []

    def issue(code, filename, detail):
        issues.append({"code": code, "file": filename, "detail": detail})

    report = {
        "scope": "synthetic_fixtures_only",
        "warning": "DATE SINTETICE - audit de consistenta, fara validare factuala.",
        "counts": {}, "issues": issues,
    }
    documents = {}
    for name in FILES:
        try:
            documents[name] = json.loads((directory / name).read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as error:
            issue("unreadable_json", name, str(error))
    if issues:
        return report

    manifest = documents["manifest.json"]
    if not isinstance(manifest, dict):
        issue("invalid_shape", "manifest.json", "Expected a JSON object.")
        return report
    if manifest.get("data_mode") != "synthetic":
        issue("wrong_data_mode", "manifest.json", "This audit accepts synthetic fixtures only.")
    if manifest.get("schema_version") != "2.0":
        issue("wrong_schema", "manifest.json", "Expected schema_version 2.0.")

    crossings = documents["crossings.geojson"]
    if not isinstance(crossings, dict) or crossings.get("type") != "FeatureCollection":
        issue("invalid_shape", "crossings.geojson", "Expected a GeoJSON FeatureCollection.")
        return report
    collections = {
        name: documents[name] for name in ("articles.json", "accidents.json", "hotspots.json", "measure.json")
    }
    collections["crossings.geojson"] = crossings.get("features")
    for name, items in collections.items():
        if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
            issue("invalid_shape", name, "Expected a list of objects.")
    if any(item["code"] == "invalid_shape" for item in issues):
        return report

    def index(items, key, filename):
        result = {}
        for item in items:
            identifier = item.get(key)
            if not isinstance(identifier, str) or not identifier.strip():
                issue("invalid_id", filename, f"Missing or invalid {key}.")
            elif identifier in result:
                issue("duplicate_id", filename, f"Duplicate {key}: {identifier}.")
            else:
                result[identifier] = item
        return result

    articles = index(collections["articles.json"], "article_id", "articles.json")
    events = index(collections["accidents.json"], "event_id", "accidents.json")
    locations = index(collections["hotspots.json"], "id", "hotspots.json")
    measures = index(collections["measure.json"], "id", "measure.json")
    crossing_properties = []
    for feature in collections["crossings.geojson"]:
        properties, geometry = feature.get("properties"), feature.get("geometry")
        if feature.get("type") != "Feature" or not isinstance(properties, dict):
            issue("invalid_feature", "crossings.geojson", "Expected Feature with properties.")
            continue
        crossing_properties.append(properties)
        coords = geometry.get("coordinates") if isinstance(geometry, dict) else None
        if (not isinstance(geometry, dict) or geometry.get("type") != "Point"
                or not isinstance(coords, list) or len(coords) != 2 or not _coordinates(*coords)):
            issue("invalid_coordinates", "crossings.geojson", f"Invalid Point for {properties.get('id')}.")
    crossing_ids = index(crossing_properties, "id", "crossings.geojson")

    def references(item, field, known, filename):
        values = item.get(field)
        if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
            issue("invalid_references", filename, f"{field} must be a list of IDs.")
            return []
        if field == "article_ids" and not values:
            issue("missing_reference", filename, "An event must reference at least one article.")
        if len(set(values)) != len(values):
            issue("duplicate_reference", filename, f"Duplicate IDs in {field}.")
        missing = sorted(set(values) - set(known))
        if missing:
            issue("missing_reference", filename, f"{field}: {', '.join(missing)}.")
        return values

    precise_count = reviewed_count = 0
    for event in events.values():
        references(event, "article_ids", articles, "accidents.json")
        precision = event.get("precizie_loc")
        lat, lon = event.get("lat"), event.get("lon")
        if not isinstance(precision, str) or precision not in LOCATION_PRECISIONS:
            issue("invalid_precision", "accidents.json", f"Invalid precision for {event['event_id']}.")
        if precision == "vag" and (lat is not None or lon is not None):
            issue("vague_point", "accidents.json", f"Vague location has coordinates: {event['event_id']}.")
        if (lat is not None or lon is not None) and not _coordinates(lon, lat):
            issue("invalid_coordinates", "accidents.json", f"Invalid lat/lon for {event['event_id']}.")
        if type(event.get("verificat")) is not bool:
            issue("invalid_review_flag", "accidents.json", f"Expected boolean for {event['event_id']}.")
        precise_count += (isinstance(precision, str) and precision in PRECISE_LOCATIONS and event.get("in_iasi") is True
                          and _coordinates(lon, lat))
        reviewed_count += event.get("verificat") is True

    counts = {
        "nr_articole": len(collections["articles.json"]),
        "nr_evenimente": len(collections["accidents.json"]),
        "nr_localizate_precis": precise_count, "nr_verificate": reviewed_count,
    }
    report["counts"] = counts | {"crossings": len(crossing_properties), "hotspots": len(locations), "measures": len(measures)}
    for key, actual in counts.items():
        declared = manifest.get(key)
        if type(declared) is not int or declared != actual:
            issue("manifest_count_mismatch", "manifest.json", f"{key}: declared {declared}, actual {actual}.")

    for location in locations.values():
        event_ids = references(location, "event_ids", events, "hotspots.json")
        if location.get("nr_evenimente") != len(set(event_ids)):
            issue("location_count_mismatch", "hotspots.json", f"Event count mismatch for {location['id']}.")
        crossing_id = location.get("crossing_id")
        if not isinstance(crossing_id, str) or crossing_id not in crossing_ids:
            issue("missing_reference", "hotspots.json", f"Unknown crossing for {location['id']}.")
        recommendations = location.get("masuri")
        if not isinstance(recommendations, list) or any(not isinstance(item, dict) for item in recommendations):
            issue("invalid_shape", "hotspots.json", f"Invalid masuri for {location['id']}.")
        else:
            for recommendation in recommendations:
                measure_id = recommendation.get("measure_id")
                if not isinstance(measure_id, str) or measure_id not in measures:
                    issue("missing_reference", "hotspots.json", f"Unknown measure for {location['id']}.")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", nargs="?", type=Path, default=Path("false_data"))
    args = parser.parse_args()
    report = audit_fixtures(args.directory)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["issues"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
