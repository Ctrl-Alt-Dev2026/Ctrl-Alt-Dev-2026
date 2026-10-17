# Verificarea interfeței conectate

Verificare locală la 17 octombrie 2026. Angular 21 consumă API v0.7; stack-ul existent este păstrat. Acesta este un rezultat de integrare, nu certificarea datelor pentru demo-ul final.

## Ce este conectat

- Harta, clasamentul, numărătorile, dosarul și fișa citesc aceeași publicație imuabilă. Filtrul de participanți nu recalculează scorul sau rangul. Exportul JSON/HTML include `data_mode` și versiunea afișată.
- Importul salvează articolul complet și candidații. Operatorul poate reciti extracția originală, corecta cu versiune/motiv, verifica localizarea și aproba, respinge sau asocia un articol unui eveniment existent.
- Geocodarea observată are preview și aplicare confirmată, separate de aprobare. În modul sintetic, alegerea contextului fictiv este explicită; încadrarea în municipiu rămâne o verificare distinctă.
- Aprobarea nu modifică harta. Publicarea are selecție de evenimente, asocieri verificate, perioadă, preview și confirmare separată. O publicare nouă fixează exact versiunea returnată, chiar dacă pagina afișa una veche.
- 404 pentru lipsa unei publicații înseamnă stare goală; 503 înseamnă eroare. Ambele păstrează accesul la import. Niciuna nu încarcă automat fixture-uri.

`npm run build:local` produce `/ui/` pe originea FastAPI. `npm start` folosește proxy-ul de dezvoltare. Variantele `build:mock` și `build:pages` sunt prototipuri statice explicite, fără scrieri. Comenzi: [pornire locală](LOCAL_DEVELOPMENT.md), [contracte](FRONTEND_HANDOFF.md).

## Verificări efectuate

Au trecut **246 teste Python**: 160 backend/review/publicare/SafeCross, 42 extracție AI, 21 patterns și 23 context/scor. Cele două teste noi din [test_frontend_host.py](../tests/test_frontend_host.py) verifică accesul local, traversarea căilor, activele și comportamentul unui build lipsă sau cu bază greșită.

Build-urile Angular `build:local` și `build:mock` trec cu Node 24.19. Există avertismente de buget CSS: `map-page.scss` 4,05 kB și `import-page.scss` 5,18 kB, sub limita de eroare de 8 kB. Helper-ul limitează paralelismul pe acest laptop; nu modifică dependențele sau setări globale.

Verificarea în browser folosește un profil izolat, date exclusiv sintetice și un director separat `runtime/ui-integration-demo/`, pe portul 8002. Nu modifică setul demonstrativ 8001 sau analizele video existente. Jurnalele și capturile locale sunt în `runtime/ui-connected-*.json` / `runtime/ui-connected-*.png`, ignorate de Git.

## Controlul regulilor de prezentare

Lista urmărește verificările din `.claude/skills/ui-honesty-check/SKILL.md`. Pentru fluxul HTTP, publicația serverului este sursa numărătorilor în locul manifestului vechi al prototipului.

