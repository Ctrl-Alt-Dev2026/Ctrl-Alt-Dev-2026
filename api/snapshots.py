"""Read-only loading of consistent synthetic schema 2.0 snapshots."""

from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
import re

from api.validate_fixtures import FILES, PRECISE_LOCATIONS, audit_documents


SYNTHETIC_WARNING = "DATE SINTETICE - doar pentru dezvoltare, nu dovezi despre accidente reale."
EVENT_FIELDS = (
    "event_id", "article_ids", "urls", "data_eveniment", "ora", "loc_text",
    "precizie_loc", "lat", "lon", "in_iasi", "participanti", "cauza_raportata",
    "gravitate", "noapte", "dovezi", "verificat",
)


class SnapshotError(Exception):
    def __init__(self, code, message, issues=None):
        super().__init__(message)
        self.code, self.message, self.issues = code, message, issues or []

    def detail(self):
        return {"code": self.code, "message": self.message, "issues": deepcopy(self.issues)}


@dataclass(frozen=True)
class Snapshot:
    snapshot_id: str
    manifest: dict
    eligible_events: tuple

    def metadata(self):
        return {
            "snapshot_id": self.snapshot_id, "data_mode": "synthetic",
            "warning": SYNTHETIC_WARNING, "eligible_event_count": len(self.eligible_events),
        }

    def manifest_payload(self):
        return self.metadata() | {"manifest": deepcopy(self.manifest)}

    def events_payload(self):
        return self.metadata() | {"events": deepcopy(list(self.eligible_events))}


def _fingerprint(path):
    stat = path.stat()
    return stat.st_ino, stat.st_size, stat.st_mtime_ns


def _reject_constant(value):
    raise ValueError(f"Non-standard JSON constant: {value}.")


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON object key.")
        result[key] = value
    return result


def _date(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("Expected YYYY-MM-DD.")
    return date.fromisoformat(value)


def load_snapshot(directory):
    """Load one immutable release directory; never write or repair source data."""
    directory, documents, digest = Path(directory), {}, hashlib.sha256()
    try:
        before = {name: _fingerprint(directory / name) for name in FILES}
        for name in FILES:
            raw = (directory / name).read_bytes()
            try:
                documents[name] = json.loads(
                    raw.decode("utf-8-sig"), parse_constant=_reject_constant,
                    object_pairs_hook=_unique_keys,
                )
                # Also reject float overflow and unpaired Unicode surrogates.
                json.dumps(documents[name], allow_nan=False, ensure_ascii=False).encode("utf-8")
            except (ValueError, UnicodeError) as error:
                raise SnapshotError(
                    "invalid_snapshot", "Snapshot-ul conține JSON invalid.",
                    [{"code": "invalid_json", "file": name}],
                ) from error
            digest.update(name.encode("utf-8") + b"\0" + raw)
        after = {name: _fingerprint(directory / name) for name in FILES}
    except OSError as error:
        raise SnapshotError(
            "snapshot_unavailable", "Fișierele snapshot-ului lipsesc sau nu pot fi citite.",
        ) from error
    if before != after:
        raise SnapshotError("snapshot_changed", "Snapshot-ul s-a modificat în timpul citirii.")

    manifest = documents["manifest.json"]
    if isinstance(manifest, dict) and manifest.get("data_mode") == "observed":
        raise SnapshotError(
            "unsupported_data_mode",
            "Publicarea datelor observate nu este implementată; cititorul acceptă doar date sintetice.",
        )
    report = audit_documents(documents)
    if report["issues"]:
        raise SnapshotError(
            "invalid_snapshot", "Snapshot-ul nu trece verificările de consistență.", report["issues"],
        )

    issues = []
    period = manifest.get("perioada")
    try:
        if not isinstance(period, list) or len(period) != 2:
            raise ValueError("Expected two dates.")
        start, end = (_date(value) for value in period)
        if start > end:
            raise ValueError("Reversed period.")
    except ValueError as error:
        raise SnapshotError(
            "invalid_snapshot", "Perioada de analiză lipsește sau este invalidă.",
            [{"code": "invalid_period", "file": "manifest.json"}],
        ) from error
    try:
        generated = manifest.get("generat_la")
        if not isinstance(generated, str) or datetime.fromisoformat(generated).utcoffset() is None:
            raise ValueError("Expected timestamp with offset.")
    except ValueError:
        issues.append({"code": "invalid_generated_at", "file": "manifest.json"})

    events = documents["accidents.json"]
    eligible = []
    for event in events:
        try:
            raw_date = event.get("data_eveniment")
            event_date = None if raw_date is None else _date(raw_date)
        except ValueError:
            issues.append({"code": "invalid_event_date", "file": "accidents.json", "event_id": event["event_id"]})
            continue
        if event.get("in_iasi") is not None and type(event["in_iasi"]) is not bool:
            issues.append({"code": "invalid_municipality_flag", "file": "accidents.json", "event_id": event["event_id"]})
        if event.get("duplicate_of") is not None:
            # Schema 2.0 read snapshots must already contain canonical events.
            # Silently dropping duplicates here could discard their sources.
            issues.append({"code": "noncanonical_event", "file": "accidents.json", "event_id": event["event_id"]})
        if (
            event.get("verificat") is True and event.get("in_iasi") is True
            and event.get("precizie_loc") in PRECISE_LOCATIONS
            and event.get("lat") is not None and event.get("lon") is not None
            and event_date is not None and start <= event_date <= end
        ):
            eligible.append({key: event[key] for key in EVENT_FIELDS if key in event})
    if issues:
        raise SnapshotError("invalid_snapshot", "Metadatele evenimentelor sunt invalide.", issues)
    return Snapshot("sha256:" + digest.hexdigest(), deepcopy(manifest), tuple(eligible))
