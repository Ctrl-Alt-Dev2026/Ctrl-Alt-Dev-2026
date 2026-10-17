# Automatizare asistată prin browser, fără API plătit

Pentru workerul Python independent de Codex, vezi [WEB_SCRAPER.md](WEB_SCRAPER.md).
Documentul de față descrie numai vechiul transport operat de asistent.

Transportul folosește sesiunea ChatGPT vizibilă și acțiunile UI sau WebMCP
expuse de pagina curentă. Nu se apelează endpoint-uri private, nu se copiază
cookie-uri/tokenuri, nu se ocolesc CAPTCHA sau limitele contului.

Acesta este un flux rulat de asistent în browserul conectat, nu un serviciu
Python autonom care funcționează pe fundal independent de sesiunea Codex.
`browser_flow.py` gestionează pachetul, jurnalul și validarea; nu conduce singur
browserul și nu contactează ChatGPT.

Test live reușit la 18 octombrie 2026, fără cont: trei articole trimise ca text,
răspuns final citit din DOM-ul afișat și validat local. Butonul Send dezactivat
într-un composer gol nu indica o cerință de autentificare. După introducerea
textului, pagina a acceptat mesajul fără login.

## Fluxul de text

1. `python -m measures.browser_flow prepare --output measures/output/browser-run-N`
   creează un job nou și CHAT_MESSAGE.txt, conținând promptul, schema și articolele.
2. Asistentul verifică conversația nouă și composerul gol, apoi introduce textul.
   Poate folosi sesiunea fără cont dacă pagina permite. Dacă apare efectiv o
   cerință de login ori o verificare de securitate, aceasta se rezolvă de utilizator.
3. Înainte de unicul send, jurnalul este trecut în dispatch_started:
   `python -m measures.browser_flow mark --job measures/output/browser-run-N --state dispatch_started`
4. Asistentul trimite textul prin acțiunea normală a paginii, apoi citește starea
   conversației. Un send dispecerizat nu se reîncearcă automat. Înregistrează ID-ul:
   `python -m measures.browser_flow mark --job measures/output/browser-run-N --state sent --conversation-id ID`
5. Asistentul așteaptă răspunsul final, citește JSON-ul afișat și îl salvează în
   cache. Nu sunt acceptate mesaje incomplete, răspunsuri din altă conversație sau
   rezultatul unei cereri vechi drept rezultat curent.
6. `python -m measures.browser_flow finish --job measures/output/browser-run-N --response measures/cache/response.json`
   verifică pachetul, articolele și citatele; salvează datele numai după validare.

Fără schimbări de stare permise, comanda refuză trimiterea/finalizarea duplicată.
Jurnalul nu este un mecanism de blocare pentru procese concurente: un singur
asistent/proces trebuie să opereze un job. După întrerupere în dispatch_started,
se inspectează conversația înainte de a lua o decizie; nu se presupune eșecul.

## Ce se poate garanta

Se poate verifica dacă am primit JSON valid, cu articolul corect și citate exacte.
Nu putem garanta disponibilitatea ChatGPT, autenticitatea unui fișier adus manual,
corectitudinea semantică sau fezabilitatea lucrării. Sugestiile nu sunt aprobate
automat și nu au asociere OSM. Erorile opresc fluxul, fără rezultate inventate.
Pentru demo poate fi folosit un rezultat verificat anterior, etichetat explicit
„reluare”, separat de o cerere live. Nu există o comutare automată care să îl
prezinte ca răspuns nou.

Teste offline: `python -m unittest measures.test_browser_flow measures.test_chatgpt_exchange -v`.

## Rezultatul testului fără cont

Job local: `measures/output/browser-text-01/job.json`, stare `validated`.
Conversație: `6ad3f427-67b4-83ea-8a64-e584cc0491b8`.
Răspuns brut: `measures/cache/chatgpt-guest-response.json`.
Rezultat validat: `measures/output/browser-text-01/chatgpt_suggestions.json`.
Aceste rezultate de rulare și cache-ul sunt ignorate de Git.

S-a trimis o variantă compactă a instrucțiunilor, cu toate paragrafele originale
ale celor trei articole și aceleași ID-uri de pasaje; nu textul identic octet cu
octet din CHAT_MESSAGE.txt. Hash-urile jobului identifică pachetul pregătit,
nu atestă identitatea promptului compact efectiv trimis.

Răspunsul a identificat articolul despre controale drept nerelevant; pentru
Podu Roș și Nicolina a oferit câte două sugestii, cu șapte citate exacte în total.
Toate cele patru sugestii rămân `needs_human_review`, fără costuri sau reduceri
inventate și fără asociere automată la OSM. Modelul nu a fost afișat în sesiune.
Importerul generic păstrează eticheta `external_manual_chatgpt_response`;
ID-ul conversației și acest jurnal descriu preluarea asistată din browser.

Acest test confirmă fluxul în sesiunea disponibilă, nu disponibilitatea permanentă
și nici un serviciu automat în backend. Comanda `finish` poate valida din nou
un răspuns salvat printr-un job nou; nu trimite singură articole către ChatGPT.
