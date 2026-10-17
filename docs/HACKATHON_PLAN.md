# SafeIași — organizarea echipei pentru un demo în 25 de ore

Plan propus la 17 octombrie 2026. Echipa: 6 persoane. Client vizat: Primăria Iași, cu utilizator operațional din zona de mobilitate/siguranță rutieră. Numele produsului este provizoriu.

Repository indicat: https://github.com/andrei-vladjitaru/Ctrl-Alt-Dev-2026/

**Starea verificării:** conexiunea GitHub a returnat 404 pentru repository și lista sa de fișiere; căutarea în repository-urile accesibile nu l-a găsit. Nu am putut verifica stack-ul, codul, branch-urile sau instrucțiunile AGENTS.md. Nu am modificat repository-ul și nu am publicat issues. Căile, contractele și sarcinile din acest document sunt propuneri de adaptat la codul existent. Nu înlocuiți un stack funcțional doar pentru a urma această propunere.

## 1. Decizia de produs

Construim un instrument care răspunde la întrebarea: **„Ce locații ar trebui să verifice prioritar administrația și pe ce dovezi ne bazăm?”**

Fluxul obligatoriu este: sursă → extragere AI → verificare umană → localizare → prioritizare explicabilă → măsuri candidate → fișă de verificare exportabilă.

Păstrăm din prima planificare responsabilul de integrare, analiza verificabilă, controlul uman și demo-ul reproductibil. Din a doua păstrăm harta, contextul infrastructurii și recomandările pentru administrație. Detecția video SafeCross devine o extensie care poate adăuga dovezi pentru o locație selectată.

**Demo-ul trebuie să funcționeze integral fără analiza video.** Aceasta intră numai dacă există deja un clip utilizabil și o procesare verificată, iar fluxul principal trece criteriile de acceptare. Datele video și accidentele documentate rămân categorii distincte; un conflict video nu se numără drept accident.

### Cele trei ecrane

1. **Harta priorităților:** locații, filtre, surse și perioada acoperită; clasament al locațiilor din eșantion. Titlul nu pretinde acoperirea tuturor accidentelor din Iași.
2. **Dosarul locației:** evenimente unice, sursele lor, precizia localizării, informații cunoscute/lipsă despre infrastructură, explicația scorului și 1–3 măsuri candidate.
3. **Import și verificare:** textul unui anunț/articol → câmpuri extrase cu dovezi → corectare/aprobare → actualizarea dosarului. Lipsurile rămân vizibile.

Rezultatul exportat este o fișă de verificare pentru administrație, nu un audit rutier certificat sau o decizie de amenajare.

### Dimensiunea realistă

- Prag minim pentru demo: 10 evenimente reale, distincte, verificate și localizate suficient de precis.
- Țintă: 20–40 de evenimente; extindere numai dacă fluxul și verificarea țin pasul.
- 3 dosare de locație revizuite complet pentru prezentare; numărul de evenimente din fiecare trebuie să fie cel real.
- 5 tipuri de măsuri în catalog, cu condiții de aplicabilitate și surse.
- Date sintetice doar pentru dezvoltare, într-un mod separat, marcat permanent.

Acestea sunt ținte de lucru, nu cantități de date deja obținute. Dacă nu găsiți suficiente evenimente pentru agregări utile, prezentați dosare individuale și explicitați limita eșantionului.

## 2. Împărțirea celor șase persoane

