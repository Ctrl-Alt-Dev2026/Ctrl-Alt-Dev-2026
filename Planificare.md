# Harta pietonului – Iași · Plan v2
**Unde sunt pietonii în pericol, pe ce dovezi și ce ar trebui verificat sau schimbat**

> Hackathon AI Iași 2026 · 6 oameni · final duminică 18 oct, 17:00 · predarea livrabilelor 16:30–17:00 · pitch 3 min + 1–3 min întrebări
> v2 = planul inițial + corecturile colegului + programul oficial al hackathonului

---

## 0. Pe scurt

- Construim o **hartă 3D a Iașiului** cu accidentele cu pietoni raportate în presă (BZI, Știri Iași), extrase automat cu AI.
- Locațiile cu risc sunt clasate după un **scor transparent**, iar pentru fiecare propunem **măsuri candidate**: ce recomandăm, de ce, cât costă, ce trebuie verificat în teren.
- **Rolul AI e vizibil live:** lipim un articol nou, AI-ul extrage datele și arată în text de unde le-a luat, omul aprobă, iar punctul apare pe hartă.
- **Suntem onești cu datele:** presa e un eșantion, nu toate accidentele. Scorul e o prioritizare, nu o probabilitate. Recomandările sunt de verificat, nu decizii.

**Criteriile juriului de duminică:** inovație și relevanța utilizării AI 30%, impact 25%, fezabilitate și demo 25%, pitch 20%.
**Atenție:** la Demo Day (13 noiembrie) jurizează administrația publică din Iași. Orice cifră pe care o arătăm azi trebuie să o putem susține și atunci.

---

## 1. Produsul: 3 ecrane și un export

### Ecranul 1 – Harta priorităților
- Hartă întunecată, camera înclinată la ~45°, clădiri 3D dacă stilul hărții le are.
- **Coloane hexagonale 3D** (H3) pentru densitatea accidentelor: înălțimea și culoarea (galben → roșu) arată intensitatea. Hexagoanele sunt doar vizualizare.
- **Top 10 locații concrete** (intersecții sau treceri), marcate cu cercuri care pulsează. Clasamentul se face pe locații, nu pe hexagoane.
- Titlu onest: „Accidente cu pietoni raportate în presă, [perioada]”, plus numărul de articole, evenimente unice și evenimente localizate precis.
- **Turul cinematic „Top 10”**: camera zboară pe rând la fiecare locație (`map.flyTo` cu rotație și înclinare), iar fișa intră din lateral.
- **Butonul „Aplică măsurile”**: coloanele din zonele vizate coboară animat, iar un contor afișează:
  `Locații vizate: 10 · Accidente documentate acolo: N · Cost estimat: X–Y lei`
  **Nu** afișăm „accidente evitate pe an” și nici „vieți salvate”.

### Ecranul 2 – Fișa locației
- Numele locației, scorul și **din ce e compus scorul**.
- Evenimentele unice, fiecare cu sursele ei (link-uri), data și gravitatea.
- Graficul pe 24 de ore (de exemplu: accidentele se adună seara).
- Infrastructura: ce știm și ce **nu știm** (necunoscutul se afișează ca atare).
- 1–3 măsuri candidate, fiecare cu: motivul, costul estimat (cu sursă), reducerea tipică raportată în literatură (cu sursă CMF, ca informație, nu ca predicție) și **ce trebuie verificat în teren**.
- Poză de la nivelul străzii din Mapillary (opțional).

### Ecranul 3 – Import și verificare (piesa centrală pentru AI)
1. Lipim link-ul sau textul unui articol.
2. AI-ul extrage câmpurile, iar în text se evidențiază pasajele care le susțin.
3. Omul corectează și aprobă.
4. Evenimentul apare pe hartă și scorul locației se actualizează.

### Exportul – Fișa de verificare pentru primărie (PDF)
Top 10 locații, dovezile, măsurile candidate, verificările necesare și limitele datelor. **Nu e un audit certificat**, ci o listă de priorități de verificat.

---

## 2. Date și limite

