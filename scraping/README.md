# Colectarea și exportul textelor din presă

Acest director se ocupă numai de colectare, curățare și export. Nu importă modulul ai/, nu apelează modele și nu decide dacă un pieton traversa regulamentar. Integrarea cu extracția AI și verificarea eligibilității se fac separat, după export.

## Ce fișiere rulezi

| Fișier | Rol |
|---|---|
| scraper_stiri.py | Citește listările Local BZI/Ziarul de Iași, selectează preliminar URL-uri, descarcă articole și extrage textul din HTML. |
| curata_si_exporta_articole.py | Citește un CSV existent, elimină eticheta de comentarii de la final și exportă CSV curățat + JSON pentru predare. Nu accesează internetul. |
| test_scraper_stiri.py, test_curata_si_exporta_articole.py | Teste offline, fără accesarea publicațiilor sau a vreunui model. |

Exportul se face exclusiv cu biblioteca standard Python; singurele dependențe externe din requirements.txt sunt pentru colectarea și parsarea paginilor.

## 1. Instalare și colectare

Din rădăcina proiectului, cu Python 3.10+:

```powershell
python -m pip install -r scraping/requirements.txt
python -m scraping.scraper_stiri --de-la 2026-01-01 --pana-la 2026-10-17 --pauza 15 --max-taskuri 200
```

--max-taskuri limitează taskurile succesive dintr-o rulare, nu concurența. Un task este o listare, un sitemap sau un articol; robots.txt poate necesita cereri suplimentare. Repetarea comenzii continuă din scraping/data/colectare.sqlite3. Un singur proces per director și domeniu. Ctrl+C păstrează progresul confirmat. --pana-la este inclusiv; dacă lipsește, se folosește ziua rulării.

Se filtrează preliminar după titlu, rezumat și URL; apoi se descarcă paginile articolelor selectate. Termenii includ accident, pieton, trecere, călcat, lovit, mortal, mort, rănit și variante. --exhaustiv permite și articolele fără acești termeni. Body-ul este extras din HTML-ul articolului; nu este doar o descriere din listare. Completitudinea nu este garantată pentru orice structură de pagină.

## 2. Curățare și export pentru coleg

Pentru cel mai recent CSV generat de scraper:

```powershell
python -m scraping.curata_si_exporta_articole --intrare scraping/data/candidati.csv --director scraping/data/predare
```

Comanda produce articole_curatate.csv, articole_v2.json și raport_pregatire.json. Este exclusiv locală și folosește numai biblioteca standard Python.

Pentru setul fix de demo deja inclus în repository:

```powershell
python -m scraping.curata_si_exporta_articole --intrare scraping/articole_extrase_accident_raw.csv --director scraping/predare_ai --csv-curatat scraping/articole_extrase_accident_clean.csv
```

Originalul raw rămâne păstrat. Pentru setul actual: 94 rânduri, 94 URL-uri unice, 37 de texte cu eticheta finală eliminată și 94 de articole în JSON. Curățarea nu elimină documente după relevanță. CSV-ul păstrează toate rândurile și coloanele; JSON-ul deduplică numai URL-urile identice. Raportul arată separat aceste numere.

Trimite colegului [predare_ai/articole_v2.json](predare_ai/articole_v2.json) sau CSV-ul clean. [Formatul exportului](EXPORT_TEXTE.md) conține detaliile. Integrarea ulterioară îi poate verifica pe pietonul care traversa regulamentar, impactul, rănirea/decesul, localitatea și data reală a accidentului; acestea nu sunt criterii validate de export.

## Ce se salvează în scraping/data/

- colectare.sqlite3: inventar, progres și textele deja parsate.
- cache/: răspunsurile HTML, pentru reparsare locală.
- inventar_urluri.csv: toate URL-urile descoperite, cu stări și indicii din listare.
- articole.jsonl: toate articolele procesate, inclusiv cele care nu trec filtrul de candidați.
- candidati.csv: articole cu indicii de pieton/traversare și accident/impact, publicate în interval sau cu data publicării necunoscută.
- raport.json: stări, taskuri rămase și erori.

Cele 946 de articole din backup sunt toate articolele procesate la acel moment. Cele 94 din CSV-ul fix de demo au trecut filtrul de cuvinte-cheie și de publicare. Nu sunt 94 de accidente confirmate; curățarea textului nu a produs această selecție. Câmpurile de clasificare sunt indicii prin reguli, nu verdict AI, confirmare a traversării regulamentare sau aprobare pentru hartă. Data publicării nu este data accidentului.

## Export fără cereri noi și reluare din backup

```powershell
python -m scraping.scraper_stiri --export-only --de-la 2026-01-01 --pana-la 2026-10-17
```

Aceasta reconstruiește exporturile din baza existentă, fără accesarea publicațiilor. Un alt interval schimbă exportul, nu șterge textele din SQLite.

Pentru restaurare, oprește scraperul și pune colectare.sqlite3 din ZIP în <proiect>/scraping/data/colectare.sqlite3. Salvează separat o eventuală bază locală înainte de înlocuire. Cu codul actualizat, colectarea continuă fără cache HTML: articolele done au deja textul în SQLite. Nu folosi --actualizeaza pentru simpla continuare; ar rearma și articolele descărcate. Baza și cache-ul rămân ignorate de Git; distribuie backupul separat. [Instrucțiuni de automatizare](AUTOMATIZARE.md).

## Opțiuni și limite

- --surse bzi sau --surse zdi: o singură publicație.
- --faza descoperire sau --faza articole: separă descoperirea de procesarea articolelor.
- --urluri fisier.txt: URL-uri absolute suplimentare, unul pe linie, numai din domeniile selectate.
- --sitemap: urmărește și sitemap-urile declarate de site, inclusiv alte secțiuni/perioade.
- --director cale: alt director de colectare.
- --reincearca: rearmează erorile/blocările, cu reverificarea robots.txt și păstrarea pauzei domeniului.
- --actualizeaza: golește cache-ul taskurilor terminate și le rearmează pentru o nouă descărcare.
- --noutati: verifică paginile recente, păstrând articolele deja descărcate.

Paginarea urmărește pagina imediat următoare și se oprește la o pagină cu toate cardurile datate înaintea începutului intervalului. Presupune arhive cronologice; pagini reordonate, articole neindexate sau termeni lipsă pot produce omisiuni. Nu se garantează acoperirea completă.

Pauza implicită este 5 secunde; crawl-delay o poate crește. HTTP 429 respectă Retry-After, 403 amână domeniul o oră, iar erorile temporare au reîncercare progresivă. După cinci eșecuri taskul intră în error. robots.txt inaccesibil nu este considerat permisiune. Redirecturile sunt raportate pentru verificare. Verifică raport.json înainte de reluări repetate.

## Teste

```powershell
python -m unittest scraping.test_scraper_stiri scraping.test_curata_si_exporta_articole -v
```

Testele acoperă parsarea, paginarea, cache-ul, reluarea din SQLite fără HTML, erorile, curățarea și exportul. Nu validează semantic toate știrile și nu necesită modulul ai/.