| Rol | Responsabilitate și limite | Primul rezultat verificabil | Rezultat înainte de înghețare |
|---|---|---|---|
| **P1 — coordonator tehnic și integrare** | Contracte, schelet rulabil, validare, pipeline, dependențe, integrare și versiunea de demo. Nu preia pitch-ul. | H+1: structura și contractele; H+3: prima integrare pe date sintetice | Pornire documentată, verificări automate esențiale, versiune reproductibilă pe laptopul de prezentare |
| **P2 — surse și extracție AI** | Import dintr-o listă mică de surse, extragere structurată, dovezi pentru câmpuri, gestionarea erorilor. P6 ajută la selecția articolelor. | H+3: câteva surse procesate și rezultat valid; demonstrație reală de extracție | Set de evenimente candidate, trasabilitate și rezultate salvate pentru demo |
| **P3 — geocodare și infrastructură** | Localizare asistată, verificarea municipiului, deduplicare geografică asistată de P6, H3, straturi OSM locale | H+3: primii candidați localizați și context minimal | Geometrii revizuite, strat H3 și context cu sursă/data verificării; vitezele sunt opționale |
| **P4 — prioritizare și recomandări** | O singură logică de calcul, catalog de măsuri și explicații bazate pe dovezi. Nu inventează cauze sau efecte | H+3: scor și recomandări pe fixture-uri | Clasament reproductibil, condiții de aplicabilitate, tratarea datelor lipsă, fișă exportabilă |
| **P5 — interfață și experiența demo-ului** | Cele trei ecrane, selecția pe hartă, filtre, stări fără date și prezentare vizuală. Nu face slide-urile | H+3: navigare cap-coadă pe fixture-uri | Interfață pe date reale, clară la proiector, funcțională cu snapshot local |
| **P6 — produs, verificare manuală și pitch** | Selectează surse, revizuiește duplicatele/datele/pinii, testează dosarele; validează problema cu un mentor; pregătește pitch-ul | H+3: o selecție inițială de surse și 3 scenarii de demo | Registrul verificărilor, prezentare de 3 minute, Q&A și video de rezervă |

P1 este colegul care poate integra cel mai repede munca celorlalți. P5 este cel mai bun pe interfață. P6 trebuie să înțeleagă produsul și datele suficient de bine încât să poată respinge o afirmație nesusținută. Numele se completează la început; nu presupunem că proprietarul repo-ului are automat un anumit rol.

P6 și P2 formează o pereche pe surse; P6 și P3 pe cazurile geografice ambigue. P4 și P5 pot lucra imediat pe contracte și fixture-uri. P1 începe integrarea în primele ore și rezervă cel puțin jumătate din timpul activ pentru aceasta.

## 3. Stack și delimitarea fișierelor

**Dacă repo-ul are deja o aplicație funcțională, o păstrați.** Dacă porniți de la zero și nu aveți un specialist frontend care livrează rapid, recomand Python + Streamlit + pydeck, cu modele validate și fișiere JSON/GeoJSON locale. Streamlit oferă integrare pydeck și selecție de obiecte pe hartă [S5].

Nu sunt necesare microservicii sau o bază de date nouă pentru acest demo. Dacă există deja React/MapLibre, P1 asigură un adaptor API sau fișiere statice conforme cu aceleași contracte. Decizia de stack se închide în primele 30 de minute.

| Cale propusă | Proprietar | Conținut |
|---|---|---|
| `contracts/` | P1 | Schema v1, modele, fixture-uri și reguli semantice |
| `src/ingestion/` | P2 | Import, extracție, cache și proveniență |
| `src/geo/` | P3 | Localizare, context, limite administrative, H3 |
| `src/analysis/` | P4 | Scor, catalog de măsuri, explicații și export |
| `src/ui/` | P5 | Ecrane și componente de interfață |
| `src/pipeline/`, `tests/integration/` | P1 | Orchestrare, validare și verificarea integrării |
| `data/raw/` | P2 | Intrări locale; texte integrale numai unde utilizarea și redistribuirea sunt permise |
| `data/curated/`, `docs/validation/` | P6 | Evidențe aprobate și registrul verificărilor; P3 produce modificările geometrice pentru revizuire |
| `data/demo/` | P1 | Snapshot generat și etichetat, nu editat manual de fiecare modul |
| `docs/pitch/`, `docs/demo/` | P6 | Scenariu, prezentare, întrebări și rezervă |

Fișierele comune și lockfile-ul au un singur editor principal: P1. Autorul unui modul scrie verificările pentru acel modul; P1 deține integrarea. Schimbările de schemă se anunță înainte de implementare.

## 4. Contractul v1 care se fixează în prima oră

