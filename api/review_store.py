"""Atomic JSON review store for one local server process, never a public snapshot."""

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
from uuid import uuid4

from pydantic import ValidationError

from ai.engine import digest as extraction_digest
from api.review_models import CandidateFields, CandidateRecord, CorrectionRequest, HistoryEntry, ImportRecord, ReviewedEvent, StoreDocument


_LOCK = threading.RLock()  # Shared by factory instances pointing at the same file.
_REPOSITORY = Path(__file__).resolve().parents[1]


class ReviewError(Exception):
    def __init__(self, status, code, message):
        self.status, self.code, self.message = status, code, message
        super().__init__(message)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _id(prefix):
    return prefix + uuid4().hex


def _hash(request):
    raw = json.dumps(request.model_dump(), sort_keys=True, ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _require(condition):
    if not condition:
        raise ValueError("invalid extraction contract")


def validate_extraction(article, result, mode):
    """Validate the seam, exact evidence and unapproved state before any write."""
    try:
        json.dumps(result, ensure_ascii=False, allow_nan=False).encode("utf-8")
        _require(result["schema_version"] == "2.0" and result["data_mode"] == mode)
        _require(result["review_status"] == "pending" and result["errors"] == [])
        _require(result["processing_mode"] in ("rules", "live", "cache"))
        _require(isinstance(result["candidates"], list))
        _require(isinstance(result["duplicate_review_queue"], list))
        _require(len(result["articles"]) == 1)
        row = result["articles"][0]
        _require(row["article_id"] == article["article_id"] and row["review_status"] == "pending")
        _require(row["content_hash"] == extraction_digest(article["text"]))
        for candidate in result["candidates"]:
            _require(all(key in candidate for key in ("data_eveniment", "ora", "loc_text", "participanti", "cauza_raportata", "gravitate", "noapte", "lat", "lon", "precizie_loc", "in_iasi")))
            _require(isinstance(candidate["event_id"], str) and candidate["event_id"])
            _require(candidate["article_ids"] == [article["article_id"]])
            _require(candidate["urls"] == [article["url"]] and candidate["data_mode"] == mode)
            _require(candidate["verificat"] is False and candidate["review_status"] == "pending")
            _require(all(candidate.get(key) is None for key in ("lat", "lon", "in_iasi", "precizie_loc", "location_evidence")))
            fields = CandidateFields.model_validate({k: candidate[k] for k in CandidateFields.model_fields if k in candidate})
            evidence, references = candidate["dovezi"], candidate["evidence_refs"]
            _require(isinstance(evidence, dict) and isinstance(references, dict))
            for field, refs in references.items():
                _require(isinstance(field, str) and isinstance(refs, list) and refs)
                for ref in refs:
                    _require(ref["article_id"] == article["article_id"])
                    start, end, quote = ref["start"], ref["end"], ref["quote"]
                    _require(type(start) is int and type(end) is int and isinstance(quote, str))
                    _require(0 <= start < end <= len(article["text"]) and article["text"][start:end] == quote)
            for field, quote in evidence.items():
                _require(isinstance(quote, str) and any(ref["quote"] == quote for ref in references[field]))
            for field in ("data_eveniment", "ora", "loc_text", "participanti", "cauza_raportata", "gravitate", "noapte"):
                value = getattr(fields, field)
                if value is not None and value != [] and value != "necunoscut":
                    _require(field in evidence)
            _require(candidate["extraction_runs"] and all(
                run["content_hash"] == row["content_hash"] and run["model"] and run["prompt_version"]
                for run in candidate["extraction_runs"]
            ))
    except (KeyError, TypeError, ValueError, UnicodeError) as error:
        raise ReviewError(502, "invalid_extraction", "Rezultatul extractorului nu respectă contractul sau dovezile sursei.") from error


class ReviewStore:
    def __init__(self, directory, mode):
        self.directory, self.mode = Path(directory).resolve(), mode
        if any(self.directory.is_relative_to(_REPOSITORY / name) for name in ("false_data", "ai", "context", "risk", "coordonate", ".git")):
            raise ReviewError(503, "protected_review_directory", "Alege un director de lucru separat de sursele și fixture-urile comune.")
        self.path = self.directory / f"{mode}.json"

    def _read(self):
        try:
            if not self.path.exists():
                return StoreDocument(data_mode=self.mode)
            raw = json.loads(self.path.read_text(encoding="utf-8"), object_pairs_hook=_unique_keys)
            json.dumps(raw, allow_nan=False, ensure_ascii=False).encode("utf-8")
            document = StoreDocument.model_validate(raw)
            if document.data_mode != self.mode:
                raise ValueError("mixed data modes")
            request_ids, article_ids = set(), set()
            for key, record in document.imports.items():
                if key != record.import_id or record.data_mode != self.mode or record.request_id in request_ids or record.article.article_id in article_ids:
                    raise ValueError("invalid import identity")
                request_ids.add(record.request_id)
                article_ids.add(record.article.article_id)
                for candidate_id in record.candidate_ids:
                    if document.candidates[candidate_id].import_id != key:
                        raise ValueError("broken import reference")
            for key, record in document.candidates.items():
                imported = document.imports[record.import_id]
                if key != record.candidate_id or record.data_mode != self.mode or record.article_id != imported.article.article_id or key not in imported.candidate_ids:
                    raise ValueError("invalid candidate identity")
                if not record.history or record.version != len(record.history) or record.history[-1].version != record.version:
                    raise ValueError("invalid review history")
                approved = record.review_status in ("approved", "linked")
                if record.verificat != approved or bool(record.canonical_event_id) != approved:
                    raise ValueError("invalid approval state")
                if approved and key not in document.events[record.canonical_event_id].candidate_ids:
                    raise ValueError("broken canonical event")
            for key, record in document.events.items():
                if key != record.event_id or record.data_mode != self.mode or not record.candidate_ids or len(record.candidate_ids) != len(set(record.candidate_ids)):
                    raise ValueError("invalid event identity")
                if record.version != len(record.history):
                    raise ValueError("invalid event version")
                if any(document.candidates[c].canonical_event_id != key for c in record.candidate_ids):
                    raise ValueError("broken event reference")
            return document
        except (OSError, ValueError, KeyError, TypeError, UnicodeError) as error:
            raise ReviewError(503, "review_store_unavailable", "Stocarea de review nu poate fi citită sau este invalidă; nu a fost înlocuită.") from error

    def _write(self, document):
        temporary = None
        try:
            serialized = json.dumps(document.model_dump(), ensure_ascii=False, allow_nan=False, indent=2)
            self.directory.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.directory, prefix="review-", suffix=".tmp", delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(serialized + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        except (OSError, ValueError, UnicodeError) as error:
            raise ReviewError(503, "review_store_unavailable", "Modificarea nu a putut fi salvată; versiunea anterioară a fost păstrată.") from error
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass  # A cleanup failure must not hide the transaction result.

    def find_import(self, request):
        with _LOCK:
            for record in self._read().imports.values():
                if record.request_id == request.request_id:
                    if record.request_hash != _hash(request):
                        raise ReviewError(409, "request_id_conflict", "request_id a fost deja folosit pentru altă cerere.")
                    return record.model_dump()
                if record.article.article_id == request.article.article_id:
                    raise ReviewError(409, "article_already_imported", "Articolul există deja; reutilizează cererea originală sau identifică explicit o nouă versiune a sursei.")
            return None

    def save_import(self, request, extraction):
        with _LOCK:
            existing = self.find_import(request)
            if existing is not None:
                return existing, True
            article = request.article.model_dump()
            validate_extraction(article, extraction, self.mode)
            document, import_id, now = self._read(), _id("imp_"), _now()
            candidate_ids = []
            for raw in extraction["candidates"]:
                candidate_id = _id("cnd_")
                candidate_ids.append(candidate_id)
                document.candidates[candidate_id] = CandidateRecord(
                    candidate_id=candidate_id, import_id=import_id, article_id=article["article_id"], data_mode=self.mode,
                    fields=CandidateFields.model_validate({k: raw[k] for k in CandidateFields.model_fields if k in raw}),
                    original_extraction=deepcopy(raw),
                    history=[HistoryEntry(version=1, action="imported", operator=request.operator, at=now, note="Candidat importat; necesită verificare.")],
                )
            record = ImportRecord(
                import_id=import_id, request_id=request.request_id, request_hash=_hash(request), data_mode=self.mode,
                operator=request.operator, created_at=now, article=request.article,
                extraction=deepcopy(extraction), candidate_ids=candidate_ids,
            )
            document.imports[import_id] = record
            self._write(document)
            return record.model_dump(), False

    def get_import(self, import_id):
        with _LOCK:
            record = self._read().imports.get(import_id)
            if record is None:
                raise ReviewError(404, "import_not_found", "Import inexistent în modul de date ales.")
            return record.model_dump()

    def list_candidates(self, status=None):
        with _LOCK:
            return [c.model_dump() for c in self._read().candidates.values() if status is None or c.review_status == status]

    def get_candidate(self, candidate_id):
        with _LOCK:
            document = self._read()
            record = self._candidate(document, candidate_id)
            return record.model_dump() | {"article": document.imports[record.import_id].article.model_dump()}

    @staticmethod
    def _candidate(document, candidate_id, expected_version=None):
        record = document.candidates.get(candidate_id)
        if record is None:
            raise ReviewError(404, "candidate_not_found", "Candidat inexistent în modul de date ales.")
        if expected_version is not None:
            if record.version != expected_version:
                raise ReviewError(409, "version_conflict", "Candidatul a fost modificat; recitește versiunea curentă.")
            if record.review_status != "pending":
                raise ReviewError(409, "review_finalized", "Candidatul are deja o decizie; nu poate fi suprascris prin acest flux.")
        return record

    def correct(self, candidate_id, request, *, geocoding=None):
        with _LOCK:
            document = self._read()
            record = self._candidate(document, candidate_id, request.expected_version)
            if not set(request.changes) <= CandidateFields.model_fields.keys():
                raise ReviewError(422, "invalid_correction", "Corectează doar câmpurile editabile; proveniența și identitatea sunt păstrate.")
            before = record.fields.model_dump()
            base = dict(before)
            if "loc_text" in request.changes and request.changes["loc_text"] != before["loc_text"]:
                # A pin/evidence for the previous text is no longer applicable.
                # An operator may explicitly supply a coherent new location in this patch.
                base.update(lat=None, lon=None, precizie_loc=None, in_iasi=None, location_evidence=None)
            try:
                corrected = CandidateFields.model_validate(base | request.changes)
            except ValidationError as error:
                raise ReviewError(422, "invalid_correction", "Câmpuri invalide sau localizare incoerentă.") from error
            changes = {key: {"before": value, "after": getattr(corrected, key)} for key, value in before.items() if value != getattr(corrected, key)}
            if geocoding is not None:
                changes["geocoding"] = {"before": None, "after": deepcopy(geocoding)}
            if not changes:
                raise ReviewError(422, "empty_correction", "Cererea nu schimbă niciun câmp.")
            record.fields, record.version = corrected, record.version + 1
            record.history.append(HistoryEntry(version=record.version, action="corrected", operator=request.operator, at=_now(), note=request.reason, changes=changes))
            self._write(document)
            return record.model_dump()

    def _geocoding_proposal(self, record, service):
        proposal = {
            "schema_version": "geocoding-proposal-1", "candidate_id": record.candidate_id,
            "data_mode": self.mode, "expected_version": record.version,
            "loc_text": record.fields.loc_text,
            "current_location": {key: getattr(record.fields, key) for key in ("lat", "lon", "precizie_loc", "in_iasi", "location_evidence")},
        } | service.suggest(record.fields.loc_text, self.mode)
        raw = json.dumps(proposal, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        proposal["suggestion_id"] = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return proposal

    def preview_geocoding(self, candidate_id, request, service):
        with _LOCK:
            record = self._candidate(self._read(), candidate_id, request.expected_version)
            return self._geocoding_proposal(record, service)

    def apply_geocoding(self, candidate_id, request, service):
        with _LOCK:
            record = self._candidate(self._read(), candidate_id, request.expected_version)
            # Recompute from server-owned inputs; never trust coordinates or a report
            # supplied by the client. Any changed input invalidates the preview token.
            proposal = self._geocoding_proposal(record, service)
            if proposal["suggestion_id"] != request.suggestion_id:
                raise ReviewError(409, "geocoding_proposal_changed", "Sugestia sau datele de referință s-au schimbat; solicită un preview nou.")
            changes = dict(proposal["proposed_changes"])
            # The resolver supplies evidence, not an operator's verification.
            # The complete note/report remain in history; this is a compact reference.
            report = proposal["report"]
            references = ", ".join(report.get("referinte_osm", [])[:8]) or "fără referință precisă"
            changes["location_evidence"] = (
                f"Verificare declarată de {request.operator}: {request.reason[:2500]} · "
                f"Metodă: {str(report.get('metoda', 'necunoscut'))[:160]} · OSM: {references}"
            )
            correction = CorrectionRequest(
                data_mode=self.mode, expected_version=request.expected_version,
                operator=request.operator, reason=request.reason, changes=changes,
            )
            archived = proposal | {"location_checked": True, "applied_changes": changes}
            return self.correct(candidate_id, correction, geocoding=archived)

    def review(self, candidate_id, request):
        with _LOCK:
            document = self._read()
            candidate = self._candidate(document, candidate_id, request.expected_version)
            fields = candidate.fields
            if request.action != "reject" and (fields.lat is not None or fields.in_iasi is not None):
                if not request.location_checked or (fields.lat is not None and not fields.location_evidence):
                    raise ReviewError(422, "location_check_required", "Localizarea cunoscută necesită verificare explicită; un pin necesită și location_evidence.")
            event = None
            if request.action == "link":
                event = document.events.get(request.canonical_event_id)
                if event is None:
                    raise ReviewError(404, "event_not_found", "Eveniment canonic inexistent în modul de date ales.")
                if event.version != request.expected_event_version:
                    raise ReviewError(409, "event_version_conflict", "Evenimentul a fost modificat; recitește versiunea curentă.")
            candidate.version += 1
            candidate.review_status = {"approve": "approved", "reject": "rejected", "link": "linked"}[request.action]
            candidate.verificat = request.action != "reject"
            now = _now()
            decision = HistoryEntry(
                version=candidate.version, action=candidate.review_status, operator=request.operator, at=now, note=request.note,
                changes={"source_checked": request.source_checked, "duplicate_checked": request.duplicate_checked, "location_checked": request.location_checked},
            )
            candidate.history.append(decision)
            if candidate.verificat:
                if event is None:
                    event = ReviewedEvent(
                        event_id=_id("evt_"), data_mode=self.mode, fields=fields.model_copy(deep=True),
                        candidate_ids=[], article_ids=[], urls=[], source_claims=[], history=[],
                    )
                    document.events[event.event_id] = event
                candidate.canonical_event_id = event.event_id
                imported = document.imports[candidate.import_id]
                event.candidate_ids.append(candidate_id)
                event.article_ids = list(dict.fromkeys(event.article_ids + [candidate.article_id]))
                event.urls = list(dict.fromkeys(event.urls + [imported.article.url]))
                # Linking attaches source claims; it never silently replaces canonical facts.
                event.source_claims.append(candidate.model_dump())
                event.version = len(event.history) + 1
                event.history.append(decision.model_copy(update={"version": event.version}, deep=True))
            self._write(document)
            return {"candidate": candidate.model_dump(), "event": event.model_dump() if event else None}

    def list_events(self):
        with _LOCK:
            return [event.model_dump() for event in self._read().events.values()]
