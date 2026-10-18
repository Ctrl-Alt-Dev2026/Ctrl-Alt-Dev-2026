# Cache Gemini de partajat cu echipa

94 de articole de presă, în 24 de loturi, procesate anterior cu modelul și promptul
din `manifest.json`. Fișierele sunt răspunsuri reale salvate, nu mock-uri; nu includ
cheia API. Textele din prompt sunt relatări de presă nevalidate și pot menționa
persoane. Rezultatele rămân `pending`, nu evenimente aprobate pentru hartă.

Păstrați structura acestui director și CSV-ul sursă din
`scraping/articole_extrase_accident_clean.csv`. Nu aveți nevoie de
`gemini.local.json`, Ollama, browser sau de fișierele personale din `work/`.

În Postman: POST `http://127.0.0.1:8000/api/v1/ai/extract`, Body raw/JSON:

```json
{"mode":"gemini_csv", "cache_only":true}
```

`cache_only` este implicit true. Răspunsul este JSON cu `articole_valide` și
extracțiile lor. `api_calls: 0`, `cache_hits: 24`, `processed: 94` confirmă
reutilizarea completă. Exporturile sunt regenerate în `ai/work/gemini/`, ignorat
de Git. Pentru un subset de test: `limit: 4`. `limit: 2` schimbă primul lot;
poate lipsi din cache chiar dacă toate loturile de 4 sunt prezente.

Dacă CSV-ul, modelul, promptul ori gruparea loturilor se schimbă și lipsesc
rezultate compatibile, primiți HTTP 409, `status: "cache_miss"`. Niciun apel
Gemini nu este făcut. Nu există fallback automat la API. Fișierele sunt
revalidate local la citire; `manifest.json` include SHA-256 pentru verificare.

Numai pentru proprietarul cheii, apelurile reale cer explicit
`cache_only:false` și cheia locală. Pentru actualizarea pachetului după o
rulare completă: `python -m ai.exporta_cache`, apoi revizuiți schimbările Git.
Exportul verifică toate loturile înainte de publicarea manifestului.