Cele două exporturi principale pentru interfață rămân `accidents.geojson` și `hotspots.geojson`. Se adaugă `articles.jsonl` pentru proveniență și `context.geojson` pentru infrastructură. Un `manifest.json` declară versiunea, intervalul de timp, municipiul și modul datelor.

### Convenții comune

- GeoJSON folosește WGS84 și coordonate în ordinea **[longitudine, latitudine]**. Orice adaptor de API care cere ordinea inversă o convertește explicit.
- `schema_version: "1.0"`, `dataset_id`, `generated_at`, `data_mode: "synthetic" | "observed"` sunt în manifest. O versiune de demo folosește un singur mod; nu combină în tăcere cele două seturi.
- `null` înseamnă necunoscut. Nu înlocuiți un tag OSM lipsă cu `false` și nici o limită de viteză lipsă cu o valoare prezentată drept observată.
- Data publicării, data accidentului, data colectării și data verificării sunt câmpuri separate. Orele exacte au fus orar Europe/Bucharest/offset explicit. Dacă știm numai ziua, nu fabricăm ora 00:00.
- Există un ID stabil pentru articol și alt ID pentru eveniment. Mai multe articole despre același accident se leagă de același `event_id`.
- Identitatea persoanelor implicate nu este necesară pentru prioritizarea locațiilor; păstrăm datele despre eveniment.

### `articles.jsonl` — intrarea P2

| Câmp | Semnificație |
|---|---|
| `article_id`, `url`, `publisher`, `title` | Identificarea sursei |
| `published_at`, `retrieved_at` | Publicare și colectare |
| `content_hash`, `text_ref` | Deduplicare de conținut și referință locală la text, când poate fi păstrat |
| `extraction_run_id`, `model`, `prompt_version` | Trasabilitatea extragerii |
| `evidence` | Referințe la pasaje scurte care susțin câmpurile extrase |

### `accidents.geojson` — ieșirea P2 + P3, revizuită de P6

Un `Feature` reprezintă un **eveniment rutier unic**, nu un articol și nu o victimă. Geometria este `Point` sau `null` când localizarea nu este suficientă.

| Câmp în `properties` | Valori/rol |
|---|---|
| `event_id`, `source_article_ids` | Eveniment unic și toate sursele asociate |
| `event_date`, `event_time`, `date_precision` | Dată/oră posibil nule; precizia este explicită |
| `municipality`, `municipality_status` | Confirmat în municipiu, în afara lui sau neclar |
| `location_text`, `road_segment_id` | Formularea sursei și segmentul asociat, dacă există |
| `geocode_method`, `location_precision`, `uncertainty_m` | Metodă; precizie de tip intersecție/segment/stradă/localitate; incertitudine numerică doar dacă justificată |
| `participants` | Listă de categorii: pieton, biciclist, autoturism etc.; independentă de cauză |
| `reported_causes` | Cauze descrise de sursă, cu referință și statutul afirmației; nu verdict al aplicației |
| `severity` | `fatal`, `serious_injury`, `minor_injury`, `injury_unspecified`, `property_damage`, `unknown` |
| `conditions` | `night`, `rain` etc. cu valori `true`, `false` sau `null`, fiecare susținută când este cunoscută |
| `review_status`, `reviewed_by`, `reviewed_at` | `pending`, `approved` sau `rejected`; câmpurile de review se păstrează |
| `duplicate_of` | ID canonic dacă înregistrarea a fost identificată ca duplicat |
| `evidence` | Proveniență per câmp și conflicte între surse |

Decesul după publicarea inițială actualizează același eveniment și păstrează istoricul. Dacă locația este doar „pe strada X”, nu punem arbitrar un pin în mijlocul străzii pentru a calcula un hotspot.

### `context.geojson` — ieșirea P3

Conține geometria obiectului, `feature_id`, `feature_type`, `source_url`, `source_feature_id`, `retrieved_at`, `attributes` și statutul verificării. `lit`, `maxspeed`, trecerile și semafoarele pot fi necunoscute. „Nu apare în extract” nu este echivalent cu „nu există”.

### `hotspots.geojson` — ieșirea P4