| Sursă | Ce ne dă | Note |
|---|---|---|
| BZI, Știri Iași | Accidentele: locul, data, ora, cauza raportată, gravitatea | Scraping + extracție cu LLM |
| OpenStreetMap (OSM) | Treceri, semafoare, iluminat, școli, stații, tipul străzii, numărul de benzi | Gratuit, prin `osmnx`. Lipsa unui tag ≠ lipsa obiectului |
| Nominatim (OSM) | Numele străzilor transformate în coordonate | Maxim 1 cerere/secundă, cache obligatoriu, identificarea aplicației (vezi politica oficială) |
| CMF Clearinghouse (FHWA) | Reducerea tipică raportată pentru fiecare măsură | Doar informativ în fișă |
| SEAP, știri | Costuri în lei | Fiecare cost are sursă |
| TomTom Traffic Flow | Viteza medie curentă și viteza în condiții ideale | **Opțional, prioritate mică.** Nu dovedește depășirea limitei |

**Limitele pe care le spunem deschis:**
- Presa scrie selectiv, mai ales despre accidentele grave sau spectaculoase. Absența din date ≠ zonă sigură.
- Scorul e o regulă de prioritizare pe acest eșantion, nu o probabilitate de accident.
- Recomandările sunt candidate; decizia aparține Comisiei de circulație.
- În versiunea reală, datele vin de la primărie și poliție, din Centrul de Management al Traficului și din Waze for Cities.

**Ce numărăm separat:** articole colectate · evenimente unice · evenimente localizate precis · evenimente verificate manual · evenimente excluse.

---

## 3. Stack

- **Date:** Python (`requests`, `beautifulsoup4`, `osmnx`, `geopandas`, `h3`) + un API de LLM. Organizatorii oferă la cerere acces la o platformă AI plătită: cereți-l pe Discord, în #suport-tehnic.
- **Frontend:** o pagină HTML cu **MapLibre GL + deck.gl**, care citește JSON-urile din `data/`.
  Varianta de rezervă, dacă nimeni nu e confortabil cu JS: Streamlit + pydeck (merge și cu coloane 3D, dar turul cinematic e mai greu).
- **Backend minimal:** un singur endpoint Python (FastAPI) `POST /extract`, folosit doar de ecranul de import. Cheia API stă pe server, nu în pagină.
- **Link-ul public de demo:** pagina statică pe GitHub Pages sau Netlify. Pe link-ul public, ecranul de import rulează în **modul reluare**, cu 2–3 extracții salvate dinainte și etichetate ca atare. Extracția live o arătăm de pe laptop.
- **Fără bază de date.** Totul circulă prin fișiere JSON.

**Structura repo-ului:**
```
/scraping     A    /extraction  B    /geocoding   C
/context      D    /risk        E    /measures    F
/web          G    /api         B (endpoint-ul /extract)
/data         fișierele contract     run_all.py   H
```
**Regula pentru Git:** fiecare lucrează în folderul lui, pe branch-ul lui. Fișierele comune (`requirements.txt`, `data/manifest.json`) au un singur editor: omul 1.

---

## 4. Contractul dintre arii

Ariile comunică **doar prin aceste fișiere**. Fiecare fișier are un singur proprietar, iar ceilalți doar îl citesc. Până apar datele reale, toată lumea lucrează pe versiunile false.

| Fișier | Proprietar | Folosit de |
|---|---|---|
| `data/manifest.json` | H | toți |
| `data/articles.json` | A | B |
| `data/accidents.json` | B (câmpurile de conținut) + C (localizarea) | E, G |
| `data/crossings.geojson` | D | E, G |
| `data/hotspots.json` | E | F, G |
| `data/measures.json` | F | E, G |

### Convenții
- `null` = necunoscut. Nu transformăm „nu știm” în `false`.
- Data accidentului ≠ data publicării. Dacă știm doar ziua, ora rămâne `null`.
- GeoJSON și deck.gl folosesc coordonatele în ordinea **[longitudine, latitudine]**.
- **Un eveniment = un accident**, nu un articol. Mai multe articole despre același accident se leagă de același `event_id`.
- Nu păstrăm numele persoanelor implicate; nu ne trebuie.
- `manifest.json` spune dacă datele sunt `synthetic` sau `observed`. Nu amestecăm niciodată cele două tipuri.

### `manifest.json`
```json
{"schema_version": "2.0", "data_mode": "observed", "perioada": ["2024-10-01", "2026-10-17"],
 "generat_la": "2026-10-17T20:00:00+03:00", "nr_articole": 0, "nr_evenimente": 0,
 "nr_localizate_precis": 0, "nr_verificate": 0}
```

### `articles.json`
```json
[{"article_id": "bzi-1023", "sursa": "BZI", "url": "https://...", "titlu": "...",
  "text": "...", "publicat_la": "2025-03-13", "colectat_la": "2026-10-17"}]
```

