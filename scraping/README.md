# Știri despre accidente cu pietoni în Iași

Fișierele Python au nume descriptive: scraper_stiri.py (fost news.py), procesare_articole_ai.py (fost team_ai.py), test_scraper_stiri.py și test_procesare_articole_ai.py. Folosește comenzile actualizate de mai jos.

Scraper_stiri descarcă listările și articolele, extrage textul din HTML și aplică filtrele de candidați. Procesare_articole_ai convertește CSV-ul în contractul modulului colegului și, opțional, îl apelează. Cu --doar-pregatire nu se face inferență AI și nu se elimină articole după relevanță. Testele verifică aceste componente, fără scraping live sau Ollama.

Cleanup-ul se face în două locuri: extract() din scraper_stiri.py elimină elemente HTML de interfață înainte de extragere; curata_text_articol() din procesare_articole_ai.py elimină numai eticheta finală „Lasă un răspuns Anulează răspunsul” din textele CSV existente. Acesta din urmă nu șterge documente. Filtrarea relevanței este separată, în prefilter()/classify() și în rezultatele modulului AI.

Fișierul pregătit pentru coleg este [predare_ai/articole_v2.json](predare_ai/articole_v2.json), cu [instrucțiuni de rulare](predare_ai/CITESTE-MA.md). Pentru actualizări periodice, vezi [AUTOMATIZARE.md](AUTOMATIZARE.md).

Pentru trimiterea textelor colectate către modulul AI existent al colegului, vezi [PROCESARE_ARTICOLE_AI.md](PROCESARE_ARTICOLE_AI.md). Scraperul extrage textul din HTML; modulul AI extrage informațiile despre accident din acel text. Păstrează atât textul, cât și URL-ul. Verificatorul separat scraping.verify a fost eliminat.

Colector pentru BZI și Ziarul de Iași, fără API comercial, date oficiale sau model AI. Rulează din rădăcina repository-ului, cu Python 3.10+. Datele sunt relatări observate în presă, nu accidente validate. Nu modifică datele aplicației, fixture-urile sau harta.

## Pornire în PowerShell

```powershell
python -m pip install -r scraping/requirements.txt
python -m scraping.scraper_stiri --de-la 2026-01-01 --pana-la 2026-10-17 --max-taskuri 200
```

Repetă aceeași comandă pentru a continua. Intervalul este inclusiv; `--pana-la` înseamnă **sfârșitul intervalului**, spre deosebire de scriptul inițial. Implicit: de la 1 ianuarie 2026 până la ziua rulării. Bugetul limitează taskurile, nu cererile HTTP: citirea robots.txt necesită o cerere suplimentară per domeniu și proces.

Modul implicit este acum rapid: se citesc paginile Local în ordine, se caută cuvinte-cheie în titlu, rezumatul cardului și URL, apoi se descarcă numai articolele selectate. Include `accident`, `pieton`, `trecere`, `călcat`, `lovit`, `mortal`, `mort`, `decedat`, `acroșat`, `spulberat`, `rănit` și alte variante. Lipsa tuturor acestor indicii poate omite o știre relevantă; pentru o cercetare suplimentară poți folosi `--exhaustiv`.

Dacă ai pornit versiunea veche, oprește cu Ctrl+C și rulează aceeași comandă. Coada existentă se refiltrează automat, iar paginile deja descărcate sunt recitite din cache. Nu este nevoie să ștergi baza sau să folosești `--actualizeaza`. Articolele eliminate de prefiltru primesc starea `filtered`, păstrând URL-ul și indiciile din listare.

Pentru o primă verificare scurtă:

```powershell
python -m scraping.scraper_stiri --max-taskuri 8 --pauza 5
```

Coada este în `scraping/data/colectare.sqlite3`. Rulările folosesc același inventar indiferent de interval; exportul se recalculează din articolele deja procesate. Pentru o colectare independentă folosește alt `--director`. Rulează un singur proces per director și per domeniu, pentru a păstra limitarea cererilor.

## Ce primești

- `inventar_urluri.csv`: toate linkurile descoperite, inclusiv cele filtrate, încă nedescărcate sau cu erori; conține și titlul/rezumatul/data din listare când sunt disponibile.
- `articole.jsonl`: corpul integral extras din fiecare articol procesat, metadate, proveniență și indicii cu dovezi. Păstrează și articolele din afara intervalului pentru audit.
- `candidati.csv`: articole cu indicii de pieton/traversare și impact, publicate în interval sau cu data publicării necunoscută. Include accidente cu răniți, decese și consecințe încă necunoscute. Nu este o listă de accidente confirmate.
- `raport.json`: numere pe sursă/tip/stare, taskuri rămase, erori și momentele de reîncercare (Unix UTC).
- `cache/`: răspunsurile descărcate. Nu este trimis în Git.

Consola afișează câte carduri și câte articole selectate are fiecare listare, apoi `CANDIDAT` sau `NERELEVANT DUPĂ TEXT` pentru articolele procesate. Exportul se actualizează după fiecare articol și periodic în timpul descoperirii; nu trebuie să aștepți sfârșitul rulării.