Un `Feature` este un poligon H3; proprietățile conțin:

- `hotspot_id`, `h3_index`, `h3_resolution`, `dataset_id`, perioada de analiză;
- `event_ids`, `event_count`, `severity_counts`, `unresolved_count`;
- `priority_score`, `score_version`, `score_components`;
- `context_refs`, `data_gaps`, `review_status`;
- `recommendations`: `measure_id`, motiv, `evidence_refs`, `applicability`, `missing_checks`, sursă, eventual cost și CMF documentate;
- `cost_ron_min/max`, `cost_basis`, `cmf`, `cmf_source` rămân nule dacă nu există dovezi utilizabile.

Un hexagon poate include mai multe străzi fără legătură funcțională. Recomandarea se leagă de o locație/segment concret din celulă; nu prescriem aceeași măsură întregului hexagon.

### Interfețe logice

`extract_article(article) -> candidates`

`resolve_location(candidate, local_context) -> located_candidate`

`review_event(candidate, decision) -> reviewed_event`

`build_hotspots(approved_events, context, config) -> hotspot_collection`

`recommend(hotspot, catalog) -> recommendations`

`export_location_brief(hotspot, evidence) -> downloadable_brief`

Fișierele și funcțiile sunt sursa comună de adevăr. Interfața nu recalculează scorul separat.

## 5. Metoda de prioritizare și limitele ei

**Scorul este o regulă demonstrativă de prioritizare în eșantion; nu este o probabilitate de accident.** Nu antrenăm în grabă un model predictiv pe câteva zeci de articole.

O variantă v1 simplă și auditabilă, de fixat înainte de a vedea clasamentul, este:

`priority_score = event_count + 4 × fatal_event_count + 2 × serious_injury_event_count + pedestrian_event_count`

Numărăm evenimente, nu persoane. `fatal` și `serious_injury` sunt categorii exclusive la nivelul unui eveniment; o interacțiune cu pieton poate primi bonus separat. Ponderile sunt alese de echipă pentru demo, nu validate empiric. Cazurile cu gravitate necunoscută rămân în numărul de evenimente și sunt raportate separat. Nu schimbați ponderile pentru a forța apariția unei străzi cunoscute în top.

Intră în agregarea spațială numai evenimente unice, aprobate, din municipiu, în intervalul declarat, cu localizare suficientă pentru celula aleasă. Cazurile neclare apar în coada de verificare și în indicatorii de completitudine. Dacă există doar 7 celule populate, afișați 7, nu inventați un „Top 20”.

**H3 rezoluția 9** este o alegere utilă pentru o primă agregare de zonă. Tabelul curent H3 indică o suprafață medie de aproximativ 0,105 km²; o celulă nu reprezintă automat o intersecție. Dimensiunile variază geografic [S2]. Verificați locațiile aflate lângă margini și păstrați punctele originale vizibile. Nu promiteți precizie la nivel de trecere dintr-o geocodare la nivel de stradă.

### Recomandări verificabile

| Dovezi disponibile | Ieșire rezonabilă | Ce trebuie verificat înaintea unei intervenții |
|---|---|---|
| Evenimente nocturne cu pietoni | Verificarea iluminatului și vizibilității; eventual proiect de îmbunătățire | Iluminat existent, măsurători, poziția trecerii și context local |
| Traversare pietonală pe un drum lat | Analiza unei soluții de refugiu/protecție a traversării | Lățime, trafic, accesibilitate, spațiu și fluxuri |
| Școală apropiată și traversări documentate | Verificarea traseelor școlare și a vitezelor locale | Intrări, flux pietonal, program, configurație și limite confirmate |
| Conflicte de prioritate descrise repetat | Verificarea vizibilității și organizării intersecției | Tipul conflictului, geometrie, trafic, semnalizare existentă |
| Informații esențiale lipsă | Solicitare de observație în teren/date | Lista explicită a câmpurilor lipsă |

O cauză relatată în presă nu conduce automat la recomandarea unui giratoriu sau semafor. AI poate explica dovezile, dar nu completează datele lipsă cu presupuneri.

