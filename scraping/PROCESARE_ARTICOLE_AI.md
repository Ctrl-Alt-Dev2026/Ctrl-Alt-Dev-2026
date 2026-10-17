# Pregătirea și procesarea articolelor cu modulul AI existent

CSV curățat, păstrând toate coloanele și rândurile, plus JSON pentru coleg:

    python -m scraping.procesare_articole_ai --doar-pregatire --director scraping/predare_ai --csv-curatat scraping/articole_extrase_accident_clean.csv

Originalul raw nu este modificat. Pentru setul curent: 94 de rânduri, 37 de body-uri cu eticheta terminală eliminată; niciun articol șters. Cleanup-ul este limitat la acea etichetă și nu validează relevanța/completitudinea textului.

## Ce distribui prin Git

Pentru colegul care rulează AI sunt suficiente CSV-ul clean sau predare_ai/articole_v2.json și codul. Textele sunt deja în fișier; acesta nu accesează publicațiile și nu are nevoie de cache-ul HTML.

scraping/data/ rămâne ignorat. Cache-ul HTML are aproximativ 192 MiB și 1275 de fișiere în verificarea curentă; este voluminos și nu este formatul de intrare al modulului AI. Nu îl adăuga forțat în Git.

Pentru cine continuă exact colectarea, baza colectare.sqlite3 conține taskurile, stările și articolele deja parsate. Se poate distribui separat un backup SQLite consistent (cu SQLite backup API sau cu scraperul oprit), pus apoi în scraping/data/. Cache-ul HTML poate fi arhivat separat dacă este nevoie de reparsare offline; nu este obligatoriu pentru articolele marcate done, al căror text este deja în bază. Refolosirea doar a cache-ului, fără baza de progres, nu reprezintă aceeași reluare. Nu copia baza în timp ce se scrie în ea folosind o simplă copiere de fișier.

Fișierul de rulare este procesare_articole_ai.py; test_procesare_articole_ai.py conține testele lui, nu un al doilea procesator AI. Acestea se numeau anterior team_ai.py și test_team_ai.py.

Cleanup-ul textelor CSV se găsește în funcția curata_text_articol(). Se elimină numai eticheta de comentarii de la final. Pregătirea exportă raport_pregatire.json, care numără rândurile citite, URL-urile unice, textele curățate, limita cerută și articolele exportate. Curățarea nu filtrează relevanța și nu elimină documente; numai URL-urile identice sunt deduplicate, iar --limit poate restrânge explicit o rulare de test.

Adaptorul nu modifică ai/ și nu introduce alt prompt: apelează ai.ExtractionService, păstrând rezultatele, dovezile și problemele raportate de acesta. Nu accesează publicațiile.

Fluxul este: URL -> scraper -> text și metadate -> modulul AI -> câmpuri despre accident și dovezi -> review și localizare. Modulul AI nu descarcă URL-ul, nu extrage text din HTML/PDF și nu face OCR. Câmpul text este obligatoriu; numai linkurile nu sunt o intrare suficientă. El extrage din text data evenimentului, ora, locul, participanții, cauza relatată, gravitatea și indicii despre noapte. URL-ul este păstrat ca sursă pentru verificare. Modelele rules/direct/evidence/hybrid/agreement sunt variante de procesare ale aceluiași modul; rules nu apelează LLM.

Rulare din rădăcina repository-ului:

    python -m scraping.procesare_articole_ai --pipeline direct

Implicit citește scraping/articole_extrase_accident_raw.csv, folosește configurația modulului colegului (qwen2.5:1.5b sau SAFEIASI_AI_MODEL) și scrie în scraping/data/ai_coleg/.

Test pe un articol:

    python -m scraping.procesare_articole_ai --pipeline direct --limit 1

Poți schimba modelul cu --model numai dacă este instalat. Adaptorul nu descarcă modele automat. Timeout implicit 600 secunde, fără reîncercare automată. La eroare salvează rezultatele și se oprește; inspectează extractii.json. Reluarea folosește cache-ul original al modulului, păstrat în directorul rezultatului.

