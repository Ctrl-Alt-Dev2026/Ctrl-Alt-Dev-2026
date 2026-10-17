# Pornirea locală a backend-ului SafeIași

Etapa curentă: FastAPI cu `/health`, documentație interactivă, audit și citire de snapshot sintetic validat. Extracția AI, review-ul, frontend-ul și publicarea datelor reale urmează separat. Pornirea serverului nu necesită chei, conturi sau corectarea fixture-urilor; rutele de date refuză seturile invalide.

## Prima instalare — Windows / PowerShell

Python 3.12 este versiunea verificată în acest mediu. Din folderul repository-ului, pe ramura `codex/backend-foundation`:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Pe laptopul lui Mihnea, folderul este:

```powershell
Set-Location 'C:\Users\Mihnea\Documents\ChatGPT\Mark AI Integrator\Ctrl-Alt-Dev-2026'
```

Instalarea pachetelor necesită internet. Mediul `.venv/` rămâne local și este ignorat de Git. Apelăm direct Python din mediu, deci nu este necesară activarea lui sau modificarea politicii PowerShell.

## Pornire și verificare

```powershell
.\.venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Păstrează terminalul deschis. Oprești serverul cu **Ctrl+C** în terminalul care l-a pornit. Pentru repornire folosești aceeași comandă; nu recreezi mediul la fiecare rulare.

- [Verificarea serverului](http://127.0.0.1:8000/health)
- [Documentația interactivă](http://127.0.0.1:8000/docs)
- [Contractul OpenAPI JSON](http://127.0.0.1:8000/openapi.json)
- [Manifestul snapshot-ului](http://127.0.0.1:8000/api/v1/manifest)
- [Evenimentele eligibile](http://127.0.0.1:8000/api/v1/events)

Răspunsul așteptat de la `/health`:

```json
{"status":"ok","service":"safeiasi-api"}
```

Acesta confirmă numai că serverul răspunde. Nu certifică datele, disponibilitatea LLM sau finalizarea backend-ului. Adresa `/` redirecționează către `/docs`. Serverul ascultă pe laptopul local; în această etapă nu îl expunem în rețea.

Manifestul și evenimentele folosesc același snapshot încărcat la pornire. Implicit acesta este `false_data/`, care este încă incomplet: cele două rute răspund **503 `invalid_snapshot`** cu diagnostice, în timp ce `/health` rămâne 200. Pentru selectarea unui director sintetic coerent, filtrare și coduri de eroare, vezi [contractul citirii](SNAPSHOT_READ_API.md). După corectarea sau schimbarea fișierelor trebuie repornit serverul; nu sunt reîncărcate automat la fiecare cerere.

Dintr-un al doilea terminal PowerShell poți verifica răspunsul astfel:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Pentru reîncărcare automată în dezvoltare, adaugă `--reload` la comanda de pornire. Dacă portul 8000 este ocupat, păstrează aplicația existentă și pornește acest server cu `--port 8001`, folosind apoi 8001 și în linkuri.

`/health` și `/openapi.json` funcționează fără internet după instalare. Interfața Swagger de la `/docs` folosește implicit resurse CDN, deci în lipsa internetului verifică direct primele două adrese.

## Teste și audit

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m api.validate_fixtures false_data
```

Testele HTTP folosesc clientul ASGI local și verifică inclusiv pornirea dintr-un folder temporar gol, fără credențiale AI. Auditul doar citește fixture-urile sintetice pe schema `2.0`. În setul actual raportează intenționat codul de ieșire **1**: există patru articole în loc de cele 18 declarate și 14 referințe de articole lipsă. Această eroare de date nu împiedică pornirea serverului.

## Probleme uzuale

| Mesaj/situație | Ce verifici |
|---|---|
| `No module named fastapi` sau `uvicorn` | Ai instalat `requirements.txt` și folosești `.venv\Scripts\python.exe`, nu Python global |
| `Could not import module api.main` | Terminalul este în rădăcina repository-ului și conține codul de pe ramura backend |
| Port ocupat | Folosește un port liber, de exemplu 8001; nu opri procese necunoscute |
| `/docs` gol fără internet | Deschide `/health` sau `/openapi.json`; Swagger are resurse CDN |
| Auditul întoarce `1` | Citește raportul; nu este un eșec de instalare și nu trebuie ascuns prin inventarea datelor lipsă |

Pasul următor este contractul de import cu Emi; publicarea datelor observate necesită validarea și fluxul de review aferente, conform [planului backend](BACKEND_WORK_PLAN.md). Surse pentru convențiile framework-ului: [FastAPI — pornire](https://fastapi.tiangolo.com/tutorial/first-steps/), [medii virtuale](https://fastapi.tiangolo.com/virtual-environments/), [testare](https://fastapi.tiangolo.com/tutorial/testing/), [încărcare la pornire](https://fastapi.tiangolo.com/advanced/events/).
