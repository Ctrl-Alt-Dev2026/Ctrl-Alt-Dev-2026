# Gemini API: configurare și testare din Postman

## Pentru colegi: doar cache, fără cheie

Pachetul `ai/cache_presa/` și CSV-ul clean sunt în repository. După pornirea
backendului, folosiți POST `/api/v1/ai/extract` cu:

```json
{"mode":"gemini_csv", "cache_only":true}
```

Acesta este modul implicit și nu citește cheia, nu construiește clientul Gemini
și nu apelează rețeaua. Returnează JSON cu articolele valide și extracțiile.
Un lot lipsă produce HTTP 409 (`cache_miss`), nu apel API. `api_calls:0` și
`cache_hits` indică sursa rezultatului. Instrucțiuni: [cache_presa/README.md](cache_presa/README.md).
Cache-ul personal `work/` rămâne ignorat de Git; partajăm doar pachetul verificat.
Pentru teste offline, folosiți `limit:4`; un limit care schimbă gruparea loturilor
poate produce cache miss (de exemplu 2 în locul primului lot de 4).

Secțiunile următoare sunt pentru proprietarul cheii care dorește apeluri API reale.

Flux: CSV clean (94 articole) → Gemini pentru filtrare + extracție împreună →
validarea și normalizarea modulului colegului → exporturi. Fără browser, Ollama
sau date mock. Textele și URL-urile sunt trimise către Google în loturi de 4.
Nu se instalează biblioteci noi: clientul folosește REST și biblioteca standard.

Prompt v2: sunt selectate relatări de la producerea accidentului și actualizări
imediate despre pietoni loviți. Știrile cu subiect principal sentința, procesul,
arestarea sau despăgubirile pentru un accident trecut sunt excluse, chiar dacă
reiau detaliile accidentului. Menționarea deschiderii unui dosar în știrea inițială
nu o exclude. Actualitatea se raportează la publicare, nu la ziua rulării.
Coliziunile cu răniți doar șoferi/pasageri nu sunt accidente cu pietoni.
`tip_stire_ai` din CSV și `clasificare.tip_stire` din JSON arată această categorie.
Schema de extracție se trimite o singură dată pe lot; textele nu sunt trunchiate.

Cache-ul vechi este păstrat, dar nu reutilizat la schimbarea promptului.
Prima rulare cu v2 necesită o nouă evaluare; apoi repetarea aceluiași lot/model
reutilizează rezultatele v2. Promptul nou este parte din cheia cache-ului.

## 1. Cheia și Free Tier



Gemini 3.1 Flash-Lite are intrare/ieșire gratuită pe Free Tier, în limita
cotelor proiectului. Verifică limitele efective în AI Studio; nu presupunem
o anumită cotă zilnică. Când cota se termină, codul se oprește la HTTP 429,
nu activează billing și nu schimbă modelul. Codul nu poate verifica nivelul
de facturare doar din cheia API. Dacă proiectul este deja Paid, cererile pot
fi taxate chiar dacă modelul există și în Free Tier.

