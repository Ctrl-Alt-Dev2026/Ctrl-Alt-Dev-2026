"""Pregătește CSV-ul pentru AI și poate apela modulul existent ai.ExtractionService."""
import argparse
from collections import Counter
import csv
import hashlib
import json
import sys
import time
from pathlib import Path

from ai import ExtractionConfig, ExtractionService


def replace_retry(temporary, path):
    for attempt in range(8):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt == 7:
                raise
            time.sleep(0.15 * (attempt + 1))


def curata_text_articol(text):
    """Elimină doar eticheta de comentarii de la final; nu filtrează articole."""
    marker = "Lasă un răspuns Anulează răspunsul"
    if text.rstrip().endswith(marker):
        return text.rstrip()[:-len(marker)].rstrip()
    return text


def exporta_csv_curatat(intrare, iesire):
    """Păstrează toate coloanele și rândurile; curăță exclusiv câmpul text."""
    if intrare.resolve() == iesire.resolve():
        raise ValueError("CSV-ul curățat trebuie salvat separat de original")
    csv.field_size_limit(10_000_000)
    with intrare.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames
        if not fields or "text" not in fields:
            raise ValueError("CSV-ul trebuie să conțină coloana text")
        rows = list(reader)
    cleaned = 0
    for row in rows:
        original = row.get("text") or ""
        row["text"] = curata_text_articol(original)
        cleaned += row["text"] != original
    iesire.parent.mkdir(parents=True, exist_ok=True)
    temporary = iesire.with_suffix(iesire.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    replace_retry(temporary, iesire)
    return {"randuri_csv": len(rows), "texte_curatate": cleaned}


def read_articles(path, *, audit=None):
    csv.field_size_limit(10_000_000)
    articles = {}
    input_count, cleaned_count = 0, 0
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not {"url", "titlu", "text"} <= set(reader.fieldnames or []):
            raise ValueError("CSV-ul trebuie să conțină url, titlu și text")
        for row in reader:
            input_count += 1
            url, text = (row.get("url") or "").strip(), row.get("text") or ""
            if not url or not text.strip():
                raise ValueError("Rând cu URL sau text absent")
            original_text = text
            text = curata_text_articol(text)
            cleaned_count += text != original_text
            article_id = "press-" + hashlib.sha256(url.encode()).hexdigest()[:20]
            articles[article_id] = dict(
                article_id=article_id, sursa=row.get("sursa") or "PRESA",
                url=url, titlu=row.get("titlu") or "", text=text,
                publicat_la=row.get("data_publicarii") or "",
                # File timestamp is not the retrieval time. Leave unknown.
                colectat_la="")
    if audit is not None:
        audit.update(randuri_csv=input_count, urluri_unice=len(articles),
                     randuri_duplicate_url=input_count - len(articles),
                     texte_curatate=cleaned_count,
                     regula_cleanup="Elimină exclusiv eticheta finală: Lasă un răspuns Anulează răspunsul",
                     filtrare_relevanta=False)
    return list(articles.values())


def save(directory, articles, results):
    def write(name, value):
        path = directory / name
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        replace_retry(temporary, path)
    write("articole_v2.json", articles)
    write("extractii.json", results)
    rows = []
    candidates = []
    for article, result in zip(articles, results):
        extracted = result["articles"][0]["extracted"]
        state = "eroare" if result["errors"] else (
            "candidat" if extracted["is_event"] is True else
            "exclus" if extracted["is_event"] is False else "neclar")
        if state == "candidat" and (extracted["issues"] or "pieton" not in extracted["participanti"]):
            state = "neclar"
        rows.append(dict(url=article["url"], titlu=article["titlu"], stare=state,
                         mod=result["processing_mode"], data_eveniment=extracted["data_eveniment"],
                         loc_text=extracted["loc_text"], gravitate=extracted["gravitate"],
                         participanti=json.dumps(extracted["participanti"], ensure_ascii=False),
                         cauza_raportata=extracted["cauza_raportata"],
                         pe_trecere="", in_iasi="", verificat=False,
                         dovezi=json.dumps([c["dovezi"] for c in result["candidates"]], ensure_ascii=False),
                         probleme=json.dumps(extracted["issues"] + result["errors"], ensure_ascii=False),
                         text=article["text"]))
        candidates.extend(result["candidates"])
    write("candidati_v2.json", candidates)
    write("raport.json", {
        "articole_intrare": len(articles), "articole_procesate": len(results),
        "stari": dict(Counter(row["stare"] for row in rows)),
        "moduri": dict(Counter(row["mod"] for row in rows)),
        "criterii_neconfirmate_de_modul": ["pe_trecere", "in_iasi"],
        "verificat_uman": False,
    })
    fields = ["url", "titlu", "stare", "mod", "data_eveniment", "loc_text", "gravitate",
              "participanti", "cauza_raportata", "pe_trecere", "in_iasi", "verificat", "dovezi", "probleme", "text"]
    for name, selected in (("toate.csv", rows),
                           ("candidati_review.csv", [r for r in rows if r["stare"] == "candidat"]),
                           ("excluse_sau_neclare.csv", [r for r in rows if r["stare"] != "candidat"])):
        path = directory / name
        temporary = path.with_suffix(".csv.tmp")
        with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(selected)
        replace_retry(temporary, path)


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--intrare", type=Path, default=Path("scraping/articole_extrase_accident_raw.csv"))
    parser.add_argument("--director", type=Path, default=Path("scraping/data/ai_coleg"))
    parser.add_argument("--pipeline", choices=("rules", "direct", "evidence", "hybrid", "agreement"), default="direct")
    parser.add_argument("--model", default=ExtractionConfig.from_env().model)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--timeout", type=float, default=600)
    parser.add_argument("--doar-pregatire", action="store_true", help="exportă articole_v2.json fără Ollama")
    parser.add_argument("--csv-curatat", type=Path, help="exportă separat CSV-ul original cu numai coloana text curățată")
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit < 1:
        parser.error("--limit trebuie să fie pozitiv")
    audit = {"sursa_csv": str(args.intrare)}
    articles = read_articles(args.intrare, audit=audit)
    if args.csv_curatat:
        csv_report = exporta_csv_curatat(args.intrare, args.csv_curatat)
        print(f"CSV curățat: {args.csv_curatat}; {csv_report}", flush=True)
    if args.limit:
        articles = articles[:args.limit]
    args.director.mkdir(parents=True, exist_ok=True)
    audit.update(limita=args.limit, articole_exportate=len(articles))
    report = args.director / "raport_pregatire.json"
    temporary = report.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    replace_retry(temporary, report)
    if args.doar_pregatire:
        path = args.director / "articole_v2.json"
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(articles, ensure_ascii=False, indent=2), encoding="utf-8")
        replace_retry(temporary, path)
        print(f"Pregătite {len(articles)} articole pentru modulul colegului: {path.resolve()}")
        return 0
    service = ExtractionService(ExtractionConfig(model=args.model,
        cache_dir=args.director / "cache", timeout_s=args.timeout, retries=0))
    results = []
    save(args.director, articles, results)
    try:
        for index, article in enumerate(articles, 1):
            print(f"[{index}/{len(articles)}] {args.pipeline}: {article['titlu']}", flush=True)
            result = service.extract(article, pipeline=args.pipeline)
            results.append(result)
            save(args.director, articles, results)
            print(f"  {result['processing_mode']}: {len(result['candidates'])} candidați", flush=True)
            if result["errors"]:
                print("Oprit la eroare:", "; ".join(result["errors"]), flush=True)
                return 1
    except KeyboardInterrupt:
        print("Oprit; rezultatele terminate sunt salvate. Cache-ul modulului AI permite reluarea.")
        return 130
    print(f"Salvat: {args.director.resolve()}; {len(results)} articole procesate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