### `accidents.json`
```json
[{"event_id": "ev-001", "article_ids": ["bzi-1023", "si-554"], "urls": ["https://..."],
  "data_eveniment": "2025-03-12", "ora": "21:30",
  "loc_text": "intersecția Păcurari cu Moara de Vânt",
  "precizie_loc": "intersectie", "lat": 47.170, "lon": 27.550, "in_iasi": true,
  "participanti": ["pieton", "autoturism"], "cauza_raportata": "viteza",
  "gravitate": "grav", "noapte": true,
  "dovezi": {"loc_text": "...pasaj scurt din articol...", "gravitate": "..."},
  "verificat": false}]
```
- `precizie_loc`: `trecere` | `intersectie` | `segment` | `strada` | `vag`. Pentru `vag`, `lat` și `lon` sunt `null`.
- `gravitate`: `deces` | `grav` | `usor` | `necunoscut`.
- `cauza_raportata`: ce spune presa (`viteza`, `neacordare_prioritate`, `traversare_neregulamentara`, `vizibilitate`) sau `null`. **E cauza relatată, nu verdictul nostru.**
- `noapte`: `true` | `false` | `null`.
- `dovezi`: scurte pasaje care susțin câmpurile, folosite în ecranul 3 și în fișă. Obligatoriu pentru loc și gravitate, opțional pentru restul.

### `crossings.geojson` (proprietățile fiecărei treceri sau intersecții)
```json
{"id": "x-551", "tip": "trecere", "nume": "Păcurari × Moara de Vânt",
 "semafor": false, "benzi": 4, "iluminat": null, "tip_strada": "bulevard",
 "scoala_150m": true, "statie_100m": true, "sursa": "OSM", "descarcat_la": "2026-10-17"}
```

### `hotspots.json`
```json
[{"id": "h-1", "crossing_id": "x-551", "nume": "Păcurari × Moara de Vânt",
  "lat": 47.170, "lon": 27.550, "h3": "891e...",
  "scor": 14, "componente_scor": {"evenimente": 5, "deces": 4, "grav": 2, "context": 3},
  "event_ids": ["ev-001", "ev-007"], "nr_evenimente": 5, "pe_ore": [0, 0, "... 24 de valori"],
  "explicatie": "5 pietoni loviți, 3 noaptea; 4 benzi fără semafor; școală la 80 m",
  "date_lipsa": ["iluminat necunoscut"],
  "masuri": [{"measure_id": "semafor_pietonal", "motiv": "...", "de_verificat": ["..."]}],
  "verificat": true}]
```

### `measures.json`
```json
[{"id": "iluminat_trecere", "nume": "Iluminat dedicat trecerii",
  "conditie": "evenimente noaptea >= 2",
  "cost_lei_min": null, "cost_lei_max": null, "sursa_cost": null,
  "reducere_tipica": null, "sursa_reducere": null,
  "de_verificat": ["iluminatul existent", "poziția stâlpilor", "vizibilitatea din ambele sensuri"]}]
```
Costurile și reducerile rămân `null` până găsim o sursă. **Nu inventăm cifre.**

---

## 5. Scorul de prioritizare

Regula se fixează **înainte** de a vedea clasamentul și nu se modifică ca să iasă în top o stradă anume.

```
scor = Σ peste evenimente (1 + 4 dacă deces + 2 dacă grav)
     + 2 dacă trecere fără semafor pe 4+ benzi
     + 1 dacă e o școală la mai puțin de 150 m
     + 1 dacă e o stație la mai puțin de 100 m
```

- Ponderile sunt alese de echipă pentru demo, nu validate științific, și spunem asta.
- Contextul se adună **numai când e cunoscut**. Un `null` nu adaugă și nu scade puncte; apare în `date_lipsa`.
- În scor intră doar evenimentele unice din municipiul Iași, cu `precizie_loc` = `trecere`, `intersectie` sau `segment`. Celelalte apar pe hartă ca „localizate aproximativ”, dar nu intră în clasament.
- Dacă avem mai puțin de 10 locații cu cel puțin 2 evenimente, afișăm câte avem, nu un „Top 10” umplut artificial.

---

## 6. Ariile și taskurile

Toate taskurile pot începe **imediat**, pe date false. Cele marcate cu ⏳ au nevoie de datele reale.

