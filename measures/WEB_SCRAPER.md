# Worker independent de Codex, fără API AI

Pentru procesarea tuturor articolelor și cache per articol, folosește acum
`python -m measures.web_pipeline`, descris în [BACKEND_HANDOFF.md](BACKEND_HANDOFF.md).
Documentul de față descrie workerul inițial pentru cele trei articole din pilot.

`web_scraper.py` pornește propriul browser prin Playwright, introduce text în
ChatGPT și citește răspunsul din pagina afișată. Nu folosește WebMCP, Codex,
endpoint-uri AI, interceptarea rețelei, tokenuri sau cookie-uri copiate.
Nu există stealth, rezolvare automată de CAPTCHA sau ocolire de limite.

## Starea reală a testelor

- 18 teste offline: cache, blocare concurentă, așteptare manuală fără apăsarea
  verificării, continuare după apariția composerului, lipsa retrimiterii după eșec,
  JSON strict, identificarea articolelor și citate exacte. Transportul din teste
  este simulat, nu un răspuns nou de la AI.
- Test live separat, 18 octombrie 2026: Edge headless a afișat verificarea
  Cloudflare înainte de composer. Nu s-au trimis articole și nu s-a obținut
  un răspuns. Captura este în `measures/cache/web-scraper/*/page.png`.
- Test live ulterior, Edge vizibil cu `--manual-wait 600`: succes end-to-end,
  fără cont, fără Codex și fără API AI. Nu a fost necesară intervenția manuală
  în această sesiune. Trei articole trimise o singură dată, patru sugestii și
  opt citate exacte validate. Articolul despre controale a fost exclus corect.
  `cache_hit=false` confirmă un rezultat nou, nu reluarea unui răspuns anterior.
  Rezultat: `measures/output/web-scraper-visible-01/chatgpt_suggestions.json`.
  Jurnal/captură: `measures/cache/web-scraper-visible-01/*/job.json`, `page.png`.
  Succesul acestei sesiuni nu garantează disponibilitatea permanentă a site-ului;
  trecerea manuală a unei verificări reale nu a fost necesară în testul live.

## Instalare și comandă

Din rădăcina repository-ului, în PowerShell:

```powershell
python -m venv measures/cache/web-venv
measures/cache/web-venv/Scripts/python.exe -m pip install -r measures/requirements-web.txt
measures/cache/web-venv/Scripts/python.exe -m measures.web_scraper --channel msedge
```

Ultima comandă folosește Edge deja instalat și deschide o fereastră pentru
inspecție. `--headless` ascunde fereastra. Browserul este într-o sesiune nouă,
fără cont, profil persistent sau acces la profilul personal. Un blocaj de
securitate oprește rularea; nu este rezolvat automat.

Dacă Edge nu este instalat, se poate instala Chromium oficial:

```powershell
$env:PLAYWRIGHT_BROWSERS_PATH = "$PWD/measures/cache/playwright-browsers"
measures/cache/web-venv/Scripts/python.exe -m playwright install chromium
measures/cache/web-venv/Scripts/python.exe -m measures.web_scraper --headless
```

Variabila trebuie păstrată și la rulare. Dependința este izolată în measures/;
nu s-au schimbat requirements-urile comune. Instalarea nu garantează că site-ul
va permite sesiunea automatizată.

## Verificare manuală în browser vizibil

```powershell
measures/cache/web-venv/Scripts/python.exe -m measures.web_scraper --channel msedge --manual-wait 600 --timeout 180 --cache measures/cache/web-scraper-visible-01 --output measures/output/web-scraper-visible-01
```

`--manual-wait 600` ține browserul deschis până la zece minute înainte de send,
în timp ce utilizatorul rezolvă verificarea pe pagină. Workerul doar observă
apariția composerului și absența blocajului; nu apasă pe verificare. După aceea
trimite articolele o singură dată și așteaptă răspunsul maximum `--timeout`
secunde. Utilizatorul nu trebuie să introducă sau să trimită mesajul.

Opțiunea este incompatibilă cu `--headless`. La închiderea browserului ori
expirarea perioadei se oprește, păstrează captura/jurnalul și nu reîncearcă
automat. O verificare apărută după send oprește fluxul, fără un al doilea send.
Un browser vizibil sau un alt browser instalat poate avea alt comportament,
dar nu garantează dispariția verificărilor. Nu se schimbă automat browserul.

Pentru Chrome deja instalat există `--channel chrome`; o încercare nouă după
un blocaj necesită un cache separat, ales deliberat, după verificarea jurnalului.
Nu se importă sesiunea personală din Chrome sau Edge.

## Apelarea din backend

Workerul este un proces CLI care poate fi apelat prin subprocess de backend,
preferabil ca job de fundal, nu în cererea HTTP a utilizatorului. Nu am adăugat
apelul în fișierele colegului. Comanda rulează o singură dată, nu instalează un
serviciu sau scheduler. Nu necesită ca aplicația Codex să fie deschisă.

Pentru MVP analizează cele trei articole din pilot, citite din sursa existentă
`scraping/predare_ai/articole_v2.json`. Nu procesează automat întregul flux de
articole și nu modifică sursa. ID-urile sunt aceleași ca în exportul manual.

- Succes: exit code 0, sumar JSON pe stdout.
- Eșec/blocaj: exit code 2, mesaj JSON pe stderr; fără un rezultat nou validat.
- Rezultat: `measures/output/web-scraper/chatgpt_suggestions.json`.
- Stare: `measures/output/web-scraper/status.json`. Colegul trebuie să verifice
  exit code 0, `state=validated` și același `packet_id` în stare și rezultat.
  Un fișier vechi nu trebuie afișat ca răspuns al unei rulări eșuate.
- Sugestiile rămân `needs_human_review`, fără costuri inventate și fără asocieri
  OSM. Nu înlocuiesc măsurile deterministe existente sau scorurile.

Cache-ul depinde de versiune, pachetul sursă și promptul exact. La fiecare hit
se validează din nou JSON-ul, identitatea răspunsului și citatele originale.
Sursele schimbate invalidează cache-ul. Un singur worker poate opera același
director de cache simultan; backend-ul trebuie să-l pornească serial.

## După un blocaj

Se inspectează `measures/cache/web-scraper/*/job.json` și `page.png`.
Starea `dispatch_started` sau ulterioară poate însemna că mesajul a fost trimis:
nu se șterge jurnalul și nu se retrimite automat. Nici restartarea backend-ului
nu retrimite același job.

Pentru primul test headless, `last_phase=prepared`, iar captura arată Cloudflare,
deci mesajul nu a fost trimis. O nouă încercare se face numai deliberat, după
rezolvarea problemei, cu `--cache measures/cache/web-scraper-retry-N`. Nu există
un retry automat care schimbă browserul, IP-ul sau sesiunea pentru a evita
protecțiile. Un lock rămas după terminare forțată se elimină doar după ce
operatorul verifică faptul că procesul nu mai rulează.

Teste:

```powershell
python -m unittest measures.test_web_scraper measures.test_browser_flow measures.test_chatgpt_exchange -v
```

Referință: [Playwright Python](https://playwright.dev/python/docs/library).