### Ce corectăm față de planul inițial

- **Viteze:** TomTom definește `currentSpeed` ca viteză medie curentă, iar `freeFlowSpeed` ca viteză așteptată în condiții ideale. Interpretarea noastră: a doua nu dovedește că vehiculele depășesc acum limita legală. Nici media nu este o măsurare individuală [S3]. Dacă integrarea este disponibilă, arătăm segmentul, unitatea, momentul și încrederea; nu interogăm orbește centrul hexagonului.
- **CMF:** o schimbare estimată a frecvenței accidentelor cere un număr de bază adecvat și un factor aplicabil contextului. Nu aplicăm un CMF unui scor arbitrar și nu extrapolăm accidente anuale dintr-un eșantion de presă. Factorii multipli pot supraestima beneficiul dacă efectele se suprapun [S4].
- **Scenariu:** dacă păstrați un panou „ce s-ar schimba”, separați-l de harta observațiilor; arătați ipotezele și măsura selectată. Pentru MVP, recomand o listă de verificări și costuri documentate, fără un contor de vieți salvate.
- **Acoperire:** presa este o sursă selectivă. Separăm numărul articolelor, numărul accidentelor unice, numărul localizărilor confirmate și evenimentele excluse. Absența din set nu demonstrează că o zonă este sigură.

## 6. Calendarul de 25 de ore

H0 este ora la care echipa începe acest plan. Dacă folosiți orientativ 17 octombrie, 13:30, H+25 este 18 octombrie, 14:30. Programul public indică predarea duminică, 16:30–17:00, și pitch de 3 minute [S1]. Păstrați acea diferență drept rezervă și verificați eventualele actualizări ale organizatorilor.

| Moment | Rezultat comun | Decizie dacă nu este gata |
|---|---|---|
| **H0–H+1** | Roluri, stack, schema v1, 5 fixture-uri sintetice și lista primelor surse; încercare LLM reală | Păstrăm cel mai simplu stack deja cunoscut; rezolvăm accesul runtime înainte de a conta pe el |
| **H+3** | Primul flux complet pe fixture-uri; modul sintetic este etichetat; cel puțin câteva surse reale procesate | P1+P5 prioritizează integrarea; P6 ajută P2 cu surse curate |
| **H+6** | Minimum 10 evenimente reale revizuite și primul dosar de locație | Reducem aria și numărul de surse; completare manuală asistată, fără extinderea scraperului |
| **H+10** | Ținta 20–40 de evenimente, prioritizare, recomandări și 3 dosare de prezentare | Fixăm setul verificat disponibil; scoatem orice dependență opțională |
| **H+12** | Înghețarea funcționalităților, snapshot local și prima repetiție | De aici se repară erori; nu se mai adaugă servicii, grafice sau modele noi |
| **H+12–H+18** | Fereastră de odihnă, aproximativ 6 ore | Nu se bazează nicio integrare critică pe muncă nesupravegheată peste noapte |
| **H+18–H+20** | Rulare din mediu curat, verificări, retestarea celor 3 dosare | P1 și proprietarul modulului repară problema; ceilalți finalizează prezentarea |
| **H+20–H+23** | Două repetiții cronometrate, video de rezervă, artefactele de predare | Fără schimbări de design ample; corectăm doar ce afectează demonstrația |
| **H+23–H+25** | Pachet final, checksum/snapshot, versiune identificabilă și livrabile pregătite | Folosim rezerva numai pentru blocaje reale |

Integrare la fiecare 60–90 de minute în orele active. Stand-up de 5 minute: ce rulează, ce interfață s-a schimbat, ce mă blochează. P1 decide ce intră în versiunea comună. După închiderea spațiului fizic, planificați numai munca pe care o puteți face dintr-un loc disponibil.

## 7. Backlog pregătit pentru issues

Acestea sunt sarcini propuse, nu issues publicate. Coloane recomandate: Backlog, În lucru, Review, Done. Maximum o sarcină principală activă pe persoană. Fiecare issue include proprietar, intrare/ieșire și criteriul de acceptare.

