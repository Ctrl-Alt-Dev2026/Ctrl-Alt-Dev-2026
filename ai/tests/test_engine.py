import copy
import io
import json
import socket
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from ai.engine import Ollama, deduplicate, empty_result, event_record, ground, load_articles, norm, parse_date, rules, schema, validate_shape

ROOT=Path(__file__).resolve().parents[1]
TASK_TMP=ROOT/"work"/"safety_tmp"
TASK_TMP.mkdir(parents=True,exist_ok=True)

class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.article=dict(article_id="unit-1",sursa="SINTETIC",url="https://example.invalid/unit-1",titlu="Unit safety fixture",publicat_la="2025-01-25",colectat_la="2026-10-17",text="Un accident rutier a implicat un pieton și un autoturism. Evenimentul s-a produs la data de 2025-01-24. Ora indicată în relatare este 08:15. Locul indicat este pe Bulevardul Carol I. Pietonul a fost rănit grav.")

    def test_missing_event_date_does_not_use_publication(self):
        a=copy.deepcopy(self.article)
        a["text"]=a["text"].replace("Evenimentul s-a produs la data de 2025-01-24.","Data evenimentului nu este precizată.")
        self.assertIsNone(rules(a)["data_eveniment"])
        self.assertIsNotNone(a["publicat_la"])

    def test_invalid_calendar_date(self):
        self.assertIsNone(parse_date("2026-02-30"))

    def test_no_coordinates_or_automatic_approval(self):
        e=event_record(self.article,rules(self.article))
        for key in ("lat","lon","in_iasi","precizie_loc"):
            self.assertIsNone(e[key])
        self.assertIs(e["verificat"],False)
        self.assertEqual(e["review_status"],"pending")

    def test_evidence_offsets_match_source(self):
        e=event_record(self.article,rules(self.article))
        for refs in e["evidence_refs"].values():
            for ref in refs:
                self.assertEqual(self.article["text"][ref["start"]:ref["end"]],ref["quote"])

    def test_invalid_evidence_drops_value(self):
        obj=dict(is_event=True,evidence_ids={k:999 for k in schema("evidence")["properties"]["evidence_ids"]["required"]})
        r=ground(self.article,obj,"evidence")
        self.assertIsNone(r["is_event"])
        self.assertIsNone(r["loc_text"])
        self.assertIn("event_has_no_evidence",r["issues"])

    def test_street_abbreviations_and_diacritics(self):
        self.assertEqual(norm("Bd. Independenței"),norm("B-dul Independentei"))
        self.assertEqual(norm("Șos. Păcurari"),norm("Șoseaua Pacurari"))

    def test_relative_dates_use_explicit_publication_anchor(self):
        self.assertEqual(parse_date("aseară","2025-03-13"),"2025-03-12")
        self.assertEqual(parse_date("miercuri seara","2025-11-21"),"2025-11-19")
        self.assertIsNone(parse_date("data nu este precizată","2025-11-21"))

    def test_abbreviation_does_not_truncate_location(self):
        from ai.engine import parse_location,sentences
        text="Locul indicat este pe Bd. Independenței. Ora indicată este 11:25."
        self.assertEqual(parse_location(sentences(text)[0]),"pe Bd. Independenței")

    def test_missing_time_is_review_not_auto_merge(self):
        a=event_record(self.article,rules(self.article))
        b=copy.deepcopy(a)
        b["article_ids"]=["another-source"]
        a["ora"]=b["ora"]=None
        merged,queue=deduplicate([a,b])
        self.assertEqual(len(merged),2)
        self.assertEqual(len(queue),1)

    def test_conflicting_severity_is_review_not_auto_merge(self):
        a=event_record(self.article,rules(self.article))
        b=copy.deepcopy(a)
        b["article_ids"]=["update-source"]
        b["gravitate"]="deces"
        merged,queue=deduplicate([a,b])
        self.assertEqual(len(merged),2)
        self.assertEqual(len(queue),1)

    def test_mixed_modes_rejected(self):
        b=copy.deepcopy(self.article)
        b.update(article_id="observed-1",sursa="A real publisher")
        with tempfile.TemporaryDirectory(dir=TASK_TMP) as tmp:
            p=Path(tmp)/"articles.json"
            p.write_text(json.dumps([self.article,b]),encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"cannot mix"):
                load_articles(p)

    def test_schema_rejects_boolean_sentence_id(self):
        obj=dict(is_event=True,evidence_ids={k:None for k in schema("evidence")["properties"]["evidence_ids"]["required"]})
        obj["evidence_ids"]["event"]=True
        with self.assertRaises(ValueError):
            validate_shape(obj,schema("evidence"))

    def test_schema_rejects_nonexistent_sentence_id(self):
        obj=dict(is_event=True,evidence_ids={k:None for k in schema("evidence")["properties"]["evidence_ids"]["required"]})
        obj["evidence_ids"]["event"]=8
        with self.assertRaises(ValueError):
            validate_shape(obj,schema("evidence",2))

    def test_later_pedestrian_mention_does_not_erase_car(self):
        a=copy.deepcopy(self.article)
        a["text"]+=" Pietonul a suferit răni ușoare."
        self.assertEqual(set(rules(a)["participanti"]),{"pieton","autoturism"})

    def test_invalid_json_retries_then_succeeds_and_cache_replays(self):
        obj=dict(is_event=False,evidence_ids={k:None for k in schema("evidence")["properties"]["evidence_ids"]["required"]})
        responses=[io.BytesIO(json.dumps({"response":"invalid"}).encode()),io.BytesIO(json.dumps({"response":json.dumps(obj),"done_reason":"stop"}).encode())]
        with tempfile.TemporaryDirectory(dir=TASK_TMP) as tmp,patch("ai.engine.urllib.request.urlopen",side_effect=responses) as call,patch("ai.engine.time.sleep"):
            c=Ollama(cache=tmp)
            _,trace=c.extract(self.article,"evidence")
            self.assertEqual(trace["attempts"],2)
            _,trace=c.extract(self.article,"evidence")
            self.assertTrue(trace["cache_hit"])
            self.assertEqual(call.call_count,2)

    def test_timeout_does_not_cache_bad_result(self):
        with tempfile.TemporaryDirectory(dir=TASK_TMP) as tmp,patch("ai.engine.urllib.request.urlopen",side_effect=socket.timeout("test")),patch("ai.engine.time.sleep"):
            with self.assertRaises(RuntimeError):
                Ollama(cache=tmp).extract(self.article,"evidence")
            self.assertEqual(list(Path(tmp).glob("*.json")),[])

    def test_hybrid_provider_failure_keeps_pending_rules_candidate(self):
        from ai.engine import run
        from unittest.mock import Mock
        client=Mock()
        client.extract.side_effect=RuntimeError("provider offline")
        result=run([self.article],"hybrid",client)
        self.assertTrue(result["rows"][0]["trace"]["failed"])
        self.assertEqual(len(result["accidents"]),1)
        self.assertEqual(result["accidents"][0]["review_status"],"pending")

if __name__=="__main__":
    unittest.main()
