# Pornirea locală SafeIași

Backend v0.7 include [geocodarea asistată în review](GEOCODING_WORKFLOW.md), fără instalare suplimentară: candidat pending → preview OSM offline → confirmare și corectură versionată → aprobare separată. Indexul este citit numai la cerere.

Etapa curentă: FastAPI cu `/health`, documentație interactivă, audit, extracția lui Emi, import/corectare/review cu persistență locală și [publicare explicită](PUBLICATION_WORKFLOW.md) cu context/scor și dosare exportabile. Cele trei ecrane Angular sunt conectate la aceste operații. [SafeCross](SAFECROSS.md) adaugă separat `/safecross`, cu instalare opțională, model YOLOX Nano și FFprobe. Nu avem încă un set de accidente reale revizuite sau un catalog integrat de măsuri. Pornirea serverului nu necesită chei, conturi sau repararea fixture-urilor; vechile rute de snapshot refuză seturile invalide, iar fluxul nou de publicații este independent de ele.

## Prima instalare — Windows / PowerShell

Frontend-ul folosește implicit API-ul HTTP, cu baza `/api/v1`. Pentru build este verificat **Node 24.19**; Node 20.11.1 global este prea vechi pentru Angular 21. Verifică `node --version` înainte de comenzi. Configurarea și limitele datelor sunt în [FRONTEND_HANDOFF.md](FRONTEND_HANDOFF.md), iar dovezile verificării în [FRONTEND_INTEGRATION.md](FRONTEND_INTEGRATION.md).

Python 3.12 este versiunea verificată în acest mediu. Din folderul repository-ului, cu versiunea integrată a backend-ului:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -r requirements-publication.txt
```

Pe laptopul lui Mihnea, folderul este:

```powershell
Set-Location 'C:\Users\Mihnea\Documents\ChatGPT\Mark AI Integrator\Ctrl-Alt-Dev-2026'
```

Instalarea pachetelor necesită internet. Mediul `.venv/` rămâne local și este ignorat de Git. Apelăm direct Python din mediu, deci nu este necesară activarea lui sau modificarea politicii PowerShell.

Pentru interfața conectată, construiește o singură dată din `web/`:

```powershell
Set-Location web
npm ci
npm run build:local
Set-Location ..
```

`build:local` generează `web/dist/web/browser` cu `<base href="/ui/">`. FastAPI îl servește la `/ui/`, pe aceeași origine cu API-ul. Helper-ul de build folosește implicit `CI=true`, `GOMAXPROCS=2`, `NG_BUILD_MAX_WORKERS=1` și `NG_BUILD_PARALLEL_TS=false`, numai pentru procesele lansate; valorile explicite ale mediului sunt păstrate. Aceasta limitează memoria și evită cache-ul persistent care a produs eroarea LMDB pe laptopul verificat. Nu schimbă setări globale.

Fără build, `/ui/` răspunde 503 `frontend_build_unavailable`, cu instrucțiunea de construire; API-ul pornește și funcționează independent. După modificări frontend, reconstruiește și reîncarcă pagina. O ieșire `mock`/Pages nu înlocuiește build-ul `/ui/`: rulează din nou `build:local` pentru găzduirea în FastAPI.

## Pornire și verificare

```powershell
.\.venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Păstrează terminalul deschis. Oprești serverul cu **Ctrl+C** în terminalul care l-a pornit. Pentru repornire folosești aceeași comandă; nu recreezi mediul la fiecare rulare.