| ID / prioritate | Proprietar | Sarcină | Criteriu de acceptare |
|---|---|---|---|
| 01 / P0 | P1 | Contracte v1 și fixture-uri | Toate exemplele validează; convențiile geografice și datele necunoscute sunt explicite |
| 02 / P0 | P1 | Aplicație rulabilă și pipeline | Un coleg pornește aplicația din instrucțiuni; nu există dependență de fișiere personale |
| 03 / P0 | P6 | Surse și tabel de verificare | Listă de URL-uri, relevanță, statut și primele cazuri revizuite |
| 04 / P0 | P2 | Import și extragere structurată | Un articol produce candidați validați, cu dovezi; eroarea de model nu strică setul existent |
| 05 / P0 | P3 | Localizare și delimitare Iași | Pinii aprobați au justificare; cazurile ambigue și cele din afara municipiului sunt separate |
| 06 / P0 | P6 + P2 | Deduplicare și adjudecare | Două articole despre același eveniment nu cresc numărul accidentelor |
| 07 / P0 | P3 | Context OSM și H3 | Sursă, dată și necunoscute păstrate; punctele și poligoanele sunt coerente |
| 08 / P0 | P4 | Prioritizare transparentă | Scor reproductibil; componente afișabile; numerele din tabel coincid cu harta |
| 09 / P0 | P4 | Catalog și fișa locației | 5 măsuri candidate cu surse/condiții; un dosar poate fi exportat |
| 10 / P0 | P5 | Hartă și dosar | Selectarea unei locații arată evenimentele și dovezile corecte |
| 11 / P0 | P5 + P2 | Ecran de import/review | Rezultatele AI pot fi corectate și aprobate înainte de publicare |
| 12 / P0 | P1 | Integrare și rezervă locală | Demo pe laptopul final, cu fallback verificat când internetul lipsește |
| 13 / P0 | P6 | Pitch și verificarea mesajelor | 3 minute, date reale în slide-uri, video funcțional și Q&A |
| 14 / P1 | P3 | Context de trafic TomTom | Numai după P0, acces disponibil, segment/unitate/moment/încredere afișate |
| 15 / P2 | P2 sau coleg disponibil | Exemplu video SafeCross | Numai cu P0 stabil, clip utilizabil și ieșire verificată; etichetă „analiză înregistrată” |

Recomand ca P1 să deschidă o ramură pentru documentație și contracte după citirea instrucțiunilor din repo. Nu trimiteți modificări direct pe branch-ul principal ca să recuperați timpul.

## 8. Verificări care merită timpul

1. Același accident descris în două articole este numărat o singură dată; sursele rămân accesibile.
2. Data publicării nu devine automat data accidentului; ora necunoscută rămâne necunoscută.
3. Latitudinea/longitudinea inversate, un punct în altă localitate și o geocodare vagă sunt detectate înainte de agregare.
4. Un tag de iluminat absent nu produce recomandarea „instalați iluminat” ca și cum lipsa ar fi confirmată.
5. Punctele, celulele H3, tabelul și exportul raportează aceleași ID-uri și aceleași totaluri.
6. Datele sintetice nu intră în versiunea observată; un rezultat AI salvat este etichetat drept reluare, nu răspuns live.
7. O extragere invalidă sau un timeout lasă aplicația într-o stare clară, fără pierderea datelor aprobate.
8. Cele trei dosare de prezentare sunt confruntate manual cu sursele. Se notează corecțiile, nu doar „testat OK”.

Pentru evaluarea extracției, P6 pregătește un mic set separat, de 10–15 cazuri, cu rezultate de referință. Raportați corectitudinea pe câmpuri cu numărător și numitor; nu inventați „95% accuracy”. Cazurile văzute la ajustarea promptului nu se prezintă drept evaluare independentă.

Pentru fallback, salvați datele necesare și un strat de drumuri local. O hartă cu fișiere locale poate încă depinde de tile-uri online: verificați explicit pornirea cu internetul oprit. pydeck poate omite basemap-ul prin `map_provider=None`; testați în versiunea instalată [S5]. Păstrați și un video MP4 de rezervă.

