# Audit flux live — 18 octombrie 2026

Verificare a versiunii curente de pe `fix_risk_score`, după integrarea
`isu/ai.py`. Auditul nu a modificat codul de producție, documentele colectate,
răspunsurile AI sau baza de date folosită de aplicație.

## Fluxul efectiv

1. **Colectare HTTP, fără LLM.** `isu/live.py` pornește scraperul de presă și
   colectorul ISU. `isu/collect.py` descarcă PDF-uri noi după filtrarea titlurilor;
   pypdf extrage textul și SQLite păstrează documentele.
2. **Relevanță și extracție.** Presa trece prin prefiltrele scraperului. Pentru
   textele cu răspuns salvat, `isu/ai.py` folosește verdictul Claude:
   `accident_actual`, `urmare_judiciara`, `alt_subiect`, `neclar`. Doar primul
   produce evenimente. Relevanța și parametrii sunt returnate în același răspuns
   structurat. Identificatorul modelului din configurație și cele 94 de răspunsuri
   salvate este `claude-haiku-5-5`. Auditul nu a făcut apeluri noi la furnizor.
   Comunicatele ISU sunt parsate prin reguli, fără LLM.
3. **Validare și deduplicare.** Valorile extrase din presă cer citate care apar
   în text; datele și orele au verificări de format. Articolele sunt grupate în
   evenimente. Datele fără răspuns Claude trec prin reguli provizorii.
4. **OSM local.** Geocoderul existent folosește indexul OSM salvat, aliasurile,
   limita administrativă și nodurile cunoscute. Nu se cere modelului să inventeze
   coordonate și nu se descarcă OSM la fiecare articol. Locațiile grosiere nu
   devin puncte de accident; harta folosește geometria străzii existente.
5. **Analiză Python.** Străzile păstrează separat ISU, presă și PMUD. Scorul
   pe fiecare sursă de evenimente este `N + 4*deces + 2*grav + context`, cu
   context 0 pe stradă. Ora, noaptea și cauza sunt statistici și dovezi pentru
   studii, nu termeni noi în formulă. OSM descrie strada, fără atribuire la
   accidente. H3 primește numai coordonate precise.
6. **Două tipuri de recomandări.** `recomandari_ai` conține studii Claude din
   catalog, cu ID-uri de evenimente ale străzii și indicator de actualitate.
   `analiza.{isu,presa}.masuri` conține recomandările deterministe bazate pe
   cauze. AI-ul nu primește contextul OSM îmbogățit sau scorul în `street_input`;
   primește evenimente, semnale și totalurile PMUD. Nu produce devize sau
   amplasamente. Reperele unitare documentate sunt în secțiunea deterministă,
   nu sunt atașate în prezent fiecărei sugestii AI.
7. **Persistență și UI.** Dataset-ul este salvat în SQLite; API-ul îl servește
   cu analiza pe străzi, iar Angular afișează geometria, sursele, scorul,
   statisticile și sugestiile marcate ca rezultate salvate.

## Ce a fost executat și validat

`runtime/audit_live_pipeline.py` a reconstruit dataset-ul din documentele ISU
salvate și CSV-urile de presă versionate. Rețeaua și apelurile modelului au fost
blocate explicit. S-a folosit SQLite temporar, apoi endpointul real
`GET /api/v1/live/dataset` prin TestClient. Raportul este disponibil local în
`runtime/pipeline-audit/report.json`.

- 431 evenimente: 398 ISU și 33 presă; 49 geometrii de stradă.
- 94/94 articole de intrare au răspuns Claude salvat: 33 acceptate, 23 urmări
  judiciare, 38 alte subiecte. Aceste numere sunt articole clasificate, nu o
  regulă că un articol ar fi întotdeauna un accident.
- 23 străzi au 25 sugestii AI acceptate; niciuna nu este marcată învechită.
  Toate ID-urile de măsură sunt în catalog, iar dovezile se referă la evenimentele
  străzii. `observatie_teren` poate exista fără un eveniment citat.
- Sumele pe ore + necunoscute, cauze, zi/noapte și componentele scorului se
  reconciliază pentru fiecare stradă și sursă.
