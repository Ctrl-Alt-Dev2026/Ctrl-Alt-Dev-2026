# Măsuri candidate — Persoana 5, etapa inițială

Sugestii AI prin [scraperul ChatGPT incremental](BACKEND_HANDOFF.md), fără API AI,
cu cache per articol și citate exacte validate. Alternativa manuală este în
[CHATGPT_WEB.md](CHATGPT_WEB.md). Regulile și catalogul determinist rămân separate.

## Extensie: viteza raportată

Contractul existent folosește cauza_raportata="viteza". Nu schimbăm enum-ul și
nu clasificăm noi textul articolului: extracția și verificarea rămân la colegi.
Minimum un eveniment cu această cauză declanșează analiza_viteza, vizibilă în
lista scurtă după observația în teren. Se propun evaluarea limitei adecvate,
controlului vitezei/radarului și calmării traficului. Nu se deduce o depășire
măsurată ori vinovăția și nu alegem automat o limită nouă sau un radar fix.

Pentru limitator/trecere înălțată, viteza raportată poate înlocui condiția școlii
apropiate, dar rămân necesare două benzi și confirmările privind compatibilitatea
drumului și traseele de autobuz/intervenție. Pe patru benzi rămâne analiza
generală a vitezei, fără limitator automat. Costul noii analize și efectele
ei sunt necunoscute. O limită maxspeed din OSM nu declanșează regula.

