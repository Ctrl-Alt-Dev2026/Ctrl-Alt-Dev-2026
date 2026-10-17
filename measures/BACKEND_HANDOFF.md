# Integrarea scraperului incremental de sugestii AI

Tot codul nou este în measures/. Nu s-au schimbat backend-ul, frontend-ul,
contractele comune sau sursa articolelor. Acesta este un worker CLI independent
de Codex, care folosește interfața web ChatGPT prin Playwright, fără API AI.

## Verificare efectivă pe sursa actuală

Test live complet la 18 octombrie 2026, în Edge vizibil, fără cont: 94/94
articole validate, dintre care 91 procesate atunci și trei adoptate din pilot.
Zero pending, blocked sau invalid. Rularea repetată a aceleiași comenzi a
reutilizat toate cele 94 de rezultate, cu `new_processed=0`, fără deschiderea
browserului sau trimiteri noi. Clasificarea modelului: 72 articole relevante,
133 sugestii și 225 citate exacte; toate sugestiile sunt neaprobate. Nu înseamnă
72 de accidente unice, confirmate sau localizate. Există 28 teste offline pentru
incrementalitate, identitatea sursei, cache, întreruperi și validarea JSON/citatelor.

## Ce are de făcut colegul de backend

1. Instalează dependența opțională din `measures/requirements-web.txt` în mediul
   Python al workerului. Pe calculatorul actual există mediul izolat
   `measures/cache/web-venv`; acesta nu intră în Git și se recreează pe alt host.
   Edge trebuie instalat pentru `--channel msedge`. Alternativ instalează
   Chromium cu `python -m playwright install chromium` și omite `--channel`.
2. După publicarea atomică a fișierului de articole, pornește un singur job de
   fundal, cu repository-ul ca working directory. Nu rula în cererea HTTP a
   utilizatorului și nu porni mai mulți workeri pe același cache.
3. Citește sumarul JSON de pe stdout, mesajele de progres de pe stderr și codul
   de ieșire. Încarcă rezultatul atomic descris mai jos. Nu deduce succesul doar
   din existența unui fișier mai vechi.
4. Servește sugestiile ca resursă separată asociată prin `article_id` și hash-ul
   conținutului. Ele nu au o legătură verificată cu trecerile OSM sau hotspot-uri.
   Legătura la un accident/locație trebuie făcută de componentele responsabile.
5. Păstrează cache-ul între deploy-uri/rulări pe un volum persistent. Fără el se
   pierde evidența procesării și articolele pot fi trimise din nou. Nu îl pune
   în Git sau în asset-urile publice. Păstrează și jurnalele loturilor incomplete.

## Comanda

Din rădăcina repository-ului, în mediul cu Playwright instalat:

```powershell
python -m measures.web_pipeline --input scraping/predare_ai/articole_v2.json --channel msedge --manual-wait 600
```

Pe calculatorul actual înlocuiește `python` cu
`measures/cache/web-venv/Scripts/python.exe`.

Aceeași comandă la următoarea rulare trimite doar articolele noi sau modificate.
`--limit 6` procesează maximum șase articole noi într-un job; următorul job
continuă cu restul. Fără limită procesează toate articolele restante. Lotul
implicit are maximum trei articole, ajustat la lungimea textului.

Verificare fără browser și fără trimiteri:

```powershell
python -m measures.web_pipeline --plan
```

`--plan` scrie doar `measures/output/web-incremental/plan.json`, nu schimbă
rezultatul publicabil sau evidența articolelor procesate. Opțiunile `--input`,
`--cache` și `--output` permit alte căi; toate scrierile trebuie să rămână în
measures/, cu directoare cache și output separate.

## Fișierul de consumat

`measures/output/web-incremental/chatgpt_suggestions.json`

Este o singură salvare atomică, cu schema locală `measures-web-pipeline-1`:

- `run_id`: identitatea ultimei rulări/exportări; compară cu sumarul stdout.
- `source_sha256`: hash-ul canonic al întregului snapshot de articole citit la
  început. Dacă sursa se schimbă în timpul jobului, pornește un job ulterior.
- `state`: `complete`, `partial` sau `stopped`.
- `counts`: total, validated, cached, new_processed, pending, blocked, invalid.
- `articles`: acoperire pentru fiecare articol din sursa actuală, inclusiv
  cele fără rezultat, cu stare, cheie și explicația erorii dacă există.
