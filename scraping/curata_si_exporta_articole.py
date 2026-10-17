"""Curăță textele din CSV și exportă CSV/JSON; fără rețea sau inferență AI."""
import argparse
import csv
import hashlib
import json
import sys
import time
from pathlib import Path



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



def scrie_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    replace_retry(temporary, path)


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--intrare", type=Path, default=Path("scraping/articole_extrase_accident_raw.csv"))
    parser.add_argument("--director", type=Path, default=Path("scraping/predare_ai"))
    parser.add_argument("--csv-curatat", type=Path,
                        help="implicit: <director>/articole_curatate.csv; originalul nu poate fi suprascris")
    args = parser.parse_args(argv)
    audit = {"sursa_csv": str(args.intrare)}
    try:
        articles = read_articles(args.intrare, audit=audit)
        csv_path = args.csv_curatat or args.director / "articole_curatate.csv"
        exporta_csv_curatat(args.intrare, csv_path)
    except (OSError, ValueError, csv.Error) as exc:
        parser.error(str(exc))
    args.director.mkdir(parents=True, exist_ok=True)
    audit.update(articole_exportate=len(articles), csv_curatat=str(csv_path))
    scrie_json(args.director / "articole_v2.json", articles)
    scrie_json(args.director / "raport_pregatire.json", audit)
    print(f"Pregătite {len(articles)} articole: {args.director.resolve()}")
    print(f"CSV curățat: {csv_path.resolve()}; texte curățate: {audit['texte_curatate']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