### A. Scraping
- **A1.** Scraper BZI: căutări după „pieton”, „lovit”, „accident”, „trecere”, pe ultimii 2 ani.
- **A2.** Scraper Știri Iași, cu aceeași logică.
- **A3.** Filtru de relevanță: doar accidente reale din municipiul Iași, fără cele din județ și fără știrile generale.
- **A4.** Cache local și pauze între request-uri.
- **Țintă:** 150+ articole relevante.

### B. Extracție AI și endpoint-ul de import
- **B1.** Promptul de extracție cu output JSON: câmpurile din contract și pasajele-dovadă. Se testează pe 10 articole copiate manual. **LLM-ul nu ghicește coordonate și nu completează ce lipsește.**
- **B2.** Runner-ul batch: reîncercări, cache, salvarea modelului și a versiunii promptului, tratarea JSON-ului invalid și a timeout-urilor.
- **B3.** Normalizarea numelor de străzi („Bd.” = „B-dul” = „Bulevardul”, „Șos.”, „str.”).
- **B4.** ⏳ Eliminarea dublurilor: același accident din mai multe articole primește un singur `event_id`. Potrivirea se face după dată, loc și gravitate; cazurile neclare se marchează, nu se unesc automat.
- **B5.** Endpoint-ul `POST /extract` pentru ecranul 3, plus 2–3 rezultate salvate pentru modul reluare.
- **B6.** Setul de evaluare: 15 articole extrase de mână, **altele decât cele folosite la ajustarea promptului**. Raportăm „X corecte din Y câmpuri”.

### C. Geolocalizare
- **C1.** Geocodare cu Nominatim: cache, 1 cerere/secundă, User-Agent cu numele aplicației.
- **C2.** Intersecții: luăm ambele străzi din OSM și verificăm că au un **nod comun**. Străzile care se suprapun doar în plan pot fi un pasaj, nu o intersecție.
- **C3.** Repere („în dreptul Palas”, „stația Târgu Cucului”), căutate ca POI în OSM.
- **C4.** Completarea `precizie_loc` și `in_iasi` pentru fiecare eveniment; ce e vag rămâne vag.
- **C5.** ⏳ Verificarea manuală a locațiilor din top 10 (vezi aria V).

### D. Context urban (OSM)
- **D1.** Treceri, semafoare, iluminat (tag-ul `lit`; lipsa lui = `null`).
- **D2.** Școli, grădinițe, stații, spitale, mall-uri.
- **D3.** Tipul străzii, numărul de benzi, limita de viteză (unde există).
- **D4.** `crossings.geojson`: fișa fiecărei treceri și intersecții, cu sursă și dată.

### E. Risc
- **E1.** ⏳ Atașarea fiecărui eveniment la cea mai apropiată trecere sau intersecție, pe o rază de 50 m.
- **E2.** Scorul din secțiunea 5, cu componentele salvate.
- **E3.** Explicația automată și lista `date_lipsa` pentru fiecare locație.
- **E4.** Statistici pe locație: distribuția pe 24 de ore, noapte/zi, cauze raportate.
- **E5.** Agregarea H3 (rezoluția 9) pentru stratul vizual de coloane.

### F. Măsuri și export
- **F1.** Tabelul de reguli din secțiunea 7.
- **F2.** Costurile în lei, cu sursă: limitator de viteză, trecere înălțată, iluminat dedicat, semafor pietonal, insulă de refugiu.
- **F3.** Reducerea tipică din CMF Clearinghouse pentru fiecare măsură, cu link. Ca informație, nu ca predicție.
- **F4.** Calculul pentru contorul „Aplică măsurile”: locații, accidente documentate, interval de cost.
- **F5.** Generatorul PDF pentru fișa de verificare.

### G. Interfață
- **G1.** Harta de bază (stil întunecat, înclinare, clădiri 3D) cu încărcarea JSON-urilor.
- **G2.** Straturile: coloane H3, puncte pentru evenimente (cu stil diferit pentru „localizate aproximativ”), cercuri care pulsează pentru top.
- **G3.** Ecranul 2: fișa locației.
- **G4.** Turul cinematic „Top 10”.
- **G5.** Ecranul 3: Import și verificare, cu pasajele evidențiate și butoanele aprobă/corectează.
- **G6.** Animația și contorul „Aplică măsurile”.
- **G7.** Bara de sus, cu sursele, perioada și numerele din manifest; eticheta vizibilă „DATE SINTETICE” când e cazul.
- **G8.** Polish: paletă, logo, lizibilitate pe proiector, comportament când lipsesc date sau harta de bază.
- **Prioritate:** G1 → G2 → G3 → G5 → G4 → G6 → G7 → G8.