Surse oficiale: [billing](https://ai.google.dev/gemini-api/docs/billing),
[pricing](https://ai.google.dev/gemini-api/docs/pricing#gemini-3.5-flash-lite),
[chei API](https://ai.google.dev/gemini-api/docs/api-key).

## 2. Unde pui cheia

În `ai/gemini.local.json`, înlocuiește numai `PUNE_CHEIA_AICI`:

```json
{"api_key":"PUNE_CHEIA_AICI", "model":"gemini-3.5-flash-lite"}
```

Fișierul local este ignorat de Git. Nu trimite cheia în chat, în Postman Body,
frontend sau commit. Pentru colegi există `gemini.example.json`: îl copiază în
`gemini.local.json` și completează propria cheie. Alternativ, serverul citește
`GEMINI_API_KEY` și `SAFEIASI_GEMINI_MODEL` din mediu, cu prioritate față de fișier.
Configurația este citită la fiecare cerere, dar repornește backendul pentru
a încărca noile rute după actualizarea codului.

## 3. Test mic de conexiune

În Postman: POST `http://127.0.0.1:8000/api/v1/ai/extract`, Body → raw → JSON:

```json
{"mode":"gemini_test"}
```

Face o singură cerere scurtă, fără articole. Răspunsul așteptat include
`ok: true`, `provider: "gemini"` și modelul. `billing_verified: false` înseamnă
că testul nu verifică facturarea: tu verifici proiectul în AI Studio.

422 cu mesaj despre cheie = completează fișierul local. 503 cu Gemini HTTP
400/401/403 = verifică cheia/accesul; 404 = model indisponibil; 429 = cotă sau
limită de ritm. Nu activa billing pentru a rezolva automat o eroare de cotă.

## 4. Test pe CSV și rulare completă

Aceeași adresă, Body:

```json
{"mode":"gemini_csv", "limit":2, "cache_only":false}
```

Procesează primele două articole, care pot fi ambele respinse; în acest caz
`articole_valide` este o listă goală, iar `clasificare.csv` conține cele două decizii.
Elimină `limit` pentru toate cele 94 de articole. Timeout Postman: 0. Cererea
este sincronă; nu apăsa Send repetat. La succes primești JSON cu raportul
și `articole_valide`, o listă de obiecte cu cele șapte câmpuri ale articolului
(`article_id`, `sursa`, `url`, `titlu`, `text`, `publicat_la`, `colectat_la`),
`clasificare` (stare, motiv, citate, issues) și `extragere` (rezultatul modulului
colegului). Evenimentele normalizate sunt în
`articole_valide[i].extragere.candidates`. Sunt pending, nu aprobate automat.
`valid`, `rejected`, `uncertain` sunt numere de articole, nu accidente unice.
`complete_input` indică dacă s-a procesat întregul CSV; pentru limit=2 este false.
Nu se fac apeluri AI suplimentare pentru JSON: rezultatele sunt deja în memorie.
Fișierele sunt păstrate pentru export și reluare în `ai/work/gemini/`:

- `clasificare.csv`: fiecare articol, text, link, verdict, motiv, citate, extracție;
- `articole_valide.csv`, `articole_respinse.csv`, `articole_neclare.csv`;
- `extractii.json`: rezultatele în contractul colegului, pending/neaprobate;
- `raport.json`: progres și erori;
- `responses/`: prompt și răspuns real, fără cheia API, pentru reluare.

Răspunsul trebuie să acopere exact toate ID-urile din lot. Citatele inexistente
fac verdictul neclar. Nu se apelează Qwen după Gemini: răspunsul Gemini trece
prin validarea existentă a colegului. Filtrarea acceptă cazuri probabile, păstrează
neclar lipsa/contradicția dovezilor privind traversarea regulamentară.

La eroare se întoarce 503 și raportul; repetarea folosește loturile deja salvate
pentru același model/prompt. Nu există retry automat sau fallback la alt model.
Răspunsurile brute deja salvate sunt revalidate local după o corecție de cod,
fără o nouă cerere AI. Un boolean primit greșit ca identificator de frază este
înlocuit cu dovadă necunoscută (`null`), niciodată cu fraza 0/1; corecția este
raportată în issues. Alte extracții cu tipuri invalide devin neclare pentru
articolul respectiv, fără să oprească restul lotului.
Exporturile unei rulări complete anterioare pot rămâne pe disc: verifică întotdeauna
statusul din raport, processed/input_count și complete_input înainte să le folosești.

Verificare locală fără consum API:
`python -m unittest ai.tests.test_gemini_client ai.tests.test_gemini_pipeline -q`.
Rularea reală necesită cheia ta și `cache_only:false`; testele locale folosesc
răspunsuri simulate sau cache-ul real salvat, fără consum API.