Valorile necunoscute sunt `null` în JSON și celule goale în CSV. Un `true` din clasificare este **un indiciu textual pentru review**, nu confirmare oficială. `mentiune_trecere` nu dovedește că pietonul se afla pe marcaj. `municipiul_iasi` caută o mențiune explicită a municipiului/orașului; simplul „Iași”, numele unui cartier sau categoria Local nu stabilesc geografia. Nu se deduce automat vinovăția, viteza ori vizibilitatea.

`data_accidentului` este o **dată posibilă extrasă dintr-o propoziție despre accident**, numai când există o singură dată explicită distinctă. Necesită verificare: poate aparține unui alt episod. Nu este copiată din data publicării. Ora nu este inventată. `accident_in_interval=false` semnalează inclusiv articole judiciare recente despre accidente vechi; acestea rămân vizibile în candidați pentru audit. Verifică ambele câmpuri de interval înainte de includerea într-un set final.

## Descoperire și reluare

Pornirea include arhivele Local ale ambelor publicații. Se urmărește doar pagina următoare, evitând salturile spre ultima pagină a arhivei. Sitemap-urile sunt opționale (`--sitemap`), deoarece pot aduce foarte multe articole din alte secțiuni și perioade. URL-urile sunt normalizate și deduplicate; fiecare origine se păstrează separat.

Se oprește extinderea unei ramuri de paginare când toate cardurile principale au date explicite anterioare începutului intervalului. Dacă există date necunoscute, continuă. Această optimizare presupune o arhivă ordonată de la nou la vechi; o arhivă reordonată poate omite rezultate. Limita superioară filtrează în continuare exportul; colectarea poate traversa paginile mai noi decât aceasta. Adâncimea maximă implicită este 1000; nu reprezintă o garanție de acoperire a arhivei. Raportul nu pretinde un procent de completitudine.

Poți separa fazele sau selecta o sursă:

```powershell
python -m scraping.scraper_stiri --faza descoperire --max-taskuri 100
python -m scraping.scraper_stiri --faza articole --max-taskuri 200
python -m scraping.scraper_stiri --surse zdi --max-taskuri 50
python -m scraping.scraper_stiri --export-only --de-la 2026-01-01 --pana-la 2026-10-17
```

Implicit se alternează o listare și două articole selectate, când coada permite. `--exhaustiv` reactivează și articolele `filtered`, păstrând progresul deja făcut. Pentru reevaluarea textelor disponibile după alte reguli, nu este nevoie de cereri noi.

Linkurile găsite prin căutare web pot completa inventarul. Pune URL-uri absolute, unul pe linie, într-un fișier UTF-8; liniile cu `#` sunt comentarii. Acceptă doar cele două domenii selectate, fără a accesa alte gazde.

```powershell
python -m scraping.scraper_stiri --urluri scraping/urluri.txt --max-taskuri 100
```

La erori temporare, taskul rămâne în coadă, cu reîncercare progresivă; după cinci eșecuri intră în `error`. HTTP 429 respectă `Retry-After` și suspendă domeniul. HTTP 403 suspendă domeniul o oră. robots.txt inaccesibil nu este interpretat ca permisiune. URL-urile interzise devin `blocked`. Redirecturile sunt raportate pentru verificare, fără urmărire automată. Pentru un redirect legitim, adaugă manual destinația acceptată în fișierul cu URL-uri.

```powershell
python -m scraping.scraper_stiri --reincearca --max-taskuri 100
python -m scraping.scraper_stiri --actualizeaza --max-taskuri 200
```

`--reincearca` rearmează erorile și blocările, dar verifică din nou robots.txt și păstrează pauza domeniului. `--actualizeaza` golește cache-ul taskurilor terminate și le rearmează, pentru știri actualizate sau o nouă parcurgere a listărilor. Este o operație asupra întregului director de colectare. Dacă nu mai există taskuri eligibile acum, rularea se încheie și exportă raportul; repetă comanda după expirarea pauzelor. Ctrl+C păstrează progresul deja confirmat; descoperirile taskului întrerupt sunt refăcute la reluare.

Pentru identificare poți seta `--user-agent "SafeIasiResearch/1.0 (+contact real)"`. Pauza implicită este 5 secunde, ajustabilă, minimum o secundă; crawl-delay din robots.txt poate crește pauza.

## Review necesar înainte de hartă

Verifică în text: municipiul, data reală a accidentului, pietonul rănit, poziția pe trecere și relatarea explicită a neacordării priorității. Păstrează cazurile neclare separat. Două articole despre aceeași zi și aceeași stradă nu sunt automat același accident. `incident_id` rămâne gol până la asocierea umană; nu număra rândurile CSV ca accidente și nu calcula risc direct din volumul știrilor.

## Verificări

```powershell
python -m unittest scraping.test_scraper_stiri -v
```

Testele sunt offline: metadate JSON-LD, paragrafe scurte, containerul editorial ZDI, paginare, sitemap XML, deduplicare/proveniență, reluarea cozii, 429, robots.txt indisponibil, roșu la semafor, data accidentului diferită de publicare și exportul erorilor. Verificarea live limitată din 17 octombrie 2026 a descărcat patru listări BZI/ZDI și trei articole (două BZI, unul ZDI), cu corp și dată extrase. Nu validează întreaga arhivă sau precizia clasificării; modificările site-urilor pot necesita ajustarea selectorilor.