### V. Verificare manuală (duminică dimineață)
- **V1.** Pentru fiecare locație din top 10: deschidem toate articolele și confirmăm data, locul, gravitatea și că nu sunt dubluri.
- **V2.** Confirmăm pinul pe hartă sau în Street View / Mapillary.
- **V3.** Verificăm că măsurile afișate sunt susținute de dovezi; altfel le trecem la „de verificat”.
- **V4.** Registrul corecturilor (ce am corectat, nu doar „OK”) e și argument pentru pitch.

### H. Integrare, publicare și rezervă
- **H1.** Fișierele false din `data/` și manifestul, în **primele 20 de minute**.
- **H2.** `run_all.py`: pipeline-ul cap-coadă, cu validarea fișierelor înainte de publicare.
- **H3.** Publicarea link-ului de demo (GitHub Pages sau Netlify).
- **H4.** Laptopul de prezentare: totul instalat, endpoint-ul de extracție testat, hotspot de pe telefon ca rezervă. **Testați și cu internetul oprit**, pentru că harta de bază are nevoie de internet.
- **H5.** Video-ul de rezervă (MP4) al demo-ului complet.
- **H6.** Livrabilele: prezentarea, link-ul demo, descrierea scurtă, lista tehnologiilor AI.

### I. Pitch
- **I1.** Problema: Iașiul e printre județele cu cele mai multe accidente (excluzând Capitala); în 2025, România a avut 3.950 de accidente grave și 1.293 de morți.
- **I2.** Demo-ul (scenariul din secțiunea 10).
- **I3.** Rolul AI, spus explicit: extracție structurată din text nestructurat, cu dovezi și verificare umană.
- **I4.** Business: pilot pentru primărie (fișă de verificare pentru 3–5 locații), apoi abonament de actualizare, apoi alte orașe. Achiziția directă e un avantaj de vânzare (prag de verificat pe anap.gov.ro), nu baza prețului. Alte canale: consultanți pentru fonduri europene și PMUD-uri, dezvoltatori imobiliari, asigurători.
- **I5.** Competitorii: MicroTraffic, VivaCity, AMAG. Modelul e validat în afară, dar nu există în România la nivel de oraș.
- **I6.** Next steps: date oficiale, camerele Centrului de Management al Traficului (detecție near-miss din video), simularea schimbărilor de circulație.
- **I7.** Q&A: pregătiți răspunsuri la „cât de complete sunt datele?”, „cum știți că AI-ul extrage corect?”, „cine plătește?”.
- **I8.** Testarea cu utilizatori (în program duminică, 12:30–14:00): arătați demo-ul unui mentor și notați ce n-a înțeles.

---

## 7. Reguli pentru măsuri

| Situație documentată | Măsură candidată | Ce trebuie verificat înainte |
|---|---|---|
| Pietoni loviți noaptea (2+ evenimente) | Iluminat dedicat trecerii | Iluminatul existent, poziția stâlpilor, vizibilitatea |
| Trecere fără semafor pe 4+ benzi | Semafor pietonal sau insulă de refugiu | Lățimea, traficul, spațiul disponibil, fluxul de pietoni |
| Școală aproape și traversări documentate | Trecere înălțată sau limitator de viteză | Intrările școlii, programul, tipul străzii (nu pe trasee de autobuz/ambulanță) |
| Neacordare de prioritate raportată repetat | Analiza vizibilității și organizării intersecției | Geometria, semnalizarea existentă, tipul conflictului |
| Accidente lângă stații | Mutarea trecerii sau a stației, marcaj, semnalizare | Fluxurile reale de traversare |
| Informații esențiale lipsă | Observație în teren | Lista câmpurilor lipsă |

O cauză relatată în presă **nu** duce automat la o măsură mare (giratoriu, semafor). Măsura e o propunere de analizat, cu verificările de mai sus.

---
# 8. Cine ce face

Scrieți numele lângă fiecare persoană. Până ajung datele reale, **fiecare lucrează pe fișierele false din `data/`**, ca să nu aștepte pe nimeni.

## Cine dă ce cui