Referință: [FHWA, gestionarea vitezei](https://highways.dot.gov/safety/speed-management/speed-concepts-informational-guide/chapter-7-managing-traffic-speed).
Acestea sunt opțiuni pentru analiză locală, nu norme juridice românești.
Catalogul are acum nouă intrări. Cele trei scenarii existente păstrează cauzele
necunoscute, deci nu primesc artificial această propunere; regula este verificată
prin cazuri sintetice de test separate.

Modul separat: citește cele trei scenarii existente și produce un catalog și
propuneri explicabile. Nu modifică scorurile, hotspot-urile originale, frontend-ul,
backend-ul, documentele comune sau false_data/measure.json. Nu generează PDF,
pitch, costuri totale ori estimări de accidente evitate.

## Rulare

Din rădăcina repository-ului, fără API-uri sau dependențe noi:

```powershell
python -m measures.run --inspect
python -m unittest measures.test_rules -v
```

Prima comandă recalculează și afișează rezultatele fără scrieri. Pentru export:

```powershell
python -m measures.run --output measures/output/review-02
```

Directorul trebuie să fie nou. Livrabilul de referință este
`measures/output/three-scenarios/`, inclus în Git; celelalte rulări sunt ignorate.
Necesită setul existent `risk/output/frontend-scenario/data/`.

## Reguli și date necunoscute

Regulile provin din Planificare.md secțiunea 7. Pragurile sunt convenții MVP ale
echipei, nu concluzii științifice sau norme românești. Fiecare regulă are starea
matched, not_matched ori insufficient_data. null nu declanșează o condiție pozitivă.
Evenimentele identice sunt deduplicate; duplicatele contradictorii sunt respinse.
Ora nu este folosită pentru a inventa noapte=true; cauzele nu sunt ghicite.

| Măsură | Condiție implementată |
|---|---|
| Analiza iluminatului | Trecere și minimum două evenimente cu noapte=true; nu presupune că iluminatul lipsește |
| Analiza semaforizării | Trecere, semafor explicit false, minimum patru benzi |
| Analiza unei insule | Aceeași configurație; existența și fezabilitatea unei insule se verifică înainte de orice lucrare |
| Trecere înălțată / calmarea vitezei | Școală apropiată, evenimente pietonale, exact două benzi și confirmări explicite de compatibilitate a drumului, absenței traseului de autobuz și intervenție |
| Analiza intersecției | Intersecție și minimum două evenimente cu neacordare_prioritate raportată explicit |
| Analiza traversării la stație | Trecere, stație apropiată și evenimente; proximitatea nu demonstrează că accidentul are legătură cu stația |
| Observație în teren | Proprietăți esențiale de infrastructură necunoscute |

Condiția de două benzi și verificările pentru calmare sunt o alegere conservatoare
MVP, nu o interdicție universală de proiectare. Refuzul unei reguli nu dovedește
că o măsură este inutilă. Propunerile nu autorizează lucrări.

Toți candidații sunt salvați. Pentru afișare se aleg maximum trei: observația în
teren mai întâi, apoi ordinea stabilă a catalogului. Această ordine nu reprezintă
eficacitate, urgență sau analiză cost-beneficiu. Insula și semaforizarea sunt
opțiuni de analizat, nu un pachet de lucrări de executat împreună.

## Rezultate pe cele trei scenarii

Toate trei au minimum două evenimente nocturne sintetice, patru benzi reale,
semafor=false și iluminat necunoscut. De aceea lista scurtă este aceeași:
observație în teren, analiza iluminatului, analiza semaforizării. Nu ajustăm
regulile pentru a forța rezultate diferite.

- Grigore Ghica Vodă: scor 13 neschimbat; mai sunt candidate analiza insulei și a traversării la stație.
- Dacia: scor 11 neschimbat; aceleași alternative; un eveniment are noapte necunoscută.
- Sfântul Lazăr: scor 9 neschimbat; analiza insulei rămâne alternativă;
  regula pentru stație este blocată de date lipsă.

Nicio trecere înălțată/limitator nu este propus(ă): toate au patru benzi, iar
regula MVP cere două. Nu sunt intersecții, deci regula de organizare a
intersecției nu se aplică. Cauzele accidentelor din aceste scenarii rămân null.

## Catalog și proveniență

Estimările orientative sunt acum atașate fiecărei locații în
scenario_measures.json (measure_details) și livrate pentru frontend în
frontend_measures.json. Ambele includ sursa, anul, TVA, formula și limitele.
Vezi [FRONTEND_HANDOFF.md](FRONTEND_HANDOFF.md) pentru legarea la crossing_id și
hotspot_id. Catalogul comun nu este extins; catalogul local păstrează valorile
ferme null, iar estimările istorice sunt câmpuri separate, etichetate explicit.

- measures.json respectă structura Measure existentă, cu opt intrări.
- catalog_provenance.json conține sursele regulilor și referințele tehnice.
- scenario_measures.json conține scenariul explicit, hash-urile intrărilor,
  evenimentele folosite, toate regulile evaluate, candidații și lista scurtă.

Actualizare: cercetarea este în [RESEARCH.md](RESEARCH.md), cu patru repere de
cost și cinci fișe CMF, condiții și motive de neaplicare. Rulează
`python -m measures.research` pentru afișarea offline. Exportul include acum
research_evidence.json. Toate costurile, sursele de cost și reducerile sunt null. Valorile fictive din
false_data/measure.json nu sunt citite. Nu avem încă un cost local comparabil
sau un CMF ales pentru condițiile acestor locații. Aceasta acoperă regulile și
catalogul inițial, nu finalizează cercetarea F2/F3.

Referințe tehnice FHWA consultate la 17 octombrie 2026:

- [Vizibilitatea trecerilor](https://highways.dot.gov/safety/proven-safety-countermeasures/crosswalk-visibility-enhancements): iluminat, marcaje și vizibilitate.
- [Insule de refugiu](https://highways.dot.gov/safety/proven-safety-countermeasures/medians-and-pedestrian-refuge-islands-urban-and-suburban-areas): context de analiză pentru drumuri cu mai multe benzi.
- [STEP](https://highways.dot.gov/safety/pedestrian-bicyclist/step): familii de intervenții pietonale, fără echivalarea automată a dispozitivelor americane cu semaforizarea românească.
- [Traffic calming](https://highways.dot.gov/safety/speed-management/traffic-calming-eprimer/module-3-part-3): elemente de proiectare; nu sursă de costuri în lei sau regulă normativă pentru Iași.

## Scraper web independent, fără API AI

Pentru toate articolele și procesare numai a celor noi/modificate, rulează
`python -m measures.web_pipeline --channel msedge --manual-wait 600`.
Verificarea fără trimiteri este `python -m measures.web_pipeline --plan`.
Integrarea concretă pentru backend este în [BACKEND_HANDOFF.md](BACKEND_HANDOFF.md).
Exportul incremental este separat de pilot și include acoperirea tuturor
articolelor, inclusiv pending/blocked/invalid. Cache-ul trebuie păstrat între rulări.
Verificare live: toate cele 94 de articole procesate; rerularea a reutilizat
94/94 din cache și nu a trimis articole noi. Rezultatul are 133 de sugestii
neaprobate, justificate prin 225 de citate exacte; nu reprezintă accidente unice
confirmate sau măsuri aprobate.

Workerul opțional `python -m measures.web_scraper` este documentat în
[WEB_SCRAPER.md](WEB_SCRAPER.md). Rulează separat de Codex, cu Playwright,
cache și validare, fără modificări în backend. Testul headless s-a oprit la
Cloudflare; testul ulterior în Edge vizibil a reușit complet, fără cont:
trei articole, patru sugestii și opt citate exacte. Opțiunea `--manual-wait 600`
permite intervenția utilizatorului înainte de send dacă reapare o verificare.

## Integrare ulterioară

Nu am populat masuri în datele comune. Colegul poate folosi ulterior suggested
ca structură HotspotMeasure (measure_id, motiv, de_verificat), împreună cu
catalogul, după stabilirea integrării. Lista goală existentă din backend rămâne
neschimbată. Modul observed cere evenimente marcate observed și verificate,
context OSM și asociere explicită; acest adaptor inițial acceptă conservator
numai coordonate identice cu locația. Nu face asociere prin proximitate și nu
înlocuiește verificarea/publicarea backend. Nu este încă un adaptor complet de
publicații versionate. Scenariile mixte nu se importă drept observed.
