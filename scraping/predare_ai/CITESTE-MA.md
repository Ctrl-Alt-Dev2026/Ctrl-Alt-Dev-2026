# Fișier pentru extracția AI a colegului

Trimite articole_v2.json. Conține 94 de articole reale din scraping/articole_extrase_accident_raw.csv.

Format: listă JSON UTF-8, fiecare obiect având exact article_id, sursa, url, titlu, text, publicat_la, colectat_la. Este acceptat de ai.engine.load_articles și ai.service.validate_article. Colectat_la este gol deoarece momentul colectării nu este cunoscut; nu este inventat. Publicat_la este data publicării, nu data accidentului.

Textul provine din HTML-ul paginii fiecărui articol, nu doar din listări, href, RSS sau descrieri meta. Toate cele 94 de rânduri sursă sunt marcate metoda_extragere=html. Pentru 37 de articole s-a eliminat exclusiv eticheta finală de interfață „Lasă un răspuns Anulează răspunsul”. Restul textului este păstrat. CSV-ul original nu a fost modificat.

Nu se garantează că fiecare body este complet sau lipsit de orice alt element de interfață. Nu s-a făcut o verificare vizuală pagină cu pagină. Articolele sunt candidați de presă nevalidați; pot include controale, accidente fără pietoni, evenimente din alte localități și relatări despre accidente vechi.

Din rădăcina repository-ului, cu Ollama pornit și qwen2.5:1.5b instalat:

    python -m ai --articles scraping/predare_ai/articole_v2.json --pipelines direct --model qwen2.5:1.5b --base-url http://127.0.0.1:11434 --out ai/work/presa --cache ai/work/cache_presa

Test pe un articol: adaugă --limit 1. Nu este nevoie de cache-ul HTML al scraperului sau de bazele lui SQLite.

Modulul AI extrage informațiile despre eveniment din câmpul text; nu descarcă URL-ul. Rezultatele lui rămân candidați pentru review, fără aprobare sau coordonate. Poziția pietonului pe trecere și apartenența la municipiul Iași necesită verificare explicită suplimentară.

Regenerarea acestui fișier, fără Ollama și fără accesarea publicațiilor:

    python -m scraping.procesare_articole_ai --doar-pregatire --intrare scraping/articole_extrase_accident_raw.csv --director scraping/predare_ai