| Persoana | Produce | Pentru cine |
|---|---|---|
| 1 | Articolele din presă (`articles.json`) | Persoana 2 |
| 2 | Accidentele extrase din articole, fără coordonate (`accidents.json`) | Persoana 3 |
| 3 | Accidentele cu coordonate (`accidents.json` completat) | Persoanele 4 și 6 |
| 4 | Trecerile (`crossings.geojson`) și locațiile cu scor (`hotspots.json`) | Persoanele 5 și 6 |
| 5 | Măsurile cu costuri (`measures.json`), PDF-ul, pitch-ul | Persoanele 4 și 6, juriul |
| 6 | Interfața | Toată echipa |

---

## Persoana 1 – Colectarea articolelor, apoi livrarea
**Nume:** ________

**Sâmbătă, până la 20:00**
- [ ] Primele 10 minute: urcă pe Git fișierele false în `data/`.
- [ ] Scraper pentru BZI: căutări după „pieton”, „lovit”, „accident”, „trecere”, pe ultimii 2 ani.
- [ ] Scraper pentru Știri Iași, cu aceeași logică.
- [ ] Filtrare: păstrează doar accidentele din municipiul Iași, fără cele din județ și fără știrile generale.
- [ ] Cache local și pauze între cereri, ca să nu fiți blocați.
- [ ] **Până la 16:00:** primele 30 de articole reale în `data/articles.json`, ca Persoana 2 să poată începe pe date reale.
- [ ] **Până la 20:00:** 150+ articole.

**Noaptea (acasă)**
- [ ] `run_all.py`: un singur script care rulează tot, în ordine (articole → extracție → coordonate → scor).
- [ ] Publică interfața pe GitHub Pages sau Netlify și verifică că link-ul merge.

**Duminică**
- [ ] Pregătește laptopul de prezentare: totul instalat, testat și **cu internetul oprit**, plus hotspot de pe telefon ca rezervă.
- [ ] Dacă Persoana 6 a rămas în urmă, preia butonul „Aplică măsurile”.
- [ ] 14:30–16:00: înregistrează video-ul de rezervă al demo-ului complet.
- [ ] **16:30–17:00: predă livrabilele:** prezentarea, link-ul demo, descrierea scurtă, lista tehnologiilor AI.

---

## Persoana 2 – Extracția cu AI
**Nume:** ________

**Sâmbătă, până la 20:00**
- [ ] Prima sarcină: cere pe Discord, în #suport-tehnic, accesul la platforma AI oferită de organizatori.
- [ ] Scrie promptul care transformă un articol în JSON cu câmpurile din `accidents.json`, inclusiv pasajele-dovadă. AI-ul **nu** ghicește coordonate și nu completează ce lipsește.
- [ ] Testează promptul pe cele 4 articole false, apoi pe 10 articole reale copiate manual de pe BZI. Nu aștepta scraper-ul.
- [ ] Scriptul care rulează promptul pe tot `articles.json`, cu reîncercări și cache.
- [ ] Unificarea numelor de străzi: „Bd.”, „B-dul” și „Bulevardul” devin aceeași formă.
- [ ] **Până la 18:00:** primele 50 de accidente reale extrase.

**Noaptea (acasă)**
- [ ] Rulează extracția pe toate articolele.
- [ ] Eliminarea dublurilor: același accident din mai multe articole primește un singur `event_id`. Testează pe ev-003 din datele false.
- [ ] Endpoint-ul `/extract` pentru ecranul de import, plus 2–3 extracții salvate pentru modul reluare de pe link-ul public.

**Duminică**
- [ ] Setul de evaluare: 15 articole extrase de mână (altele decât cele folosite la ajustarea promptului). Dă Persoanei 5 cifra „X corecte din Y câmpuri”.
- [ ] 09:30–12:00: ajută Persoana 3 la verificarea manuală a top 10.
- [ ] Împreună cu Persoana 6: testează ecranul de import cap-coadă.

---

## Persoana 3 – Coordonatele accidentelor, apoi verificarea
**Nume:** ________

**Sâmbătă, până la 20:00**
- [ ] Funcția care transformă un nume de stradă în coordonate cu Nominatim: cache, maxim 1 cerere pe secundă, User-Agent cu numele aplicației.
- [ ] Intersecțiile („X cu Y”): ia ambele străzi din OSM și găsește punctul lor comun.
- [ ] Reperele („în dreptul Palas”, „zona Gării”): caută-le ca puncte de interes în OSM.
- [ ] Completează `lat`, `lon`, `precizie_loc` și `in_iasi` în `accidents.json`.
- [ ] Testează pe datele false: ev-016 trebuie să rămână fără coordonate, iar ev-017 trebuie marcat în afara Iașiului.

