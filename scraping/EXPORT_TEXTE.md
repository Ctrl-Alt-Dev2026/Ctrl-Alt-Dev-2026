# Curățarea și exportul textelor

Comanda pentru setul fix de demo:

    python -m scraping.curata_si_exporta_articole --intrare scraping/articole_extrase_accident_raw.csv --director scraping/predare_ai --csv-curatat scraping/articole_extrase_accident_clean.csv

Comanda pentru cele mai recente rezultate ale scraperului:

    python -m scraping.curata_si_exporta_articole --intrare scraping/data/candidati.csv --director scraping/data/predare

Nu se importă și nu se execută ai/. Nu există parametri pentru modele, pipeline-uri sau apeluri de inferență.

Funcția curata_text_articol() elimină exclusiv eticheta terminală „Lasă un răspuns Anulează răspunsul”. Nu rescrie relatarea și nu filtrează relevanța. Originalul nu poate fi suprascris de opțiunea --csv-curatat.

CSV-ul curățat păstrează rândurile și toate coloanele originale. JSON-ul articole_v2.json este o listă UTF-8 cu exact șapte câmpuri per articol: article_id, sursa, url, titlu, text, publicat_la, colectat_la. Numai URL-urile identice sunt deduplicate în JSON. Publicat_la este data publicării, iar colectat_la rămâne gol când momentul colectării nu este cunoscut. Nu se inventează date.

Acest JSON este formatul de predare stabilit pentru integrarea ulterioară. Nu conține rezultate de inferență sau aprobări. Verificarea traversării regulamentare, poziției pe trecere, rănirii/decesului pietonului, localității și datei accidentului se face ulterior de integrarea separată a utilizatorului.

Raport_pregatire.json arată rândurile citite, URL-urile unice, duplicatele, textele curățate, numărul exportat și locația CSV-ului curățat. Pentru setul fix: 94 rânduri și 94 URL-uri, cu 37 de texte curățate.

Pentru lucru pe aceste texte, colegii primesc CSV-ul clean sau JSON-ul. Pentru continuarea scrapingului primesc separat backupul SQLite; cache-ul HTML nu este necesar pentru textele deja parsate. scraping/data/ rămâne ignorat de Git.