- Zero locații precise, zero celule H3; nicio coordonată grosieră nu este
  servită ca punct al unui accident.
- 418 evenimente fără cauză, 11 cu traversare neregulamentară și 2 cu
  neacordare de prioritate. Nu sunt deduse cauze din OSM.
- Build Angular reușit; rămâne avertismentul existent de buget CSS (+243 B).
- Browser desktop și mobil: navigare, schimbarea sursei/ordonării, grafice,
  context OSM, studii deterministe și sugestii AI cu eticheta de replay; zero
  erori JavaScript. Basemap local gol pentru izolarea straturilor aplicației.

## Probleme reproduse / limite

1. **Prefiltrul live este încă orientat pe pietoni.**
   `scraping/scraper_stiri.py:classify` setează `candidat` prin
   `pedestrian and collision`, iar `export` scrie în `candidati.csv` numai
   candidații. Pipeline-ul live și pasul Claude citesc acel CSV, deși noua
   extracție și UI declară toate accidentele rutiere. Exemplul de control cu
   două autoturisme și șoferi răniți nu ajunge candidat. Trebuie aliniată selecția
   înainte de a pretinde acoperire pentru toate tipurile de participanți.
2. **Deduplicarea de presă poate uni accidente distincte.**
   `isu/build.py:press_events` grupează după aceeași stradă și publicare la
   maximum o zi, fără verificarea datei/orei accidentului și fără protejarea
   accidentelor distincte din același articol. Două evenimente de test cu
   `event_key` diferite, date și ore diferite, pe aceeași stradă, au produs unul.
   Este o reproducere controlată, nu o afirmație că toate grupările actuale sunt
   greșite.
3. **Validarea AI este incompletă.** `verify` acceptă `2026-99-99`, pentru că
   verifică doar formatul, nu calendarul. `localitate` nu are citat obligatoriu
   sau verificare în text; proba cu `Iași` absent din articol a rămas acceptată.
   Strada este verificată prin potrivirea oricărui cuvânt mai lung, nu printr-un
   citat al denumirii complete. Prezența unui citat nu verifică semantic valoarea.
   Nici citatul verdictului de relevanță nu este validat înainte de excludere;
   în cache există un verdict cu citat care nu trece verificarea textuală.
4. **AI-ul nou nu rulează automat în colector/Docker.**
   `npm run ai` se execută separat pe calculatorul operatorului, prin Claude
   Code. Colectorul periodic reia răspunsurile salvate și folosește reguli pentru
   articolele noi. Pentru AI automat la fiecare lot este necesar un pas de lucru
   separat cu procesare, retry și monitorizare; nu există acum acel flux complet.
5. **Verificarea fizică a nodurilor OSM trebuie auditată.** Podu Roș este
   `verificat=true`, dar nota spune că a fost marcat pentru testare cu mock și
   agentul nu a confirmat nodul pe OSM. Geocoderul îl folosește ca nod verificat.
   Nu afectează H3 în snapshot-ul analizat (zero evenimente precise), dar flag-ul
   nu este singur suficient ca dovadă de verificare fizică pentru lucrări.

## Rezultatele testelor existente

- Setul de 69 teste pentru risk, măsuri, API live, scraper, extracție și
  geocodare: **68 trecute, 1 eșuat**. Testul eșuat presupune că Podu Roș este
  neverificat, deși fișierul actual are `verificat=true`.
- `python -m unittest discover -s ai/tests`: **66/68 trecute**. Două teste ale
  fluxului Gemini/cache eșuează: hash-ul CSV-ului nu mai corespunde manifestului
  cache, iar replay-ul raportează `cache_miss`. Normalizarea CRLF nu rezolvă
  nepotrivirea. Acest flux nu mai alimentează harta live actuală, care citește
  `isu/ai.py`, dar API-ul vechi nu poate fi declarat complet validat.

Verdict: traseul actual de replay până la UI funcționează și analiza se
reconciliază; acoperirea tuturor accidentelor, robustețea validării și
deduplicării și automatizarea AI au probleme deschise. Nu este o validare a
conectivității externe, a autentificării Claude sau a calității semantice a
fiecărei interpretări AI.