**Noaptea (acasă)**
- [ ] Rulează pe toate accidentele reale.
- [ ] Notează câte au fost localizate precis, câte vag, câte sunt în afara Iașiului (pentru manifest).

**Duminică, 09:30–12:00 – Verificarea top 10** (împreună cu Persoana 2)
- [ ] Pentru fiecare locație din top 10: deschide toate articolele și confirmă data, locul și gravitatea.
- [ ] Verifică pinul pe hartă sau în Street View / Mapillary.
- [ ] Verifică să nu existe dubluri.
- [ ] Scrie lista corecturilor (ce s-a corectat, nu doar „OK”). Și asta merge în pitch.

---

## Persoana 4 – Trecerile și scorul de risc
**Nume:** ________

**Sâmbătă, până la 20:00**
- [ ] Cu `osmnx`: descarcă trecerile, semafoarele, iluminatul, școlile, stațiile, tipul străzii și numărul de benzi pentru Iași.
- [ ] Construiește `data/crossings.geojson`. Informațiile lipsă rămân `null`, nu `false`.
- [ ] Atașează fiecare accident la cea mai apropiată trecere sau intersecție, pe o rază de 50 m.
- [ ] Calculează scorul cu formula din secțiunea 5. **Test:** pe datele false trebuie să iasă exact 13, 11, 6, 5, 5.
- [ ] Generează explicația automată, lista datelor lipsă și distribuția pe ore → `data/hotspots.json`.

**Noaptea / duminică dimineață**
- [ ] Aplică regulile de măsuri de la Persoana 5 pentru fiecare locație.
- [ ] Rulează pe datele reale imediat ce Persoana 3 termină coordonatele.
- [ ] Calculează și hexagoanele H3 pentru hartă (opțional; interfața se descurcă și fără ele).

---

## Persoana 5 – Măsuri, costuri, raport și pitch
**Nume:** ________ (probabil cel care prezintă)

**Sâmbătă, până la 20:00**
- [ ] Tabelul de reguli din secțiunea 7, într-o formă pe care Persoana 4 o poate folosi direct în cod.
- [ ] Costuri reale în lei pentru cele 6 măsuri, cu sursă (SEAP, știri despre lucrări similare). Înlocuiește valorile false din `measures.json`.
- [ ] Reducerea tipică din CMF Clearinghouse pentru fiecare măsură, cu link. Dacă nu găsești o valoare potrivită, rămâne `null`.
- [ ] Primele slide-uri: problema și cifrele de context.

**Noaptea (acasă)**
- [ ] Generatorul PDF: „Fișă de verificare pentru primărie”, cu top 10, dovezile, măsurile, ce trebuie verificat și limitele datelor.
- [ ] Slide-urile pentru business, competitori și next steps.

**Duminică**
- [ ] 12:30–14:00: arată demo-ul unui mentor și notează ce nu înțelege.
- [ ] Scenariul de 3 minute (secțiunea 10) și răspunsurile la întrebări: „cât de complete sunt datele?”, „cum știți că AI-ul extrage corect?”, „cine plătește?”.
- [ ] Două repetiții cronometrate, până la 16:00.

---

## Persoana 6 – Interfața
**Nume:** ________

**Sâmbătă, până la 20:00** (totul pe datele false)
- [ ] Harta întunecată, înclinată, care încarcă fișierele din `data/`.
- [ ] Coloanele 3D din accidente (`HexagonLayer`), punctele de accident, cercurile care pulsează pe locațiile din top.
- [ ] Fișa locației la click: scorul și din ce e compus, accidentele cu link-uri, graficul pe 24 de ore, ce lipsește, măsurile.
- [ ] Bara de sus cu cifrele din manifest și eticheta **„DATE SINTETICE”** când e cazul.

**Noaptea / duminică, în ordinea asta**
1. [ ] Ecranul de import și verificare (împreună cu Persoana 2): textul articolului, câmpurile extrase, pasajele evidențiate, butoanele „aprobă” și „corectează”.
2. [ ] Turul cinematic „Top 10”.
3. [ ] Butonul „Aplică măsurile”, cu animația și contorul (locații vizate, accidente documentate, interval de cost).
4. [ ] Polish: culori, logo, lizibilitate pe proiector.

Dacă la 09:30 duminică nu sunt gata punctele 2 și 3, Persoana 1 preia punctul 3.


---

## 9. Calendar (pe programul sălii)