- [Verificarea serverului](http://127.0.0.1:8000/health)
- [Documentația interactivă](http://127.0.0.1:8000/docs)
- [Contractul OpenAPI JSON](http://127.0.0.1:8000/openapi.json)
- [Interfața Angular conectată](http://127.0.0.1:8000/ui/)
- [Manifestul snapshot-ului](http://127.0.0.1:8000/api/v1/manifest)
- [Evenimentele eligibile](http://127.0.0.1:8000/api/v1/events)

Răspunsul așteptat de la `/health`:

```json
{"status":"ok","service":"safeiasi-api"}
```

Acesta confirmă numai că serverul răspunde. Nu certifică datele, disponibilitatea LLM sau finalizarea backend-ului. Adresa `/` redirecționează către `/docs`. Serverul ascultă pe laptopul local; în această etapă nu îl expunem în rețea.

Manifestul și evenimentele folosesc același snapshot încărcat la pornire. Implicit acesta este `false_data/`, care este încă incomplet: cele două rute răspund **503 `invalid_snapshot`** cu diagnostice, în timp ce `/health` rămâne 200. Pentru selectarea unui director sintetic coerent, filtrare și coduri de eroare, vezi [contractul citirii](SNAPSHOT_READ_API.md). După corectarea sau schimbarea fișierelor trebuie repornit serverul; nu sunt reîncărcate automat la fiecare cerere.

UI-ul conectat nu citește aceste două rute legacy. Citește o publicație completă, fixează `snapshot_id` și păstrează versiunea pentru hartă, dosar și export. Modul implicit este `observed`: pe serverul normal, lipsa unei publicații produce o stare goală explicită, cu importul accesibil. Un 503 este afișat ca eroare; nu încarcă fixture-uri sau date din celălalt mod.

Dintr-un al doilea terminal PowerShell poți verifica răspunsul astfel:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Pentru reîncărcare automată în dezvoltare, adaugă `--reload` la comanda de pornire. Dacă portul 8000 este ocupat, păstrează aplicația existentă și pornește acest server cu `--port 8001`, folosind apoi 8001 și în linkuri.

`/health` și `/openapi.json` funcționează fără internet după instalare. Interfața Swagger de la `/docs` folosește implicit resurse CDN, deci în lipsa internetului verifică direct primele două adrese.

## Dezvoltare Angular și variante statice

Pentru reîncărcare frontend la editare, păstrează backend-ul pe 127.0.0.1:8000 și rulează separat, din `web/`:

```powershell
npm start -- --host 127.0.0.1 --port 4200
```

Deschide [127.0.0.1:4200](http://127.0.0.1:4200). Proxy-ul din `web/proxy.conf.json` trimite `/api` către 8000 cu `changeOrigin:false`, păstrând Host și Origin necesare controalelor locale. Nu folosi o adresă absolută către 8000 în clientul de pe 4200 și nu activa CORS larg: ar fi altă origine. Pentru dezvoltare împotriva altui port, adaptează deliberat ținta proxy-ului.

`npm run build:mock` produce o demonstrație statică sintetică; `npm run build:pages` produce aceeași variantă cu baza GitHub Pages. Sunt alese explicit, folosesc fixture-uri și reluări pregătite și nu permit scrieri de review/publicare. Nu sunt o rezervă automată a modului HTTP și nu certifică datele vechi. `npm run build` construiește varianta HTTP cu baza implicită pentru alte găzduiri; pentru `/ui/` folosește `build:local`. Camerele și fundalul stradal au dependențe externe proprii și rămân separate de datele publicate.

## Extracția AI

Comanda standard `uvicorn api.main:app` include acum rutele lui Emi. Vechea pornire `uvicorn ai.app:app` este un alias compatibil, fără rute duplicate.

| Rută/mod | Comportament |
|---|---|
| `POST /api/v1/ai/extract` | Primește un articol pe schema `2.0`; implicit `pipeline: "hybrid"` |
| `POST /extract` | Alias compatibil, cu același handler; nu este afișat separat în Swagger |
| `GET /api/v1/ai/replays/syn-003` | Exemplu de reluare sintetică salvată, etichetată explicit |
| `pipeline: "rules"` | Extracție prin reguli, fără apel de model; nu este AI live |

Poți verifica integrarea fără model, pe un articol sintetic deja existent:

```powershell
$article = (Get-Content -Raw -Encoding utf8 false_data/articles.json | ConvertFrom-Json)[0]
$body = @{ article = $article; pipeline = 'rules' } | ConvertTo-Json -Depth 10
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/ai/extract -ContentType 'application/json; charset=utf-8' -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
Invoke-RestMethod http://127.0.0.1:8000/api/v1/ai/replays/syn-003
```

Răspunsurile indică `processing_mode`, `data_mode` și `review_status: "pending"`. Candidații au `verificat: false`, iar localizarea rămâne necunoscută până la verificare/geocodare. Endpoint-ul returnează extracția fără a o salva, fără a aproba evenimente și fără a modifica snapshot-ul.

Pentru extracție AI live, modulul presupune Ollama disponibil la `http://127.0.0.1:11434`, cu modelul `qwen2.5:1.5b` deja instalat. Alege `pipeline = 'hybrid'` în cererea de mai sus. Configurația prin `SAFEIASI_AI_MODEL`, `SAFEIASI_AI_OLLAMA_URL` și `SAFEIASI_AI_CACHE_DIR` este descrisă în [README-ul AI](../ai/README.md#local-model-configuration). Integrarea nu instalează sau descarcă modelul; `/health` nu verifică disponibilitatea lui.

Erorile de contract produc **422**, o reluare inexistentă produce **404**, iar indisponibilitatea modelului produce **503** cu `errors` și eventuali candidați `rules_fallback`, încă neverificați. Nu tratăm acest fallback ca procesare AI reușită. `cache` și `replay` sunt răspunsuri salvate, nu inferență live; `replay` folosește și eticheta explicită „SYNTHETIC REPLAY”.

Un articol real poate produce candidați `observed` pentru verificare. Aceasta nu autorizează publicarea lor prin cititorul de snapshot, care acceptă în continuare numai date sintetice validate. Limitele actuale ale extractorului, inclusiv articolele lungi și cele cu mai multe evenimente, sunt documentate în modulul AI.

## Explorarea tiparelor recurente

Aceeași pornire `uvicorn api.main:app` include [demo-ul interactiv](http://127.0.0.1:8000/patterns), `GET /api/v1/ai/patterns/corpus` și `POST /api/v1/ai/patterns/discover`. `ai.patterns.app:app` este un alias compatibil pentru aceeași aplicație, inclusiv setările de snapshot și review. Nu trebuie pornit un al doilea server.

Interfața arată grupuri semantice între locuri, pasajele disponibile, diferențele și proveniența câmpurilor. Eliminarea unui caz recalculează grupurile fără să modifice fișierele sau deciziile operatorului. Există controale pentru prag, restabilirea cazurilor, modul de surse și exportul analizei. Harta este o diagramă geografică pe coordonate sintetice, fără fundal stradal.

Vectorii modelului multilingv sunt pregătiți în repository; vizualizarea și regruparea nu descarcă modele și nu trimit date către un serviciu AI. `ai/patterns/static/index.html` funcționează și fără server. Sunt 17 evenimente fictive, dar numai 3 au articole atașate; potrivirea exactă a fragmentelor explicative există pentru 2. Modul de surse se abține, iar fixture-urile rămân etichetate explicit. Similaritatea nu este probabilitate de accident sau dovadă a unei cauze.

Dacă datele de intrare se schimbă, rutele de tipare întorc **503 `patterns_unprepared`** până la regenerare. Demo-ul HTTP refuză și un HTML care nu mai corespunde vectorilor pregătiți; versiunea HTML deschisă direct este un export înghețat. Instrucțiunile de pregătire, modelul fixat și testele sunt în [README-ul investigatorului](../ai/patterns/README.md). Regulile de publicare ale snapshot-ului și protecțiile review-ului rămân active.

## Import și review cu salvare

`POST /api/v1/imports` salvează articolul și candidații neverificați; rutele `/api/v1/candidates` permit citire, corectare și decizie explicită, cu istoric și versiuni. `/api/v1/reviewed-events` arată evenimentele canonice locale și sursele lor. Un duplicat se asociază prin `action=link`, nu prin crearea automată a unui al doilea accident.

Datele sunt separate în `runtime/review/synthetic.json` și `observed.json`, ignorate de Git. Directorul se poate selecta cu `SAFEIASI_REVIEW_DIR`. Rulează un singur proces local, fără `--workers`; rutele de review refuză accesul de la distanță și din altă origine. Stocarea nu necesită o bază de date și nu modifică `false_data/`. Aprobarea nu schimbă snapshot-ul hărții.

În UI, ecranul **Import** permite introducerea articolului integral, alegerea explicită `rules` sau `hybrid`, recitirea candidaților salvați, corecturi motivate și decizii versionate. Confirmările sursei, duplicatului și localizării pornesc nebifate. Geocodarea observată are preview și aplicare separate; contextul sintetic se alege explicit. Panoul de publicare cere o selecție verificată, perioadă și preview înainte de publicarea efectivă. Un eșec al modelului nu creează import reușit, iar lipsa unei publicații nu blochează această muncă.

Vezi [contractul și exemplul PowerShell complet](REVIEW_WORKFLOW.md) pentru import, păstrarea necunoscutelor, corectare, aprobare/respingere și asocierea surselor. Actorul din istoric este declarat de operator; nu există autentificare cu conturi. Inferența nereușită nu este salvată ca import reușit, iar răspunsurile recitite sunt marcate `stored_review`.

## Publicare și dosare pentru frontend

Instalează `requirements-publication.txt` pentru geometrie și scor. După aprobare, rutele `/api/v1/publications/preview` și `/api/v1/publications` verifică selecția și îngheață o versiune locală. `/api/v1/locations`, `/api/v1/locations.geojson` și dosarele/exporturile citesc aceeași versiune. În lipsa unei publicații apare 404; nu se servește automat un set din celălalt mod.

Urmează [ghidul de publicare](PUBLICATION_WORKFLOW.md) pentru contract, configurație și repetiția completă `python -m api.demo_publication`. Aceasta folosește un director sintetic nou, nu repară și nu modifică `false_data/` și nu schimbă analizele SafeCross sau corpusul lui Emi. Aprobarea simplă nu publică automat, iar rutele vechi de snapshot își păstrează contractul.

Repetiția izolată din `runtime/publication-demo/`, pornită conform acelui ghid pe 8001, are **șase evenimente din șapte articole, la trei locații fictive**. După `build:local`, deschide [demo-ul conectat](http://127.0.0.1:8001/ui/?data_mode=synthetic). Serverul normal 8000 rămâne pe datele sale observate, momentan fără accidente publicate. Aceste directoare runtime sunt locale, nu se livrează prin Git și nu apar automat pe alt laptop. UI-ul nu conectează importurile noi la `/patterns` sau SafeCross.

## Teste și audit

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m unittest discover -s ai/tests -v
.\.venv\Scripts\python.exe -m unittest discover -s ai/patterns/tests -v
.\.venv\Scripts\python.exe -m api.validate_fixtures false_data
```

Testele HTTP folosesc clientul ASGI local și verifică inclusiv pornirea dintr-un folder temporar gol, fără credențiale AI. Auditul doar citește fixture-urile sintetice pe schema `2.0`. În setul actual raportează intenționat codul de ieșire **1**: există patru articole în loc de cele 18 declarate și 14 referințe de articole lipsă. Această eroare de date nu împiedică pornirea serverului.

Testele AI folosesc mock-uri și cache-ul experimental sintetic; nu descarcă modele și nu necesită un serviciu Ollama. Integrarea verifică și importul ambelor puncte de pornire, fără rute duplicate sau apeluri de provider la pornire.

## Probleme uzuale

| Mesaj/situație | Ce verifici |
|---|---|
| `No module named fastapi` sau `uvicorn` | Ai instalat `requirements.txt` și folosești `.venv\Scripts\python.exe`, nu Python global |
| `Could not import module api.main` | Terminalul este în rădăcina repository-ului și conține codul de pe ramura backend |
| Port ocupat | Folosește un port liber, de exemplu 8001; nu opri procese necunoscute |
| `/docs` gol fără internet | Deschide `/health` sau `/openapi.json`; Swagger are resurse CDN |
| `/ui/` răspunde `frontend_build_unavailable` | Din `web/`, cu Node 24 verificat, rulează `npm run build:local`; reîncarcă `/ui/` |
| UI fără locații pe 8000 | Verifică modul și publicația; lipsa datelor observate este reală. Folosește explicit repetiția sintetică izolată pentru demonstrație |
| 403 în UI | Folosește `/ui/` pe originea API sau proxy-ul de dezvoltare care păstrează Host/Origin |
| Build cu memorie insuficientă / LMDB | Folosește helper-ul `build:local`, închide procesele de dezvoltare pe care le-ai pornit și verifică spațiul liber; nu șterge datele de lucru |
| Auditul întoarce `1` | Citește raportul; nu este un eșec de instalare și nu trebuie ascuns prin inventarea datelor lipsă |

Pașii rămași pentru un demo pe date observate sunt colectarea și verificarea efectivă a surselor, trei dosare pregătite și catalogul documentat de măsuri. Pentru AI live trebuie verificat separat Ollama/modelul; pe laptopul verificat lipsesc, iar `rules` și reluarea etichetată sunt variantele disponibile. Surse pentru convențiile framework-ului: [FastAPI — pornire](https://fastapi.tiangolo.com/tutorial/first-steps/), [medii virtuale](https://fastapi.tiangolo.com/virtual-environments/), [testare](https://fastapi.tiangolo.com/tutorial/testing/), [încărcare la pornire](https://fastapi.tiangolo.com/advanced/events/).