## 9. Folosirea agenților de coding

Folosiți agenții și abonamentele pe care le aveți deja. P1–P5 pot avea câte un agent care scrie în aria proprie; P6 folosește unul pentru structurarea documentației și verificări, fără ca acesta să înlocuiască revizuirea surselor. Un singur agent scrie într-un branch/worktree la un moment dat. Nu este nevoie să alegeți aceeași marcă de agent pentru toți.

Testați separat accesul modelului folosit efectiv în aplicație: cheie, cotă, răspuns structurat și salvarea rezultatului. Accesul la un agent care vă scrie codul nu demonstrează că runtime-ul aplicației este configurat.

### Instrucțiunea comună pentru fiecare agent

> Lucrezi la SafeIași, un demo de 25 de ore pentru prioritizarea locațiilor de verificat de administrație. Citește mai întâi instrucțiunile repository-ului, contractul v1 și sarcina ta. Păstrează structura funcțională existentă. Modifică doar directoarele asignate; propune separat orice schimbare de schemă sau dependențe comune. Nu inventa accidente, coordonate, surse, costuri sau efecte asupra siguranței. Necunoscut rămâne null. Nu număra articolele drept accidente. Folosește fixture-urile pentru dezvoltare și păstrează modul sintetic separat. Livrează o schimbare mică, rulabilă, cu verificări pentru riscurile reale. La final precizează fișierele schimbate, cum se rulează, ce ai verificat și ce rămâne nesigur.

### Sarcina P1

> Definește contractele v1 și fixture-urile, apoi un pipeline minimal care leagă importul, localizarea, analiza și UI. Asigură instrucțiuni de pornire, validare înainte de publicarea snapshot-ului și verificarea integrării pe laptopul final. Tu deții dependențele comune. Păstrează demo-ul rulabil la fiecare integrare. Nu implementa funcționalitățile celorlalte module în locul colegilor.

### Sarcina P2

> Implementează importul unei liste mici de surse și extracția structurată din text. Separă participanții, cauza relatată și gravitatea. Fiecare câmp important trebuie să aibă dovadă și sursă; nu deduce coordonate cu LLM-ul. Distinge publicarea de momentul accidentului. Salvează modelul, versiunea promptului și răspunsul pentru reproducere. Livrează un exemplu real de extracție, tratarea JSON invalid și timeout, plus coada de candidați pentru review.

### Sarcina P3

> Construiește localizarea asistată și contextul OSM, limitate la municipiul Iași. Folosește un extract local și un mic dicționar de locații revizuite pentru a reduce dependențele externe. Pentru intersecții, verifică nodul comun și nivelul drumurilor; o suprapunere în plan poate fi pasaj. Lasă cazurile vagi pentru review. Produce punctele, contextul cu proveniență și celulele H3 conforme contractului. TomTom este opțional și nu intră în logica de depășire a vitezei.

### Sarcina P4

> Construiește prioritizarea deterministă pe evenimente unice aprobate. Afișează componentele scorului și limitele eșantionului. Construiește catalogul de măsuri candidate cu sursă, aplicabilitate și verificări lipsă. Nu aplica CMF scorului și nu calcula accidente anuale evitate din presă. Produce hotspots.geojson și o fișă exportabilă. Verifică duplicatele, necunoscutele și coerența totalurilor.

### Sarcina P5

> Construiește cele trei ecrane pe fixture-uri: hartă, dosar, import/review. Folosește doar rezultatele contractului pentru scor. Fă vizibile sursele, perioada, datele lipsă și modul sintetic/observat. Livrează întâi un flux complet și lizibil, apoi polish. Gestionează lipsa datelor și indisponibilitatea hărții de bază. Nu modifica schema fără acordul P1. Pregătește selecția celor trei dosare pentru demo.

### Sarcina P6