| Verificare | Rezultat | Dovezi / corecție |
|---|---|---|
| 1. Fără promisiuni despre accidente evitate sau probabilități validate | PASS | [Dosarul](../web/src/app/features/location/location-dossier/location-dossier.html) precizează limitele scorului și ale măsurilor. |
| 2. Scorul nu este calculat în UI | PASS | [Proiecția](../web/src/app/core/models/publication.ts) copiază scorul/componentele/rangul; [store](../web/src/app/core/state/data.store.ts) filtrează afișarea. |
| 3. Necunoscut nu devine zero sau fals | PASS | Câmpurile infrastructurii folosesc `nullLabel`; scorul/rangul nul rămân neclasate. Introducerea numerică manuală și golirea coordonatelor sunt normalizate explicit. |
| 4. Sintetic și reluare vizibile | PASS | [Top bar](../web/src/app/shared/top-bar/top-bar.html), dosar, fișă și import; build-ul static explică reluarea și blochează scrierile. |
| 5. Numere și coordonate din sursa de date | PASS | Nicio completare artificială a clasamentului sau a accidentelor în modul HTTP. Metadatele camerelor sunt o extensie separată. |
| 6. Numărători și lungimea clasamentului | PASS | Publicația de repetiție: șase evenimente distincte, șapte articole, trei locații. |
| 7. Coerență hartă/dosar/fișă/export | PASS | Alfa: două evenimente, trei articole; fișa și exporturile sunt fixate la aceeași versiune. Catalogul gol dezactivează aplicarea măsurilor. |
| 8. Oră și iluminat necunoscute | PASS | Afișare explicită `oră necunoscută` și `necunoscut`; data accidentului și data publicării sunt separate. |
| 9. Localizare aproximativă fără pin precis | PASS, verificare de cod/contract | [Store](../web/src/app/core/state/data.store.ts) exclude coordonatele nule; backend-ul nu publică evenimente fără asociere precisă verificată. Repetiția curentă are numai locații precise; nu dovedește identificarea tuturor cazurilor din presă. |
| 10. Toate sursele evenimentului | PASS | Cele trei articole Alfa sunt afișate pentru două accidente, cu text, pasaje și istoric. Tooltip-urile redau text, fără HTML injectat. |
| 11. Fără fundal online | PASS | În browser, cererile externe blocate lasă straturile pe fundal simplu și afișează avertismentul; captură desktop verificată. |
| 12. Eșec procesare / versiune concurentă | PASS | AI indisponibil: 503, fără candidat nou și fără rezultat simulat. O corectură cu versiune veche: 409, fără suprascriere; operatorul recitește candidatul. |
| 13. Lizibilitate și mobil | PASS local | Capturi verificate la 1280×720 și 390 px; fără overflow orizontal, text de bază ≥14 px și contrast vizibil. Proiectorul fizic rămâne de verificat la repetiție. |
| 14. Demo final pe date observate | **BLOCANT** | Repetiția este integral sintetică. Nu există încă un set de accidente reale verificat/publicat; nu se prezintă drept date despre Iași. |

Corecțiile făcute în integrare: contractele HTTP provizorii au fost înlocuite, navigarea păstrează modul și pinul versiunii, coordonatele numerice/golite se salvează fără conversii greșite, iar textele surselor nu sunt injectate ca HTML în tooltip.

## Recuperarea unui import fără răspuns

Corecția formularului de import: câmpurile obligatorii lipsă și combinația sursă `SINTETIC` / mod `observed` sunt explicate înainte de trimitere. Importul are limită de așteptare (30 s pentru reguli, 180 s pentru AI) și buton „Oprește așteptarea”. Oprirea sau expirarea nu confirmă anularea procesării pe server; formularul și cheia cererii sunt păstrate pentru retry identic. Verificarea în browser include cerere ținută intenționat fără răspuns, expirare, oprire manuală și retry cu același `request_id`, pe un proxy local care nu transmite importuri backend-ului. Exemplul utilizatorului `mock-ui-001` a fost importat separat, în modul sintetic, ca un candidat pending; nu a fost aprobat sau publicat.

## Limite rămase pentru demo

Nu sunt pregătite accidentele observate verificate, catalogul de măsuri cu surse sau modelul local Ollama. `rules` este extracție deterministă, fără AI; `hybrid` depinde de serviciul modelului. Rezultatele arhivate nu sunt procesare live. `/patterns`, SafeCross și camerele rămân extensii separate; importul/publicarea nu le reantrenează și nu transformă observațiile video în accidente.

Demo-ul sintetic original rămâne la `http://127.0.0.1:8001/ui/?data_mode=synthetic`; serverele și datele runtime trebuie pornite/pregătite local conform ghidurilor. Nu există un parteneriat confirmat cu Primăria Iași și fișa nu reprezintă un audit rutier în teren.