- `rows`: numai rezultate validate, inclusiv cele din cache, fiecare cu
  `article_id`, `article_sha256`, `browser_url`, `cache_hit`,
  `relevant_model_claim`, `reason` și `suggestions`.

`article_sha256` este hash-ul canonic al câmpurilor efectiv analizate:
article_id, sursa, url, titlu, text, publicat_la. `colectat_la` și metadatele
suplimentare nu invalidează cache-ul. Conținutul, titlul, URL-ul, sursa sau data
publicării modificate sunt reanalizate; ordinea articolelor nu contează.

Un articol cu `relevant_model_claim=false` și `suggestions=[]` este un rezultat
AI validat structural, nu o eroare. Și acest rezultat este memorat în cache.
Nu confunda pending/blocked/invalid cu „nu există probleme de siguranță”.

Fiecare sugestie păstrează citatul exact, passage_id și offset-urile în textul
original, verificările propuse, `status=needs_human_review`, `cost_ron=null`,
`reduction=null`, `location_id=null`. `approved_suggestions` rămâne 0.
Validarea nu stabilește corectitudinea semantică sau fezabilitatea tehnică.

## Coduri de ieșire și publicare

- **0:** `complete`, toate articolele din snapshot au rezultat validat;
  sau `planned` când s-a cerut explicit `--plan` (planul nu este un rezultat nou).
- **3:** `partial`, există articole pending din cauza limitei ori intrări
  invalide/prea lungi; rezultatele din rows pot fi servite cu acoperirea vizibilă.
- **2:** `stopped`, blocaj, eroare, rezultat nevalid ori lot anterior nerezolvat.
  Rezultatele validate înainte de blocaj sunt păstrate în snapshot-ul parțial.
  La eroare de preflight poate lipsi un sumar stdout nou: nu atribui fișierul
  anterior unei rulări eșuate. Backend-ul trebuie să păstreze identitatea ultimei
  rulări reușite/parțiale și să afișeze separat eroarea jobului curent.

Nu modifica scorurile de risc și nu popula automat măsuri aprobate din aceste
date. Nu introduce sugestiile în publicațiile observed existente fără asocierea
și review-ul cerute de integrarea comună.

## Întreruperi și intervenție manuală

Cache: `measures/cache/web-incremental/index.json` și `jobs/<hash>/`.
Fiecare lot păstrează articolele, promptul, răspunsul brut dacă a fost primit,
jurnalul și captura browserului. Un lot este revendicat înainte de Send.
La timeout, rezultat nevalid sau întrerupere nu se retrimite automat. Nici
restartul backend-ului nu retrimite lotul incert: apare blocked și jobul se
oprește înainte de alte trimiteri. Nu șterge cache-ul pentru a „repara” blocajul.
Operatorul trebuie să inspecteze jurnalul și conversația; recuperarea unui lot
incert nu este automatizată în acest MVP.

`--manual-wait 600` necesită un desktop vizibil pe hostul workerului; utilizatorul
poate rezolva verificarea înainte de send, apoi procesarea continuă. Nu este
compatibil cu `--headless`. Un server fără desktop nu poate oferi această
intervenție. Headless a întâlnit Cloudflare în testul inițial; Edge vizibil a
reușit în pilot. Nici sesiunea fără cont, nici disponibilitatea nu sunt garantate.
Nu există retry automat, rotație de browser/IP sau ocolire de verificări.

## Reutilizarea pilotului existent, opțional o singură dată

Pe acest calculator se poate adăuga la prima rulare:
`--seed-pilot-cache measures/cache/web-scraper-visible-01`.
Cele trei rezultate sunt adoptate numai după revalidarea sursei, promptului,
răspunsului și citatelor originale, păstrând proveniența. Dacă sursa a fost
schimbată între timp, adoptarea este refuzată. După popularea indexului opțiunea
nu mai înlocuiește nimic; nu poate suprascrie un lot incert.

Cache-urile și output-urile de rulare sunt ignorate de Git. În commit intră
codul, testele, documentația și requirements-ul opțional, nu mediul Python,
capturile, profiluri de browser sau cache-ul cu articole.