Pentru comparație rapidă fără LLM:

    python -m scraping.procesare_articole_ai --pipeline rules --director scraping/data/ai_coleg_rules

Rularea rules pe cele 94 de articole este un diagnostic, nu validare LLM. Pe acest CSV include fals pozitive precum controale ale poliției și un accident feroviar; nu trimite aceste rezultate pe hartă fără review.

## Rezultate

- articole_v2.json: CSV convertit în contractul cu șapte câmpuri al modulului. Titlul și textul se păstrează; data colectării rămâne necunoscută.
- extractii.json: rezultatele complete ale serviciului, câte unul per articol.
- candidati_v2.json: candidații extrași, nemarcați ca verificați.
- toate.csv: linkuri, text, gravitate, loc, dată, dovezi și probleme.
- candidati_review.csv: numai articolele pentru care modulul propune candidați.
- excluse_sau_neclare.csv: celelalte articole, inclusiv erorile.

Un is_event=true cu probleme de grounding sau fără pieton în participanții extrași este exportat ca neclar, nu candidat. Rezultatul brut al modulului se păstrează în extractii.json și candidati_v2.json pentru audit.

## Comparație pe presa reală, 17 octombrie 2026

Modelul qwen2.5:1.5b a fost descărcat și testat local. Modul rules a procesat toate cele 94 de articole; comparația evidence a fost oprită după patru rezultate terminate, deoarece includea fals pozitive. Direct a fost testat pe primele trei articole: a exclus corect știrea despre controale ale poliției, dar a marcat cele două accidente feroviare ca evenimente, cu cinci și șase probleme interne de grounding. Aceste rezultate sunt neclare în CSV-ul adaptorului. Nu s-a realizat o validare LLM completă și fiabilă a celor 94 de articole.

Artefacte separate: scraping/data/ai_coleg_rules/, scraping/data/ai_coleg_qwen/ și scraping/data/ai_coleg_qwen_direct/. Modelele și pipeline-urile sunt indicate în rezultate; rularea rules nu este prezentată ca validare LLM.

Fișierele se actualizează după fiecare articol; nu le ține deschise în Excel în timpul rulării. Un singur proces per director. Numai articolele terminate apar în CSV-urile de rezultat; articole_v2.json conține intrarea completă selectată.

## Limite care contează pentru proiect

Modulul identifică evenimente cu pietoni și extrage câmpurile din contractul echipei; nu are un câmp explicit pentru pieton lovit pe trecere. Apartenența la municipiul Iași și coordonatele rămân necunoscute. Gravitatea necunoscută nu înseamnă lipsa rănirii; de exemplu, transportul la spital nu este suficient în acest modul pentru o categorie de gravitate.

Prin urmare candidati_review.csv nu este o listă de linkuri bune confirmate. Pe_trecere și in_iasi rămân goale. Data accidentului poate rămâne necunoscută când formularea nu este recunoscută; intervalul nu este filtrat de adaptor. Verificarea pe trecere, rănirea pietonului, municipiul, perioada și asocierea știrilor despre același accident rămân necesare înainte de hartă.

Pipeline-ul evidence face o singură citire LLM cu selecție de propoziții, apoi normalizare deterministă. Hybrid combină regulile cu o citire LLM și poate păstra fallback la eroare; adaptorul îl marchează ca eroare și se oprește. Agreement face două citiri și durează mai mult. Pe CPU, schimbarea modulului nu elimină costul încărcării și inferenței modelului.

Contextul original al modulului este de 4096 tokeni, pentru un eveniment. Articolele lungi sau cu mai multe accidente pot depăși această capacitate; adaptorul păstrează textul integral, dar nu garantează că modelul îl procesează integral.

Teste offline:

    python -m unittest scraping.test_procesare_articole_ai ai.tests.test_engine ai.tests.test_service -v
