# Fluxul de presă în modulul existent

## Gemini API

CSV clean → Gemini (filtrare + extracție) → validarea colegului → exporturi.
Configurare și Postman: [GEMINI.md](GEMINI.md). Nu necesită Ollama sau browser.

Fluxul este implementat în ExtractionService, nu într-o aplicație separată și nu într-un nou endpoint CSV:

CSV-ul clean din scraping -> filtru Qwen -> articole_valide.csv -> extracția existentă.

## Testare din Postman

Cu backend-ul actualizat și Ollama pornite, trimite POST către http://127.0.0.1:8000/api/v1/ai/extract. În Body alege raw / JSON:

    {"mode": "press_csv", "pipeline": "hybrid", "limit": 3}

Aceasta testează primele trei articole. Pentru întregul CSV elimină limit din JSON. Nu selecta binary/form-data și nu încărca fișierul: serverul citește automat CSV-ul clean din scraping/.

Cererea este sincronă. În Postman setează Request timeout in ms la 0 pentru a aștepta lotul complet. Nu apăsa Send repetat cât timp rulează; închiderea cererii în Postman nu garantează oprirea procesării pe server. Raportul și fișierele apar în ai/work/presa/. HTTP 200 indică terminarea fără erori de procesare, nu validarea juridică a articolelor; 503 indică erori de model, iar 404 lipsa CSV-ului de pe server.

## Integrarea în codul aplicației

    from ai import ExtractionService

    service = ExtractionService()
    result = service.extract()

Fără argumentul article, modulul citește automat scraping/articole_extrase_accident_clean.csv. Nu trebuie trimis manual prin POST și nu trebuie încărcat articol cu articol. service.extract(article) continuă să extragă un singur articol ca înainte.

Pentru configurare din cod există service.extract_clean_csv(source=..., output=..., pipeline=...). Implicit rezultatele merg în ai/work/presa/. Intrarea este rezolvată relativ la repository, nu la directorul curent al aplicației. Modelul, endpoint-ul și cache-ul sunt cele deja configurate în modulul colegului, implicit qwen2.5:1.5b în Ollama local.

Pornirea obișnuită a modulului batch, fără selecție explicită de articole, folosește acum acest flux automat și un singur pipeline hybrid. Nu există comenzi separate pentru filtrare și extracție. Intrările JSON explicite de benchmark și diagnosticul explicit rules păstrează comportamentul anterior. Serverul API nu pornește inferențe automat la startup, iar paginile frontend nu au fost modificate.

## Ce face în interior

1. Citește toate articolele din CSV-ul clean.
2. Cere aceluiași model Qwen o selecție permisivă: pieton lovit de vehicul rutier, concret sau probabil. Lipsa datelor formale nu este motiv suficient de respingere.
3. Verifică dacă citatele modelului există în titlu/text; răspunsurile cu citate inventate devin neclare.
4. Scrie articole_valide.csv, articole_respinse.csv și articole_neclare.csv, cu motive și citate. Păstrează și clasificare.csv cu toate articolele evaluate.
5. Citește efectiv articole_valide.csv și trimite numai articolele de acolo către funcția existentă de extracție.
6. Scrie extractii.json și extractii.csv, apoi raport.json cu numere și erori.

Nu se face scraping, nu se rescrie body-ul și nu se modifică originalul. Textele sunt deja curate din scraping. Rândurile cu același URL au ID-uri distincte; nu sunt eliminate automat. Cazurile neclare nu sunt declarate valide și nu intră automat în extracție; rămân în fișier pentru review.

Filtrul inițial este intenționat larg (pieton + impact cu mașină/camion/autobuz etc.). Nu dovedește automat că pietonul traversa regulamentar, era pe trecere sau că accidentul este eligibil pentru hartă. Aceste verificări se fac asupra extracției și a sursei, păstrând necunoscut când nu există dovezi. Rezultatele extracției rămân review_status=pending și verificat=false.

Clasificarea și extracția folosesc cache-ul modulului; repetarea fluxului reutilizează inferențele deja salvate. Textele lungi sunt filtrate în fragmente suprapuse. Nu se unesc incidente distincte. Extracția ulterioară păstrează limitele originale ale modulului (context 4096 tokeni și un eveniment per articol).

La indisponibilitatea modelului, raportul arată interrupted_filtering și nu se începe extracția unui lot filtrat incomplet. CSV-ul sursă rămâne complet; clasificare.csv poate fi parțial, cu numărul filtered și input_count în raport. Erorile de extracție sunt salvate separat în rezultat, nu interpretate drept articole nerelevante.

Nu mai există endpoint-urile /api/v1/ai/extract-csv, server separat, pagină de filtrare sau pași manuali de POST/status/download.

Teste cu model simulat:

    python -m unittest ai.tests.test_press_pipeline -v