| Când | Ce trebuie să existe |
|---|---|
| **Sâmbătă 14:20** | Fișierele false pe Git, toată lumea pornită pe aria ei. Cerut accesul la platforma AI pe Discord. |
| **16:00** | Primele articole reale, extracția testată pe 10 articole, harta cu date false. |
| **18:00** | Primul rulaj cap-coadă: minim 50 de evenimente reale pe hartă. |
| **19:30–20:00** | Raportul de progres pe Discord (cerut de organizatori), plus planul pentru noapte. |
| **Noaptea (acasă)** | Doar ce nu cere coordonare: scraping și extracție completă, geocodare batch, costuri și CMF, schița slide-urilor, polish la interfață. |
| **Duminică 09:30** | Stand-up: ce intră în demo. Datele se îngheață după acest moment, cu excepția corecturilor din V. |
| **10:00–12:00** | Verificarea manuală a top 10, turul cinematic, animația, PDF-ul. |
| **12:30–14:00** | Testarea cu utilizatori și primul draft complet de pitch. |
| **14:30** | **Feature freeze.** De aici doar bugfix. |
| **14:30–16:00** | Link-ul public, video-ul de rezervă, slide-urile finale, două repetiții cronometrate. |
| **16:30–17:00** | Predarea livrabilelor: prezentarea, link-ul demo, descrierea scurtă, lista tehnologiilor AI. |
| **17:00–20:00** | Pitch-uri: 3 minute + 1–3 minute întrebări. |

**Checkpoint-uri de 5 minute** la 16:00, 18:00, 19:30 și 09:30, cu trei întrebări pentru fiecare: ce rulează, ce s-a schimbat în fișierele contract, ce mă blochează.

---

## 10. Scenariul demo (180 de secunde)

| Secunde | Ce arătăm |
|---|---|
| 0–20 | Problema: Iașiul și pietonii; primăria nu are timp să citească sute de articole și rapoarte. |
| 20–50 | Harta 3D: unde sunt accidentele documentate și cât de complet e eșantionul. |
| 50–90 | Turul cinematic pe 2–3 locații din top: dovezi, scor, explicație. |
| 90–125 | Ecranul de import live: un articol nou intră, AI-ul extrage cu dovezi, aprobăm, punctul apare pe hartă. |
| 125–150 | „Aplică măsurile” și fișa PDF pentru primărie. |
| 150–180 | Limitele, pilotul propus, cererea concretă: date oficiale și 3–5 locații de test. |

---

## 11. Verificări înainte de demo

1. Același accident din două articole e numărat o singură dată.
2. Data publicării nu a devenit data accidentului; orele necunoscute sunt `null`.
3. Nu există puncte în altă localitate, nici latitudine și longitudine inversate.
4. Un tag OSM lipsă nu a produs o recomandare de tipul „lipsește X”.
5. Numerele din hartă, fișă, PDF și contor sunt identice.
6. Datele sintetice nu apar în versiunea finală.
7. Un timeout sau un JSON invalid la extracție nu strică datele deja aprobate.
8. Cele 3 locații din pitch au fost verificate manual, cu articolele deschise.

---

## 12. Instrucțiune comună pentru agenții de coding

> Lucrezi la „Harta pietonului – Iași”, un demo de hackathon. Citește PLAN.md (secțiunile 4–7) și sarcina ta. Modifică doar folderul ariei tale; orice schimbare a fișierelor contract o propui separat. Nu inventa accidente, coordonate, surse, costuri sau efecte asupra siguranței. Necunoscutul rămâne null. Un articol nu este un accident. Lucrează pe datele false până apar cele reale și nu le amesteca. Livrează schimbări mici și rulabile. La final spune ce fișiere ai schimbat, cum se rulează, ce ai verificat și ce rămâne nesigur.

---

## 13. Surse

- Programul și criteriile hackathonului: https://markaiintegrator.ro/hackathon-ai/
- CMF Clearinghouse: https://cmfclearinghouse.fhwa.dot.gov/userguide_CMF.php
- Politica Nominatim: https://operations.osmfoundation.org/policies/nominatim/
- H3, dimensiunile pe rezoluții: https://h3geo.org/docs/core-library/restable/
- TomTom Traffic Flow (opțional): https://docs.tomtom.com/traffic-api/documentation/tomtom-maps/v1/traffic-flow/flow-segment-data
- Documentul inițial „Aplicație siguranță rutieră Iași – date, PoC și monetizare” (context, competitori, monetizare)