> Construiește registrul verificărilor și scenariul de prezentare. Selectează surse relevante, verifică duplicatele, data, localizarea și gravitatea. Pregătește cazuri de evaluare cu rezultate de referință. Verifică dacă măsurile afișate sunt susținute sau necesită observații suplimentare. Scrie un pitch de 3 minute pentru Primărie: problema, demonstrația, rolul AI, limitele și propunerea de pilot. Nu inventa validări de client, cifre de impact sau costuri. Pregătește Q&A și filmarea de rezervă.

## 10. Demo, client și pasul comercial

Scenariu de prezentare, total 180 de secunde:

| Interval | Ce arătați |
|---|---|
| 0–20 sec | Întrebarea administrației: unde verificăm și pe ce dovezi? |
| 20–60 sec | O sursă este transformată în informație structurată; operatorul vede și aprobă câmpurile |
| 60–105 sec | Locația pe hartă, evenimente unice, surse și explicația priorității |
| 105–140 sec | Măsuri candidate, condiții lipsă și fișa exportată |
| 140–165 sec | Limitele eșantionului și ce date ar aduce un pilot |
| 165–180 sec | Cererea concretă: responsabil din administrație, date și 3–5 locații de test |

Juriul din 18 octombrie punctează AI-ul cu 30%, impactul cu 25%, funcționalitatea demo-ului cu 25% și pitch-ul cu 20% [S1]. Aceasta justifică responsabilitatea dedicată pentru prezentare și afișarea explicită a rolului AI.

**Propunere comercială de validat:** pilot de 60–90 de zile, cu locații delimitate și criterii de acceptare; ulterior implementare și abonament de actualizare/suport. Nu stabiliți prețul exclusiv în funcție de un prag de achiziție. Nu pretindeți că aveți acordul Primăriei dacă nu a fost obținut.

Indicatori potriviți pilotului: timp pe dosar, corectitudinea câmpurilor extrase pe eșantion verificat, proporția locațiilor rezolvate, duplicate eliminate, utilitatea dosarelor pentru utilizatori. Reducerea accidentelor necesită o evaluare ulterioară, distinctă de validarea demo-ului.

SafeCross poate deveni modulul care adaugă observații video la dosarele selectate, după verificarea dreptului de utilizare a filmărilor, a perspectivei și a semnalărilor. Această extensie nu este necesară pentru a demonstra acum produsul principal.

## 11. Surse tehnice și de organizare

Surse consultate la 17 octombrie 2026. Deciziile de scope, roluri, ținte și ponderi din document sunt recomandările acestui plan.

- **[S1] Program și criterii hackathon:** https://markaiintegrator.ro/hackathon-ai/
- **[S2] H3 — statistici pe rezoluții:** https://h3geo.org/docs/core-library/restable/
- **[S3] TomTom — definiția câmpurilor Traffic Flow:** https://docs.tomtom.com/traffic-api/documentation/tomtom-maps/v1/traffic-flow/flow-segment-data
- **[S4] CMF — definiții și aplicare:** https://cmfclearinghouse.fhwa.dot.gov/userguide_CMF.php ; https://cmfclearinghouse.fhwa.dot.gov/faqs.php ; https://cmfclearinghouse.fhwa.dot.gov/collateral/combining_multiple_cmfs_final.pdf
- **[S5] Streamlit — pydeck și basemap:** https://docs.streamlit.io/develop/api-reference/charts/st.pydeck_chart

**Geocodarea recomandată pentru demo este bazată pe extract local și verificare manuală.** Dacă echipa alege deliberat serviciul public Nominatim, trebuie să respecte [politica oficială](https://operations.osmfoundation.org/policies/nominatim/): maximum 1 cerere/secundă în total, identificarea aplicației, cache și atribuire; pentru mici importuri unice, un singur fir pe o singură mașină. Sarcinile periodice sau care durează peste o zi sunt limitate la 4 cereri/minut. Serviciul public nu este potrivit pentru importuri masive, autocomplete sau inventarierea sistematică a punctelor de interes. Nu îl includeți automat ca serviciu generic de geocodare; folosiți un furnizor potrivit sau propria instanță dacă nevoia crește [S6].

- **[S6] Politica serviciului public Nominatim:** https://operations.osmfoundation.org/policies/nominatim/
