"""Evaluate frozen predictions. This file alone reads the supplied answer key."""
import argparse
import itertools
import json
import statistics
from pathlib import Path
from .engine import FIELDS, atomic_json, norm, event_record

def eq(field, a, b):
    if field == "participanti":
        return set(a or []) == set(b or [])
    if field == "loc_text":
        return norm(a) == norm(b)
    return a == b

def known(field, value):
    return value is not None and value != [] and not (field == "gravitate" and value == "necunoscut")

def pairs(groups):
    return {tuple(sorted(p)) for e in groups for p in itertools.combinations(e["article_ids"], 2)}

def score(result, expected, articles, ids):
    expected = [e for e in expected if set(e["article_ids"]) <= ids]
    rows = {r["article_id"]: r for r in result["rows"] if r["article_id"] in ids}
    predictions = [e for e in result["accidents"] if set(e["article_ids"]) <= ids]
    positive_ids = {aid for e in expected for aid in e["article_ids"]}
    detection = dict(tp=0, tn=0, fp=0, fn=0, abstained=0)
    for aid in ids:
        value = rows.get(aid, {}).get("extracted", {}).get("is_event")
        if value is None:
            detection["abstained"] += 1
        if aid in positive_ids:
            detection["tp" if value is True else "fn"] += 1
        else:
            detection["fp" if value is True else "tn"] += 1
    detection["correct"] = sum(1 for aid in ids if rows.get(aid, {}).get("extracted", {}).get("is_event") is (aid in positive_ids))
    detection["total"] = len(ids)
    by_field = {f: dict(correct=0, total=len(expected), known_correct=0, known_expected=0, known_predicted=0, unknown_expected=0, unknown_correct=0) for f in FIELDS}
    errors = []
    for gold in expected:
        matches = [e for e in predictions if set(e["article_ids"]) & set(gold["article_ids"])]
        pred = max(matches, key=lambda e: (len(set(e["article_ids"]) & set(gold["article_ids"])), gold["article_ids"][0] in e["article_ids"])) if matches else None
        for field in FIELDS:
            value = pred[field] if pred else None
            correct = pred is not None and eq(field, gold[field], value)
            b = by_field[field]
            b["correct"] += int(correct)
            b["known_expected"] += int(known(field, gold[field]))
            b["known_predicted"] += int(pred is not None and known(field, value))
            b["known_correct"] += int(correct and known(field, gold[field]))
            if not known(field, gold[field]):
                b["unknown_expected"] += 1
                b["unknown_correct"] += int(correct)
            if not correct:
                errors.append(dict(event_id=gold["event_id"], article_ids=gold["article_ids"], field=field, expected=gold[field], predicted=value, candidate_ids=pred["article_ids"] if pred else []))
    auto_pairs, gold_pairs = pairs(predictions), pairs(expected)
    queued_pairs = {tuple(sorted(p)) for q in result["duplicate_review_queue"] if set(q["article_ids"]) <= ids for p in itertools.combinations(q["article_ids"], 2)}
    correct_pairs = len(auto_pairs & gold_pairs)
    latencies = [r["trace"]["duration_s"] for r in rows.values() if "duration_s" in r["trace"]]
    article_map = {a["article_id"]: a for a in articles}
    quotes = [ref for e in predictions for refs in e.get("evidence_refs", {}).values() for ref in refs]
    evidence_exact = sum(1 for q in quotes if article_map[q["article_id"]]["text"][q["start"]:q["end"]] == q["quote"])
    return dict(articles=len(ids), gold_events=len(expected), candidate_groups=len(predictions), detection=detection,
                fields_correct=sum(b["correct"] for b in by_field.values()), fields_total=len(expected)*len(FIELDS), by_field=by_field,
                known_correct=sum(b["known_correct"] for b in by_field.values()), known_expected=sum(b["known_expected"] for b in by_field.values()), known_predicted=sum(b["known_predicted"] for b in by_field.values()),
                duplicate_pairs=dict(correct=correct_pairs, predicted=len(auto_pairs), expected=len(gold_pairs), recall_including_review=len((auto_pairs|queued_pairs)&gold_pairs)),
                evidence_exact=evidence_exact, evidence_quotes=len(quotes),
                no_coordinates_or_approval=all(e[k] is None for e in predictions for k in ("lat","lon","precizie_loc","in_iasi")) and all(e["verificat"] is False for e in predictions),
                rows_with_issues=sum(bool(r["extracted"]["issues"]) for r in rows.values()),
                model_failed_rows=sum(bool(r["trace"].get("failed")) for r in rows.values()),
                original_inference_seconds=round(sum(latencies), 3), median_original_inference_seconds=round(statistics.median(latencies),3) if latencies else None,
                input_tokens=sum(r["trace"].get("prompt_eval_count",0) or 0 for r in rows.values()), output_tokens=sum(r["trace"].get("eval_count",0) or 0 for r in rows.values()),
                errors=errors)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--results", default="ai/work/results")
    p.add_argument("--articles", default="ai/benchmarks/source_articles.json")
    p.add_argument("--expected", default="ai/benchmarks/repository_annotations.json")
    args = p.parse_args()
    articles = json.loads(Path(args.articles).read_text(encoding="utf-8"))
    annotations = json.loads(Path(args.expected).read_text(encoding="utf-8"))
    expected = annotations["article_annotations"] if isinstance(annotations,dict) else annotations
    event_groups = annotations["event_groups"] if isinstance(annotations,dict) else annotations
    all_ids = {a["article_id"] for a in articles}
    results = {}
    for name in ("rules", "direct", "evidence", "agreement", "hybrid"):
        source = Path(args.results)/(name+".json")
        if not source.exists():
            continue
        result = json.loads(source.read_text(encoding="utf-8"))
        article_lookup={a["article_id"]:a for a in articles}
        by_article={**result,"accidents":[event_record(article_lookup[r["article_id"]],r["extracted"]) for r in result["rows"] if r["extracted"]["is_event"] is True]}
        s=score(by_article,expected,articles,all_ids)
        group_score=score(result,event_groups,articles,all_ids)
        s["duplicate_pairs"]=group_score["duplicate_pairs"]
        s["candidate_groups"]=len(result["accidents"])
        s["gold_unique_events"]=len(event_groups)
        s["evaluation_unit"]="source article; 7 fields each; separate duplicate identity scoring"
        results[name]=s
        print(f"{name}: fields {s['fields_correct']}/{s['fields_total']}; relevance {s['detection']['correct']}/{s['articles']}; duplicate pairs {s['duplicate_pairs']}")
    atomic_json(Path(args.results)/"metrics.json",results)

if __name__ == "__main__":
    main()
