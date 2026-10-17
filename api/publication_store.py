"""Immutable local releases, with a single atomic index as the commit point.

One process is supported, just like the review store. Publication never changes
review records or source fixtures. An unindexed file is not a published release.
"""

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import threading
from uuid import uuid4

from api.publication_models import PublicationRequest
from api.review_store import ReviewError, _LOCK as _REVIEW_LOCK


_LOCK = threading.RLock()
_REPOSITORY = Path(__file__).resolve().parents[1]
_MAX_BYTES = 64 * 1024 * 1024
_SNAPSHOT_ID = re.compile(r"^pub_[a-f0-9]{32}$")
_DIGEST = re.compile(r"^[a-f0-9]{64}$")


class PublicationError(Exception):
    def __init__(self, status, code, message, issues=None):
        self.status, self.code, self.message, self.issues = status, code, message, issues
        super().__init__(message)


def _serialized(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")


def _digest(value):
    return hashlib.sha256(_serialized(value)).hexdigest()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _read_json(path):
    if path.is_symlink() or path.stat().st_size > _MAX_BYTES:
        raise ValueError("unsafe or oversized publication file")
    raw = path.read_bytes()
    if len(raw) > _MAX_BYTES:
        raise ValueError("oversized publication file")
    document = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                          parse_constant=lambda value: (_ for _ in ()).throw(ValueError("nonfinite JSON")))
    if not isinstance(document, dict):
        raise ValueError("publication document must be an object")
    _serialized(document)
    return document


def _unavailable(error=None):
    return PublicationError(503, "publication_store_unavailable", "Publicația nu poate fi citită sau salvată; datele existente nu au fost înlocuite.")


