# Fișier pentru extracția AI a colegului

Trimite articole_v2.json. Conține 94 de articole reale din scraping/articole_extrase_accident_raw.csv.

Format: listă JSON UTF-8, fiecare obiect având exact article_id, sursa, url, titlu, text, publicat_la, colectat_la. Este acceptat de ai.engine.load_articles și ai.service.validate_article. Colectat_la este gol deoarece momentul colectării nu este cunoscut; nu este inventat. Publicat_la este data publicării, nu data accidentului.

Textul provine din HTML-ul paginii fiecărui articol, nu doar din listări, href, RSS sau descrieri meta. Toate cele 94 de rânduri sursă sunt marcate metoda_extragere=html. Pentru 37 de articole s-a eliminat exclusiv eticheta finală de interfață „Lasă un răspuns Anulează răspunsul”. Restul textului este păstrat. CSV-ul original nu a fost modificat.

Nu se garantează că fiecare body este complet sau lipsit de orice alt element de interfață. Nu s-a făcut o verificare vizuală pagină cu pagină. Articolele sunt candidați de presă nevalidați; pot include controale, accidente fără pietoni, evenimente din alte localități și relatări despre accidente vechi.

Acesta este un export de texte, fără rulare sau rezultate AI. Nu sunt necesare cache-ul HTML sau baza SQLite pentru citirea lui. Integrarea cu modulul de extracție și selecția după criteriile proiectului vor fi realizate separat de utilizator.

Regenerarea acestui fișier, fără accesarea publicațiilor:

    python -m scraping.curata_si_exporta_articole --intrare scraping/articole_extrase_accident_raw.csv --director scraping/predare_ai
