"""Release transactions keep human review and press-source grain intact."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from ai.service import ExtractionService
from api.publication_models import PublicationRequest
from api.publication_store import PublicationError, PublicationStore
from api.review_models import CorrectionRequest, ImportRequest, ReviewRequest
from api.review_store import ReviewStore
from risk.pipeline import score_location


REPOSITORY = Path(__file__).resolve().parents[1]
ARTICLE = json.loads((REPOSITORY / "false_data/articles.json").read_text(encoding="utf-8"))[0]


class ContextStub:
    metadata = {"data_mode": "synthetic", "fingerprint": "test-context-sha", "provenance": {"source": "SYNTHETIC"}}

    def feature(self, identifier):
        return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [27.58, 47.16]},
                "properties": {"id": identifier, "tip": "trecere", "nume": identifier,
                               "semafor": None, "benzi": None, "iluminat": None,
                               "tip_strada": None, "scoala_150m": None, "statie_100m": None}}

    def check_event(self, fields, identifier):
        if identifier not in ("loc-a", "loc-b", "loc-c"):
            return ["location_not_found"]
        if fields["lat"] is not None and abs(fields["lat"] - 47.16) > .01:
            return ["location_too_far"]
        return []

    def score(self, feature, events):
        return score_location(feature, events)


class PublicationStoreTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.review = ReviewStore(self.directory / "review", "synthetic")
        self.store = PublicationStore(self.directory / "publications", "synthetic", self.review, self.directory / "context")
        self.context_patch = patch("api.publication_context.load_context", return_value=ContextStub())
        self.context_patch.start()
        self.addCleanup(self.context_patch.stop)
        self.counter = 0

    def pending(self):
        self.counter += 1
        article = deepcopy(ARTICLE)
        article["article_id"], article["url"] = f"pub-test-{self.counter}", f"https://example.test/{self.counter}"
        request = ImportRequest.model_validate({"request_id": f"import-{self.counter}", "operator": "tester", "data_mode": "synthetic",
                                                "pipeline": "rules", "article": article})
        imported, _ = self.review.save_import(request, ExtractionService().extract(article, "rules"))
        return self.review.get_candidate(imported["candidate_ids"][0])

    def approved(self, *, changes=None, link=None):
        candidate = self.pending()
        fields = {"data_eveniment": "2026-10-01", "lat": 47.16, "lon": 27.58, "precizie_loc": "trecere",
                  "in_iasi": True, "location_evidence": "SYNTHETIC manually verified test location."}
        fields.update(changes or {})
        candidate = self.review.correct(candidate["candidate_id"], CorrectionRequest.model_validate({
            "data_mode": "synthetic", "expected_version": 1, "operator": "reviewer", "reason": "SYNTHETIC fixture reviewed.", "changes": fields}))
        body = {"data_mode": "synthetic", "expected_version": candidate["version"], "operator": "reviewer", "note": "Source, deduplication, and location checked.",
                "action": "link" if link else "approve", "source_checked": True, "duplicate_checked": True, "location_checked": True}
        if link:
            body.update(canonical_event_id=link["event_id"], expected_event_version=link["version"])
        return self.review.review(candidate["candidate_id"], ReviewRequest.model_validate(body))["event"]

    def body(self, events, *, request_id="release-1", locations=None):
        locations = locations or ["loc-a"] * len(events)
        return {"request_id": request_id, "data_mode": "synthetic", "operator": "publisher", "note": "Checked source disagreements; synthetic exercise.",
                "period_start": "2026-10-01", "period_end": "2026-10-17", "source_conflicts_checked": True,
                "selections": [{"event_id": event["event_id"], "expected_version": event["version"], "location_id": location,
                                "association_checked": True, "association_note": "Human checked this exact event-location association."}
                               for event, location in zip(events, locations)]}

    def request(self, events, **kwargs):
        return PublicationRequest.model_validate(self.body(events, **kwargs))

    def assert_error(self, code, callable, *args):
        with self.assertRaises(PublicationError) as caught:
            callable(*args)
        self.assertEqual(code, caught.exception.code)
        return caught.exception

    def test_contract_requires_explicit_boolean_checks_unique_events_and_iso_period(self):
        event = self.approved()
        body = self.body([event])
        invalid = [body | {"source_conflicts_checked": 1}, body | {"period_start": "20261001"},
                   body | {"period_start": "2026-10-18"}, body | {"request_id": "../escape"},
                   body | {"selections": body["selections"] * 2}, body | {"selections": []}]
        invalid.append(body | {"selections": [body["selections"][0] | {"association_checked": 1}]})
        invalid.append(body | {"selections": [body["selections"][0] | {"expected_version": True}]})
        for item in invalid:
            with self.subTest(item=item), self.assertRaises(ValidationError):
                PublicationRequest.model_validate(item)

    def test_preview_has_no_writes_and_published_snapshot_keeps_source_date_separate(self):
        event = self.approved()
        before = self.review.path.read_bytes()
        request = self.request([event])
        preview = self.store.preview(request)
        self.assertFalse(preview["persisted"])
        self.assertEqual(1, preview["eligible_event_count"])
        self.assertFalse(self.store.directory.exists())
        snapshot, reused = self.store.publish(request)
        self.assertFalse(reused)
        self.assertEqual(before, self.review.path.read_bytes())
        published = snapshot["events"][0]
        self.assertEqual("published", published["publication_status"])
        self.assertEqual("not_published", self.review.list_events()[0]["publication_status"])
        self.assertEqual(ARTICLE["publicat_la"], published["source_articles"][0]["publicat_la"])
        self.assertEqual("2026-10-01", published["fields"]["data_eveniment"])
        self.assertEqual(event["source_claims"], published["source_claims"])
        self.assertIsNone(snapshot["locations"][0]["score"])
        self.assertIsNone(snapshot["locations"][0]["rank"])
        self.assertEqual(snapshot, self.store.latest())
        self.assertEqual(snapshot, self.store.get(snapshot["snapshot_id"]))

    def test_linked_articles_count_once_and_score_uses_existing_formula(self):
        first = self.approved()
        first = self.approved(link=first)
        second = self.approved(changes={"gravitate": "deces"})
        snapshot, _ = self.store.publish(self.request([first, second]))
        self.assertEqual(2, snapshot["eligible_event_count"])
        location = snapshot["locations"][0]
        self.assertEqual(2, location["event_count"])
        self.assertEqual(3, location["source_article_count"])
        expected = score_location(location["feature"], [e["fields"] | {"event_id": e["event_id"]} for e in snapshot["events"]])
        keys = {"scor", "componente_scor", "explicatie", "date_lipsa", "pe_ore", "event_ids"}
        self.assertEqual({key: expected[key] for key in keys}, location["score_details"])
        self.assertEqual(keys, set(location["score_details"]))
        self.assertEqual("operator_checked", location["association_status"])
        self.assertNotIn("verificat", location["score_details"])
        self.assertNotIn("masuri", location["score_details"])
        self.assertEqual(snapshot["provenance"]["scorer"]["source_sha256"], snapshot["provenance"]["formula_sha256"])
        self.assertEqual(expected["scor"], location["score"])
        self.assertEqual(1, location["rank"])
        self.assertEqual(2, len(snapshot["events"][0]["source_articles"]))

    def test_idempotent_retry_ignores_changed_review_and_context_but_conflicting_request_fails(self):
        event = self.approved()
        request = self.request([event])
        first, _ = self.store.publish(request)
        self.approved(link=event)
        self.context_patch.stop()
        with patch("api.publication_context.load_context", side_effect=AssertionError("retry must use saved snapshot")):
            second, reused = self.store.publish(request)
        self.assertTrue(reused)
        self.assertEqual(first, second)
        changed = request.model_copy(update={"note": "Different review decision."})
        self.assertEqual(409, self.assert_error("request_id_conflict", self.store.publish, changed).status)
        self.assertEqual(1, len(self.store.list_snapshots()))

    def test_stale_and_unknown_events_fail_without_mutating_anything(self):
        event = self.approved()
        stale = self.request([event])
        self.approved(link=event)
        self.assertEqual(409, self.assert_error("event_version_conflict", self.store.publish, stale).status)
        body = self.body([event])
        body["selections"][0]["event_id"] = "cnd_pending_is_not_event"
        self.assertEqual(404, self.assert_error("event_not_found", self.store.preview, PublicationRequest.model_validate(body)).status)
        self.assertFalse(self.store.directory.exists())

    def test_eligibility_explains_unknown_date_period_and_geospatial_failures(self):
        variants = [({"data_eveniment": None}, "event_date_unknown"),
                    ({"data_eveniment": "2026-09-30"}, "outside_analysis_period"),
                    ({"lat": None, "lon": None, "precizie_loc": "vag"}, "coordinates_missing"),
                    ({"in_iasi": False}, "outside_iasi"),
                    ({"lat": 46.0}, "location_too_far")]
        for index, (changes, expected) in enumerate(variants):
            event = self.approved(changes=changes)
            request = self.request([event], request_id=f"excluded-{index}")
            preview = self.store.preview(request)
            self.assertEqual(0, preview["eligible_event_count"])
            self.assertIn(expected, preview["diagnostics"][0]["reasons"])
            error = self.assert_error("ineligible_publication", self.store.publish, request)
            self.assertEqual(422, error.status)
            self.assertIn(expected, error.issues[0]["reasons"])
        self.assertFalse(self.store.directory.exists())

    def test_unknown_location_is_an_exclusion_and_one_invalid_selection_blocks_whole_release(self):
        first, second = self.approved(), self.approved()
        request = self.request([first, second], locations=["loc-a", "unknown"])
        preview = self.store.preview(request)
        self.assertEqual((1, 1), (preview["eligible_event_count"], preview["excluded_event_count"]))
        self.assertIn("location_not_found", preview["diagnostics"][1]["reasons"])
        self.assert_error("ineligible_publication", self.store.publish, request)
        self.assertFalse(self.store.directory.exists())

    def test_stable_ranking_uses_location_id_for_score_ties_and_omits_singleton_rank(self):
        events = [self.approved(changes={"gravitate": "usor"}) for _ in range(5)]
        snapshot, _ = self.store.publish(self.request(events, locations=["loc-b", "loc-b", "loc-a", "loc-a", "loc-c"]))
        self.assertEqual([("loc-a", 1), ("loc-b", 2), ("loc-c", None)], [(l["location_id"], l["rank"]) for l in snapshot["locations"]])

    def test_concurrent_same_request_creates_one_release(self):
        request = self.request([self.approved()])
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(self.store.publish, [request, request]))
        self.assertEqual([False, True], sorted([item[1] for item in results]))
        self.assertEqual(results[0][0], results[1][0])
        self.assertEqual(1, len(self.store.list_snapshots()))

    def test_failed_atomic_index_commit_keeps_latest_and_orphan_unaddressable(self):
        event = self.approved()
        previous, _ = self.store.publish(self.request([event]))
        before = self.store.index_path.read_bytes()
        with patch("api.publication_store.os.replace", side_effect=OSError("simulated failure")):
            self.assert_error("publication_store_unavailable", self.store.publish, self.request([event], request_id="release-2"))
        self.assertEqual(before, self.store.index_path.read_bytes())
        self.assertEqual(previous, self.store.latest())
        orphans = [p.stem for p in self.store.mode_directory.glob("pub_*.json") if p.stem != previous["snapshot_id"]]
        self.assertEqual(1, len(orphans))
        self.assert_error("publication_not_found", self.store.get, orphans[0])
        self.assertEqual([], list(self.store.mode_directory.glob("*.tmp")))
        retried, reused = self.store.publish(self.request([event], request_id="release-2"))
        self.assertFalse(reused)
        self.assertEqual(retried, self.store.latest())

    def test_corrupt_index_duplicate_keys_nonfinite_and_snapshot_tampering_fail_closed(self):
        snapshot, _ = self.store.publish(self.request([self.approved()]))
        original = self.store.index_path.read_bytes()
        for raw in ('{"a":1,"a":2}', '{"a":NaN}', '[]', '[broken'):
            self.store.index_path.write_text(raw, encoding="utf-8")
            self.assert_error("publication_store_unavailable", self.store.latest)
            self.assertEqual(raw, self.store.index_path.read_text(encoding="utf-8"))
        self.store.index_path.write_bytes(original)
        snapshot_path = self.store.mode_directory / f"{snapshot['snapshot_id']}.json"
        altered = deepcopy(snapshot)
        altered["events"][0]["fields"]["gravitate"] = "deces"
        snapshot_path.write_text(json.dumps(altered), encoding="utf-8")
        self.assert_error("publication_store_unavailable", self.store.latest)
        self.assert_error("publication_store_unavailable", self.store.list_snapshots)

    def test_mode_and_protected_directory_isolation(self):
        snapshot, _ = self.store.publish(self.request([self.approved()]))
        observed = PublicationStore(self.store.directory, "observed", ReviewStore(self.review.directory, "observed"), self.directory / "context")
        self.assert_error("publication_not_found", observed.latest)
        self.assert_error("publication_not_found", observed.get, snapshot["snapshot_id"])
        for protected in ("false_data", "ai/benchmarks", "ai/patterns", "risk", "context", ".git"):
            self.assert_error("protected_publication_directory", PublicationStore,
                              REPOSITORY / protected / "must-not-exist", "synthetic", self.review, self.directory / "context")
        self.assert_error("publication_not_found", self.store.get, "../../secret")

    def test_publication_directory_cannot_overlap_configured_review_or_context(self):
        for target in (self.review.directory, self.review.directory / "published",
                       self.directory / "context", self.directory / "context" / "published", self.directory):
            self.assert_error("protected_publication_directory", PublicationStore,
                              target, "synthetic", self.review, self.directory / "context")
        self.assertFalse(self.review.directory.exists())
        self.assertFalse((self.directory / "context").exists())


if __name__ == "__main__":
    unittest.main()