class PublicationStore:
    def __init__(self, directory, mode, review_store, context_directory):
        if mode not in ("synthetic", "observed") or review_store.mode != mode:
            raise PublicationError(422, "invalid_data_mode", "Modurile review și publicație trebuie să coincidă.")
        self.directory, self.mode = Path(directory).resolve(), mode
        protected = [_REPOSITORY / name for name in ("false_data", "ai", ".git", "context", "risk", "coordonate")]
        protected.extend((review_store.directory.resolve(), Path(context_directory).resolve()))
        if any(self.directory.is_relative_to(path) or path.is_relative_to(self.directory) for path in protected):
            raise PublicationError(503, "protected_publication_directory", "Publicațiile necesită un director separat de sursele și modulele comune.")
        self.mode_directory = self.directory / mode
        self.index_path = self.mode_directory / "latest.json"
        self.review_store, self.context_directory = review_store, Path(context_directory).resolve()

    def _safe_directory(self):
        if self.mode_directory.resolve() != self.mode_directory:
            raise ValueError("symlinked publication directory")

    def _index(self):
        try:
            self._safe_directory()
            if not self.index_path.exists():
                return {"schema_version": "publication-index-1", "data_mode": self.mode,
                        "latest_snapshot_id": None, "requests": {}, "snapshots": {}}
            index = _read_json(self.index_path)
            if (set(index) != {"schema_version", "data_mode", "latest_snapshot_id", "requests", "snapshots"}
                    or index["schema_version"] != "publication-index-1" or index["data_mode"] != self.mode
                    or not isinstance(index["requests"], dict) or not isinstance(index["snapshots"], dict)):
                raise ValueError("invalid publication index")
            for snapshot_id, summary in index["snapshots"].items():
                if (not _SNAPSHOT_ID.fullmatch(snapshot_id) or not isinstance(summary, dict)
                        or not _DIGEST.fullmatch(summary.get("content_sha256", ""))
                        or not isinstance(summary.get("published_at"), str)
                        or type(summary.get("event_count")) is not int or summary["event_count"] < 1
                        or type(summary.get("location_count")) is not int or summary["location_count"] < 1):
                    raise ValueError("invalid snapshot index entry")
            referenced = set()
            for request_id, entry in index["requests"].items():
                if (not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", request_id)
                        or not isinstance(entry, dict) or set(entry) != {"request_hash", "snapshot_id"}
                        or not _DIGEST.fullmatch(entry.get("request_hash", ""))
                        or entry["snapshot_id"] not in index["snapshots"]):
                    raise ValueError("invalid publication request entry")
                referenced.add(entry["snapshot_id"])
            if referenced != set(index["snapshots"]):
                raise ValueError("unreferenced indexed snapshot")
            latest = index["latest_snapshot_id"]
            if (latest is None) != (not index["snapshots"]) or latest is not None and latest not in index["snapshots"]:
                raise ValueError("invalid latest snapshot")
            if latest is not None:
                self._snapshot(index, latest)
            return index
        except (OSError, ValueError, KeyError, TypeError, UnicodeError, RecursionError) as error:
            raise _unavailable() from error

    def _snapshot(self, index, snapshot_id):
        if not isinstance(snapshot_id, str) or not _SNAPSHOT_ID.fullmatch(snapshot_id) or snapshot_id not in index["snapshots"]:
            raise PublicationError(404, "publication_not_found", "Publicație inexistentă în modul ales.")
        try:
            data = _read_json(self.mode_directory / f"{snapshot_id}.json")
            summary = index["snapshots"][snapshot_id]
            digest = data.get("content_sha256")
            if (data.get("schema_version") != "publication-1" or data.get("snapshot_id") != snapshot_id
                    or data.get("data_mode") != self.mode or data.get("publication_status") != "published"
                    or digest != summary["content_sha256"]
                    or _digest({k: v for k, v in data.items() if k != "content_sha256"}) != digest):
                raise ValueError("snapshot identity or digest mismatch")
            request = PublicationRequest.model_validate(data["request"])
            request_entry = index["requests"][request.request_id]
            if (request.data_mode != self.mode or data["request_id"] != request.request_id
                    or data["request_hash"] != _digest(request.model_dump())
                    or request_entry != {"request_hash": data["request_hash"], "snapshot_id": snapshot_id}
                    or data["published_at"] != summary["published_at"]
                    or len(data["events"]) != summary["event_count"]
                    or len(data["locations"]) != summary["location_count"]
                    or data["eligible_event_count"] != len(data["events"]) or data["excluded_event_count"] != 0):
                raise ValueError("snapshot metadata mismatch")
            event_ids = [event["event_id"] for event in data["events"]]
            selected = {s.event_id: s for s in request.selections}
            if len(event_ids) != len(set(event_ids)) or set(event_ids) != set(selected):
                raise ValueError("snapshot event identity mismatch")
            for event in data["events"]:
                if (event["data_mode"] != self.mode or event["publication_status"] != "published"
                        or event["verificat"] is not True
                        or event["version"] != selected[event["event_id"]].expected_version
                        or event["association"]["location_id"] != selected[event["event_id"]].location_id
                        or event["association"]["checked"] is not True or not event["source_articles"]):
                    raise ValueError("invalid published event")
            grouped_ids = []
            location_ids = []
            for location in data["locations"]:
                location_ids.append(location["location_id"])
                if location["event_count"] != len(location["event_ids"]) or not location["event_ids"]:
                    raise ValueError("invalid location count")
                grouped_ids.extend(location["event_ids"])
                if any(selected[identifier].location_id != location["location_id"] for identifier in location["event_ids"]):
                    raise ValueError("invalid location association")
            if len(location_ids) != len(set(location_ids)) or sorted(grouped_ids) != sorted(event_ids):
                raise ValueError("invalid location identity")
            return data
        except (OSError, ValueError, KeyError, TypeError, UnicodeError, RecursionError) as error:
            raise _unavailable() from error

    def get(self, snapshot_id):
        with _LOCK:
            return self._snapshot(self._index(), snapshot_id)

    def latest(self):
        with _LOCK:
            index = self._index()
            if index["latest_snapshot_id"] is None:
                raise PublicationError(404, "publication_not_found", "Nu există încă o publicație în modul ales.")
            return self._snapshot(index, index["latest_snapshot_id"])

    def list_snapshots(self):
        with _LOCK:
            index = self._index()
            # Validate every visible release, never advertise corrupt records.
            records = []
            for identifier, summary in index["snapshots"].items():
                self._snapshot(index, identifier)
                records.append({"snapshot_id": identifier, "data_mode": self.mode, **summary,
                                "latest": identifier == index["latest_snapshot_id"]})
            return sorted(records, key=lambda row: (row["published_at"], row["snapshot_id"]), reverse=True)

    def _build(self, request):
        from api.publication_context import load_context, scorer_provenance, PublicationContextError
        if request.data_mode != self.mode:
            raise PublicationError(422, "invalid_data_mode", "Modul cererii diferă de modul publicației.")
        try:
            if self.review_store.path.exists() and self.review_store.path.stat().st_size > _MAX_BYTES:
                raise PublicationError(503, "review_store_unavailable", "Stocarea review depășește limita de publicare.")
            document = self.review_store._read()
        except ReviewError as error:
            raise PublicationError(error.status, error.code, error.message) from error
        except OSError as error:
            raise PublicationError(503, "review_store_unavailable", "Stocarea review nu poate fi citită în siguranță.") from error
        for selection in request.selections:
            event = document.events.get(selection.event_id)
            if event is None:
                raise PublicationError(404, "event_not_found", "Eveniment canonic inexistent; candidații pending/rejected nu se publică.")
            if event.version != selection.expected_version:
                raise PublicationError(409, "event_version_conflict", "Evenimentul a fost modificat; recitește versiunea curentă.")
        try:
            context = load_context(self.context_directory, self.mode)
            events, diagnostics, grouped = [], [], {}
            for selection in request.selections:
                event = document.events[selection.event_id]
                fields = event.fields.model_dump()
                reasons = []
                if fields["data_eveniment"] is None:
                    reasons.append("event_date_unknown")
                elif not request.period_start <= fields["data_eveniment"] <= request.period_end:
                    reasons.append("outside_analysis_period")
                if fields["in_iasi"] is not True:
                    reasons.append("outside_iasi" if fields["in_iasi"] is False else "iasi_membership_unknown")
                if fields["lat"] is None or fields["lon"] is None:
                    reasons.append("coordinates_missing")
                if fields["precizie_loc"] not in ("trecere", "intersectie"):
                    reasons.append("location_precision_insufficient")
                if not fields["location_evidence"] or not any(entry.changes.get("location_checked") is True for entry in event.history):
                    reasons.append("location_check_evidence_missing")
                if not event.verificat or any(not (entry.changes.get("source_checked") is True and entry.changes.get("duplicate_checked") is True) for entry in event.history):
                    reasons.append("source_review_incomplete")
                reasons.extend(context.check_event(fields, selection.location_id))
                reasons = list(dict.fromkeys(reasons))
                diagnostics.append({"event_id": event.event_id, "location_id": selection.location_id,
                                    "status": "excluded" if reasons else "eligible", "reasons": reasons})
                if reasons:
                    continue
                articles = {}
                for candidate_id in event.candidate_ids:
                    candidate = document.candidates[candidate_id]
                    article = document.imports[candidate.import_id].article
                    articles[article.article_id] = article.model_dump()
                published = event.model_dump() | {
                    "publication_status": "not_published", "source_articles": list(articles.values()),
                    "association": {"location_id": selection.location_id, "checked": True,
                                    "note": selection.association_note, "operator": request.operator},
                }
                events.append(published)
                grouped.setdefault(selection.location_id, []).append(published)
            locations = []
            for location_id in sorted(grouped):
                rows = grouped[location_id]
                feature = context.feature(location_id)
                flat = [row["fields"] | {"event_id": row["event_id"], "verificat": True,
                                         "data_mode": self.mode} for row in rows]
                raw_details = context.score(feature, flat) if len(rows) >= 2 else None
                details = {key: raw_details[key] for key in (
                    "scor", "componente_scor", "explicatie", "date_lipsa", "pe_ore", "event_ids",
                )} if raw_details is not None else None
                properties = feature["properties"]
                unknowns = [key for key in ("semafor", "benzi", "iluminat", "tip_strada", "scoala_150m", "statie_100m")
                            if properties.get(key) is None]
                locations.append({"location_id": location_id, "feature": feature,
                                  "event_ids": [row["event_id"] for row in rows], "event_count": len(rows),
                                  "source_article_count": len({a["article_id"] for row in rows for a in row["source_articles"]}),
                                  "score": details["scor"] if details else None, "rank": None,
                                  "sufficient_for_score": details is not None, "score_details": details,
                                  "association_status": "operator_checked",
                                  "unknowns": unknowns})
            locations.sort(key=lambda row: (row["score"] is None, -(row["score"] or 0), row["location_id"]))
            ranked = 0
            for location in locations:
                if location["sufficient_for_score"]:
                    ranked += 1
                    location["rank"] = ranked
            warnings = ["Date sintetice pentru demonstrație; nu reprezintă accidente observate." if self.mode == "synthetic"
                        else "Eșantion selectiv de presă; nu este un inventar complet al accidentelor.",
                        "Scorul prioritizează locațiile în acest eșantion; nu este o probabilitate validată de accident.",
                        "Lipsa unui tag OSM nu dovedește absența infrastructurii."]
            scorer = scorer_provenance()
            return {"data_mode": self.mode, "period": {"start": request.period_start, "end": request.period_end},
                    "eligible_event_count": len(events), "excluded_event_count": len(request.selections) - len(events),
                    "diagnostics": diagnostics, "events": events, "locations": locations, "warnings": warnings,
                    "provenance": {"review_digest": _digest(document.model_dump()), "context": context.metadata,
                                   "formula_sha256": scorer["source_sha256"], "scorer": scorer},
                    "source_conflicts_checked": True}
        except PublicationContextError as error:
            raise PublicationError(error.status, error.code, error.message) from error
        except (OSError, KeyError, ValueError, TypeError) as error:
            raise PublicationError(503, "publication_input_unavailable", "Datele sau contextul nu permit o publicație verificabilă.") from error

    def preview(self, request):
        with _LOCK, _REVIEW_LOCK:
            self._index()  # Fail closed if an existing registry is corrupt.
            return self._build(request) | {"publication_status": "preview", "persisted": False}

    def _write(self, path, payload, *, immutable=False):
        temporary = None
        try:
            raw = _serialized(payload) + b"\n"
            if len(raw) > _MAX_BYTES:
                raise ValueError("publication exceeds file size limit")
            self._safe_directory()
            self.mode_directory.mkdir(parents=True, exist_ok=True)
            if immutable:
                with path.open("xb") as stream:
                    stream.write(raw)
                    stream.flush()
                    os.fsync(stream.fileno())
                return
            with tempfile.NamedTemporaryFile(mode="wb", dir=self.mode_directory, prefix="publication-", suffix=".tmp", delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        except (OSError, ValueError, UnicodeError) as error:
            raise _unavailable() from error
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass

    def publish(self, request):
        with _LOCK, _REVIEW_LOCK:
            if request.data_mode != self.mode:
                raise PublicationError(422, "invalid_data_mode", "Modul cererii diferă de modul publicației.")
            index, request_hash = self._index(), _digest(request.model_dump())
            existing = index["requests"].get(request.request_id)
            if existing:
                if existing["request_hash"] != request_hash:
                    raise PublicationError(409, "request_id_conflict", "request_id a fost folosit pentru altă cerere de publicare.")
                return self._snapshot(index, existing["snapshot_id"]), True
            preview = self._build(request)
            if preview["excluded_event_count"]:
                raise PublicationError(422, "ineligible_publication", "Selecția conține evenimente neeligibile; publicația nu a fost creată.", preview["diagnostics"])
            identifier = "pub_" + uuid4().hex
            snapshot = preview | {"schema_version": "publication-1", "snapshot_id": identifier,
                                  "publication_status": "published", "published_at": datetime.now(timezone.utc).isoformat(),
                                  "operator": request.operator, "note": request.note, "request_id": request.request_id,
                                  "request_hash": request_hash, "request": request.model_dump()}
            snapshot["events"] = [event | {"publication_status": "published"} for event in snapshot["events"]]
            snapshot["content_sha256"] = _digest(snapshot)
            self._write(self.mode_directory / f"{identifier}.json", snapshot, immutable=True)
            updated = deepcopy(index)
            updated["latest_snapshot_id"] = identifier
            updated["requests"][request.request_id] = {"request_hash": request_hash, "snapshot_id": identifier}
            updated["snapshots"][identifier] = {"content_sha256": snapshot["content_sha256"], "published_at": snapshot["published_at"],
                                               "event_count": len(snapshot["events"]), "location_count": len(snapshot["locations"])}
            self._write(self.index_path, updated)
            return snapshot, False
