# Data sources for Iași crash and risk data: findings (Claude Code)

Research run on 2026-10-18 against the brief in `../DATA_SOURCES_RESEARCH.md`. Everything marked as verified was opened in
this session; the command or URL and a real sample are given. Samples are in `samples/claude/`.

## Summary

- **The press is a small share of reality.** Iași county had **1,462 injury crashes in 2025, 58 deaths and 1,799
  injured** (INS, official). The county was **2nd of 42 in Romania**, after Bucharest. The municipality alone had
  about **650 injury crashes a year** before COVID (IPJ data published in the PMUD). Our press scrape holds 94 articles
  for June–October 2026, many of them not crashes.
- **Best source to automate today: ISU Iași press releases.** These are official, published within days, follow a fixed
  template, contain no personal names, and give the event date, time, road, vehicles and victims. There were 252 crash
  releases in 2025 and 158 in 2026 up to 15 October.
- **Best ground truth: the IPJ Iași crash database.** IPJ already handed the record-level database for 2010–2014 to the
  PMUD consultants, and the 2022 PMUD update publishes IPJ figures per street for 2020–2021. That precedent makes a
  Legea 544 request or a partnership realistic. This is the product's real data source.
- **The market exists and is priced.** Municipiul Iași buys traffic-light designs for single intersections or crossings
  at **26,900 lei each** (at least 6 times in 2022–2024). Sector 3 Bucharest bought **road safety audits for busy
  intersections** at 20,000–264,000 lei per lot (2023). Miroslava bought traffic studies for 35,000 and 201,000 lei.

## 1. Top 5

### 1. ISU Iași press releases ("Știri de presă"). Verdict: use now

- **What:** every intervention by the county emergency service (pompieri + SMURD) gets a numbered press release (SP nr.)
  with a PDF.
- **Where:**
  - Listing pages (one per year): `https://isuis.igsu.ro/comunicate-de-presa/stiri-de-presa-2025-56`,
    `…/stiri-de-presa-2026-175`, `…/stiri-de-presa-2024-57`.
  - PDFs: `https://isuis.igsu.ro/resources/<uuid>.pdf`. The page sets `<base href="/">`, so the PDF links resolve
    against the site root, not the listing folder.
- **Sample, SP nr. 29 from 07.01.2025** (`samples/claude/isu_pdf/` holds 15 releases from 2026):
  > "Dispeceratul Integrat ISU – SMURD – SAJ Iași a fost anunțat prin SNUAU 112, în data de 7 ianuarie a.c., la ora 18:24,
  > despre producerea unui accident rutier în municipiul Iași, strada Cerna, unde au fost implicate două autoturisme …
  > a rezultat o victimă, conștientă, neîncarcerată … transportată la spital."
- **Volume:** 421 crash-titled releases on the site: 11 from 2024 (October onwards only), 252 in 2025, 158 in 2026 up to
  15 October. About 66 of the 2025 titles name the municipality or a street. Some 2026 titles include the street
  ("Accident rutier în municipiul Iași, strada Vasile Lupu"). The list of crash titles with URLs is in
  `samples/claude/isu_accidente_titluri_2024_2026.json`.
- **Format:** the wording varies by period.
  - Early 2025: "anunțat … la ora HH:MM, despre producerea unui accident rutier în …, strada X".
  - 2026: "În data de DD.MM.YYYY, ora HH:MM, … au intervenit pe DJ 208L, în satul Brătești, comuna …".
  - My first regex found the time and vehicles in most releases, but the location in 0 of 15. The parser needs two or
    three patterns plus the title, and is rule-based, with no LLM.
  - **The event date ≠ the release date.** One release dated 28.09 describes a crash on 23.09.
- **Limits:**
  - Only crashes where ISU intervened (extrication or first aid), roughly 250 a year against 1,462 police-recorded
    injury crashes in the county.
  - No coordinates; the location is a street, road code or village.
  - The archive before October 2024 is gone: the old site `isujis.ro` now serves the new SPA.
  - There's no stated licence. These are public-institution press releases, so we store the facts and the link.
  - Includes some non-road items (rail, aviation, work accidents). Filter by title.
- **Scores:** granularity 3, coverage 2, history 2, freshness 5, provenance 5, access 4, licence 3, effort 4.
- **Next step:** a scheduled scraper over the yearly listing pages, a PDF-to-text step, a rule parser, then the existing
  `coordonate/` geocoder, publishing events labelled "sursă: ISU Iași".

### 2. PMUD Iași (2017 update and 2022 re-update), with IPJ data. Verdict: use now as a baseline

- **Where:**
  - `https://zmi.ro/wp-content/uploads/2026/06/PMUD-Iasi-Reactualizare-2022.pdf` (21 MB, 266 pages), §2.6.2, pp. 72–75.
  - `https://zmi.ro/wp-content/uploads/2026/06/01.PMUD-Iasi-Actualizare-finala_sept_2017.pdf` (25 MB), §2.6.2, pp. 77–80.
  - zmi.ro's WordPress media API is open: `https://zmi.ro/wp-json/wp/v2/media?search=PMUD`.
- **Verified content.** The footnotes say "Sursa: Inspectoratul Județean de Poliție Iași". The pages are rendered in
  `samples/claude/pmud2022_p-072.png`, `pmud2022_p-073.png` and `pmud2017_p-077.png`.
  - **Table 2.11: arteries with the most crashes, 2020/2021**, checked against the rendered page
    (`samples/claude/pmud2022_tabel_2_11_artere.csv`). Watch out: plain text extraction shifts every row by one.
    - str. Nicolina 40/43
    - Bucium 18/23
    - Carol I 19/16
    - Păcurari 17/16
    - Alexandru cel Bun 16/6
    - Vasile Lupu 16/12
    - Nicolae Iorga 12/15
    - Socola 13/7
    - Calea Chișinăului 12/8
    - Independenței 10/9
    - Tudor Vladimirescu 4/16
    - Sf. Lazăr 7/11
  - **Municipality totals, 2014–2020:** 503, 624, 636, 652, 649, 660, 484 crashes, with serious/minor split
    (`pmud2022_municipiu_total_2014_2020.csv`).
  - **Causes in 2020:**
    - failure to yield to vehicles 85
    - pedestrian indiscipline 84
    - cyclist indiscipline 57
    - failure to yield to pedestrians 46
    - following distance 43
    - speed 32
    - other 73
  - **List of signalised intersections (Table 2.12).** Useful context for "fără semafor".
  - **2017:** IPJ Serviciul Rutier provided the crash **database for 2010–2014**. Coordinates were recorded only for
    November–December 2014; before that, locations were descriptions relative to landmarks.
    - Fig. 37 is a dot map of all 2010–2014 crashes in the municipality by severity.
    - Table 12 gives crashes, deaths and injuries per locality per year (Iași: 420–470 a year).
    - Table 13 gives crashes by type (pedestrian struck: 1,379 in five years, 63 deaths).
  - **Black spots in 2012:** eight zones in the county; DN28 at Tomești, Valea Lupului, Lețcani, Podu Iloaiei, Bălțați,
    Războieni, Târgu Frumos; DN24 at Poiana (Schitu Duca).
- **Limits:** aggregates per street, not per crash. Data stops in 2021. The GIS layer behind Fig. 37 isn't published.
- **Scores:** granularity 3, coverage 5, history 4, freshness 1, provenance 5, access 4, licence 3, effort 5.
- **Next step:** load Table 2.11 as an "official ranking 2020–2021" layer. Use it to check that our ranking from ISU and
  the press points at the same arteries; Nicolina and Bucium also top our press data. Ask ZMI or Primăria for the
  PMUD GIS layers (request B).

### 3. INS TEMPO API (TRN104F, TRN105B), mirrored by Eurostat `tran_sf_roadnu`. Verdict: use now for context

- **Where:**
  - Table catalogue (JSON): `http://statistici.insse.ro:8077/tempo-ins/matrix/matrices?lang=ro`.
  - Table metadata: `…/tempo-ins/matrix/TRN104F`.
  - Data: `POST …/tempo-ins/pivot` with
    `{"language":"ro","encQuery":"3085:<year ids>:9669","matCode":"TRN104F","matMaxDim":3,"matUMSpec":0}`, which
    returns CSV.
  - Eurostat: `https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/tran_sf_roadnu?geo=RO213`. This is
    the NUTS 3 table, and RO213 is Iași county.
- **Sample:** "Iasi, Anul 2025, Numar, 1462". The Iași series runs from 254 crashes in 1999 to 1,462 in 2025 and has risen
  every year since 2020. Iași county deaths/injured: 2018 61/1,469 … 2025 58/1,799. Eurostat gives the same counts, plus
  a rate of **1,784 crashes per million inhabitants in 2024**. Files: `samples/claude/tempo_*.csv` and
  `eurostat_roadnu_RO213.json`.
- **Cross-check:** INS 2022 = 1,235, which matches the IPJ figure in the prefecture document (source 6).
- **Ranking in 2025:** Bucharest 3,028, Iași 1,462, Suceava 1,127, Constanța 1,115, Cluj 1,080
  (`tempo_TRN104F_judete_2025.csv`).
- **Other INS tables:** TRN104A–E break crashes down by type, moment, road surface, conditions and place. I checked only
  their titles, not whether they split by county: **UNVERIFIED**.
- **Scores:** granularity 1, coverage 5, history 5, freshness 2, provenance 5, access 5, licence 4 (Eurostat allows reuse
  with attribution; INS terms **UNVERIFIED**), effort 5.

### 4. IPJ Iași record-level crash database, through Legea 544 or a partnership. Verdict: use for the business

- **Evidence it exists and has been shared:**
  - PMUD 2017 (above): "IPJ Iași – Serviciul Rutier a pus la dispoziție baza de date a accidentelor rutiere din perioada
    2010–2014". GPS recording has been mandatory since 2011.
  - PMUD 2022 publishes IPJ per-street counts.
  - The prefecture document (source 6) is IPJ analysis with yearly county figures.
- **Why it matters:** this is the only source with every injury crash, its cause and its severity. With coordinates it
  scores 5 on granularity, coverage and provenance.
- **Limits:** it takes 10–30 days. IPJ may refuse coordinates or cite ongoing investigations, so ask for an anonymised
  statistical extract. There's no API.
- **Scores:** granularity 5 (if coordinates are given), coverage 5, history 5, freshness 2, provenance 5, access 1,
  licence 3, effort 1.
- **Next step:** send request A, below.

### 5. SICAP (e-licitatie.ro) public API for direct awards. Verdict: use now for the pitch and pricing

- **Where:** `POST https://www.e-licitatie.ro/api-pub/DirectAcquisitionCommon/GetDirectAcquisitionList/` with
  `{"pageSize":500,"pageIndex":0,"directAcquisitionName":"<text>","finalizationDateStart":"2022-01-01T00:00:00.000Z","finalizationDateEnd":"…"}`
  and a `Referer` header from e-licitatie.ro. No login.
- **Sample and the full export:** `samples/claude/sicap_achizitii_directe_siguranta.csv` (8 queries, 2,057 rows; capped at 500 per query).
  The Iași-area rows are listed in §4.
- **Scores (market evidence, not crash data):** access 5, provenance 5, effort 5.

## 2. Full table

| Source | URL / endpoint | Format | Status | Granularity | History | Licence | Scores G/C/H/F/P/A/L/E | Verdict |
|---|---|---|---|---|---|---|---|---|
| ISU Iași press releases | `isuis.igsu.ro/comunicate-de-presa/stiri-de-presa-<year>-<id>` + `/resources/<uuid>.pdf` | HTML list + PDF | ✅ 200 | street / road / village, time | Oct 2024 → now | none stated, public | 3/2/2/5/5/4/3/4 | **use now** |
| ISU Iași daily bulletins (BI) | `…/comunicate-de-presa/buletine-informative-2026-171` (also 2024, 2025) | PDF | ✅ 200, 184 in 2026 | daily totals? content **UNVERIFIED** | 2024 → now | public | ?/3/2/5/5/4/3/3 | check content |
| PMUD Iași 2022 re-update (IPJ data) | `zmi.ro/wp-content/uploads/2026/06/PMUD-Iasi-Reactualizare-2022.pdf` | PDF | ✅ 200 | per street (aggregates) | 2014–2021 | public document | 3/5/4/1/5/4/3/5 | **use now** (baseline) |
| PMUD Iași 2017 update (IPJ DB 2010–2014) | `zmi.ro/wp-content/uploads/2026/06/01.PMUD-Iasi-Actualizare-finala_sept_2017.pdf` | PDF | ✅ 200 | dot map image, locality tables | 2010–2014 | public document | 3/5/4/1/5/4/3/4 | use now (history) |
| PMUD drawings (Partea II) | `zmi.ro/…/02.PMUD_FINAL_PARTEA-II_Parti-desenate.pdf` | PDF maps | ✅ 200, 18 pages | maps of planned measures by code | — | public | 2/–/–/1/5/4/3/2 | low value |
| INS TEMPO TRN104F / TRN105B | `statistici.insse.ro:8077/tempo-ins/…` | JSON + CSV API | ✅ 200 | county | 1999–2025 | INS terms **UNVERIFIED** | 1/5/5/2/5/5/4/5 | **use now** (context) |
| Eurostat `tran_sf_roadnu` | `ec.europa.eu/eurostat/api/…/tran_sf_roadnu?geo=RO213` | JSON API | ✅ 200 | NUTS 3 (county) | 1999–2024 | Eurostat reuse with attribution | 1/5/5/2/5/5/4/5 | use now (EU comparison) |
| IPJ Iași record-level crash DB | via request A | XLSX/CSV, if granted | precedent ✅, access ❌ | per crash (GPS since 2011) | 2010 → | to be agreed | 5/5/5/2/5/1/3/1 | **business** |
| Prefecture: IPJ material, May 2023 | `is.prefectura.mai.gov.ro/wp-content/uploads/sites/49/2023/07/Material-IPJ-Iasi.pdf` | PDF | ✅ 200 | county | 2021–2022 | public | 1/5/2/1/5/4/3/5 | use (quotes, cross-check) |
| Prefecture WordPress API | `is.prefectura.mai.gov.ro/wp-json/wp/v2/media` | JSON | ❌ 401/403 | — | — | — | — | dead end (use site search) |
| IPJ Iași daily press bulletin | `is.politiaromana.ro/ro/stiri-si-media/stiri` (+ `/ro/rss`) | HTML | ✅ (incomplete TLS chain) | crash in about 1 of 30 bulletins | rolling | public | 3/1/2/5/5/3/3/3 | secondary |
| IGPR national road safety report 2024 | `politiaromana.ro/ro/stiri/activitati-ale-politiei-romane-pentru-siguranta-rutiera-desfasurate-in-anul-2024` | HTML | ✅ | national totals only | yearly | public | 1/5/3/2/5/4/3/5 | pitch context |
| Court portal SOAP | `http://portalquery.just.ro/query.asmx` (`CautareDosare`, `CautareSedinte`) | SOAP XML | ✅ 200, no key | court and case object only, **no location** | current cases | contains **full names, GDPR** | 1/2/2/4/5/5/1/3 | aggregates only |
| CNAIR black spots | press only (economedia, 9 June 2023): 267 hotspots for 2015–2019, 40 to be lit, not named | — | list not published | — | — | — | — | request D |
| Avocatul Poporului road safety report, 2025 | `avp.ro/wp-content/uploads/2025/05/raport-special-siguranta-rutiera-in-Romania.pdf` | PDF | ✅ | national; mentions the DRDP Iași 2022 traffic census on DN2 | 2019–2024 | public | 1/–/2/1/5/4/3/4 | pitch context; census lead → request D |
| data.gov.ro | `data.gov.ro/api/3/action/package_search` | CKAN API | ✅, 0 crash datasets | — | — | — | — | dead end |
| Primăria Iași open data | none found | — | none found | — | — | — | — | dead end |
| Comisia de circulație decisions | only in press (BZI); official minutes not found | — | **UNVERIFIED** | per crossing | — | — | — | request B |
| Waze for Cities | `waze.com/ro/wazeforcities` (Bucharest city-hall partnership reported in press) | partner feed | free for public partners | live alerts and jams | — | partner terms | 4/3/1/5/3/1/2/1 | business (through Primăria) |
| ZDI WordPress API (press) | `ziaruldeiasi.ro/wp-json/wp/v2/posts?search=accident` | JSON | ✅ (about 40 s) | text only | years | copyright: facts and link only | 2/1/4/5/2/5/2/5 | use now (already in repo) |
| BZI search feed | `bzi.ro/?s=accident&feed=rss2` | RSS | ✅ | text | about 1 week per page | same as above | 2/1/2/5/2/4/2/5 | use now |
| Radio Iași WordPress API | `radioiasi.ro/wp-json/wp/v2/posts?search=accident` | JSON | ✅ 200 | text | **UNVERIFIED** depth | same as above | 2/1/?/5/3/5/2/5 | add to ingestion |
| infotraficromania.ro Iași feed | `infotraficromania.ro/category/info-trafic-iasi/feed/` | RSS | ✅ 200 (35 KB) | text | **UNVERIFIED** | aggregator, unclear | 2/1/?/5/1/4/1/4 | low priority |
| Google News RSS | `news.google.com/rss/search?q=accident+Iași…` | RSS | ✅ | titles and redirect links | about 30 days | — | 1/2/1/5/2/4/1/4 | discovery only |
| Open-Meteo archive | `archive-api.open-meteo.com/v1/archive?latitude=47.16&longitude=27.58&…&hourly=precipitation,is_day` | JSON | ✅ 200, no key | hourly, about 10 km cell | decades | free tier (terms not re-checked) | –/–/5/5/3/5/3/5 | use now (derive night and rain) |
| OSM (already in repo) | `context/`, `coordonate/` | GeoJSON | ✅ | infrastructure | current | ODbL | –/–/–/4/3/5/4/5 | use now |
| France BAAC (template) | `data.gouv.fr/api/1/datasets/bases-de-donnees-annuelles-des-accidents-corporels-…` | JSON / CSV | ✅ 200 | per crash with GPS | 2005–2023 | Licence Ouverte | — | template for request A + pitch |
| UK STATS19 / DE Unfallatlas (template) | `data.gov.uk/dataset/cb7ae6f0-…/road-safety-data`, `unfallatlas.statistikportal.de` | CSV / map | ✅ 200 | per crash | decades | OGL / dl-de | — | pitch: "Romania doesn't publish this" |
| TUIASI theses | `doctorat.tuiasi.ro/…/Rezumat-Teza-Marius-iunie-2025.pdf` (sensors, not crashes); cites Dumbravă (2018), a thesis on "zone negre" | PDF | ✅ / thesis **UNVERIFIED** | — | — | — | — | follow up on the Dumbravă thesis |
| CTP Iași GTFS | transitfeeds search returned 403 | — | **UNVERIFIED** | stops | — | — | — | OSM stops as fallback |

## 3. Legea 544/2001 request drafts

Send by email, keep the registration number, and ask for an electronic reply. The legal deadline is 10 days, or 30 for
complex requests, as the law requires. All four ask for **anonymised data, without personal data**. That keeps them
outside the GDPR and outside the exception for ongoing investigations.

### A. IPJ Iași, Serviciul Rutier (most important)

To: Inspectoratul de Poliție Județean Iași, str. Mihai Costachescu nr. 2, Iași. Email `ipjiasi@is.politiaromana.ro`
(this address appears in the IPJ document published by the prefecture).

> Subsemnatul/Subsemnata …, în temeiul Legii nr. 544/2001 privind liberul acces la informațiile de interes public,
> vă rog să-mi comunicați, în format electronic editabil (CSV sau XLSX), următoarele informații:
> 1. Lista accidentelor de circulație cu victime (decedați, răniți grav, răniți ușor) înregistrate pe raza municipiului
>    Iași și a comunelor din Zona Metropolitană Iași în perioada 01.01.2021 – 30.09.2026, cu următoarele câmpuri pentru
>    fiecare accident: data, ora, localitatea, strada / intersecția / reperul, coordonatele GPS (dacă au fost
>    înregistrate), modul de producere, cauza principală reținută, categoriile de participanți (pieton, biciclist,
>    trotinetă, autoturism, transport public etc.), numărul de decedați, răniți grav și răniți ușor, condițiile de
>    iluminare și de carosabil.
> 2. Lista zonelor / sectoarelor de drum identificate ca „puncte negre" sau zone cu risc ridicat de accidente pe raza
>    județului Iași, cu criteriul folosit și anul identificării.
> Solicit exclusiv date anonimizate, fără date cu caracter personal (nume, CNP, numere de înmatriculare, date despre
> dosare penale individuale). Precizez că un extras similar (baza de date a accidentelor 2010–2014) a fost pus la
> dispoziție pentru elaborarea Planului de Mobilitate Urbană Durabilă Iași. Dacă un câmp nu este disponibil, vă rog
> să-mi comunicați celelalte câmpuri.
> Vă mulțumesc. Data, semnătura, adresa de e-mail.

### B. Primăria Municipiului Iași

To: Primăria Municipiului Iași. Email `informatii@primaria-iasi.ro` (from the home page).

> În temeiul Legii nr. 544/2001, vă rog să-mi comunicați în format electronic:
> 1. Procesele-verbale / hotărârile Comisiei de circulație a Municipiului Iași din perioada 2021–2026 privind
>    înființarea, desființarea sau semaforizarea trecerilor de pietoni, montarea limitatoarelor de viteză și
>    reorganizarea intersecțiilor.
> 2. Lista trecerilor de pietoni și a intersecțiilor semaforizate administrate de municipiu, cu localizarea lor
>    (fișier GIS sau coordonate, dacă există).
> 3. Datele privind accidentele rutiere puse la dispoziție de IPJ Iași pentru Reactualizarea 2022 a PMUD
>    (tabelele și straturile GIS din capitolul 2.6.2) și straturile GIS ale PMUD.
> 4. Volumele de trafic pe intersecție înregistrate de sistemul de management al traficului, pentru un an complet
>    (2025), dacă sunt disponibile.

### C. ISU „Mihail Sturdza" Iași

To: ISU Iași, str. Lascăr Catargi nr. 59, Iași. Email `relatii.publice.isujiasi@gmail.com` and `isujiasi@gmail.com`
(both appear on the official ISU release, SP nr. 29/2025).

> În temeiul Legii nr. 544/2001, vă rog să-mi comunicați în format electronic lista intervențiilor la accidente rutiere
> din județul Iași în perioada 01.01.2019 – 30.09.2026, cu: data și ora apelului, localitatea și adresa/locul
> intervenției (și coordonatele, dacă sunt înregistrate în dispecerat), numărul de vehicule implicate, numărul de
> victime și dacă a fost necesară descarcerarea. Solicit date anonimizate, fără date cu caracter personal.
> De asemenea, vă rog să precizați dacă știrile de presă publicate înainte de octombrie 2024 sunt disponibile într-o
> arhivă publică.

### D. DRDP Iași / CNAIR

To: Direcția Regională de Drumuri și Poduri Iași (CNAIR). **Contact UNVERIFIED**: look it up on the cnair.ro contact
page before sending.

> În temeiul Legii nr. 544/2001, vă rog să-mi comunicați: (1) lista sectoarelor de drum național din județul Iași
> identificate ca „puncte negre" / zone cu concentrație de accidente în ultimii 5 ani, cu poziția kilometrică;
> (2) rezultatele evaluării siguranței rutiere la nivelul întregii rețele pentru drumurile naționale din județul Iași
> (conform legislației de transpunere a Directivei (UE) 2019/1936), inclusiv clasificarea pe niveluri de siguranță;
> (3) rezultatele recensământului circulației din 2022 (volume medii zilnice) pentru posturile de pe DN2, DN24, DN28,
> DN28A din județul Iași.

## 4. Market evidence (SICAP direct awards, verified through the API)

| Date | Buyer | What | Value (lei) |
|---|---|---|---|
| 2023-06 | Sector 3, Municipiul București | "Servicii de audit de siguranță rutieră pentru intersecțiile aglomerate" (6 awards) | 20,000 – 264,000 each |
| 2023-04-03 | Autoritatea Rutieră Română | Software to manage road safety impact assessments and audits | 146,000 |
| 2022-04 → 2024-08 | **Municipiul Iași** | Design of traffic lights for one intersection or crossing, including Bd. Alexandru cel Bun × Prof. Paul Bujor and Șos. Națională × Str. Olt (at least 6 awards) | 26,900 each |
| 2022-03-29 | **Municipiul Iași** | Supervision of traffic-light works | 8,260 |
| 2024-03-13 | Direcția Județeană de Administrare a Drumurilor Iași | Road safety: design and works for traffic lights on DJ 249A km 2+510 | 144,000 |
| 2024-07-03 | Comuna Miroslava (metropolitan area) | Study of car and pedestrian traffic organisation | 35,000 |
| 2026-10-07 | Comuna Miroslava | Technical studies: traffic study, DNSH, approval documents | 201,000 |
| 2023-10 | Comuna Rediu | Speed bumps with documentation and permits | 4,000 + 6,000 |
| 2026-10 | Municipiul Săcele, Brad, Județul Ialomița, Mediaș, Tulcea | Traffic studies | 35,000 – 269,000 |

From press, not checked in SICAP: Brașov launched a 4-year framework for maintaining and installing traffic-safety
elements worth 67.7 million lei (bids due 28.10.2026); Sector 1 launched a 50 million lei tender for school-zone safety.

**Takeaways:**
1. Cities already pay 25,000–35,000 lei per intersection for design or studies, and up to 264,000 lei for audits.
2. Iași's purchases are reactive, one intersection at a time. A prioritised, evidence-backed list is exactly the input
   these purchases lack.
3. A per-location "dossier" priced below the design contract can be bought by direct award; the threshold for services
   is **UNVERIFIED**, check the current value.

## 5. Open questions for a human

1. **Will IPJ release coordinates?** The 2010–2014 extract was given to a ministry-funded PMUD consortium, not to a
   private company. Partnering through Primăria Iași or ZMI (as the city's contractor) may work better than a cold
   request.
2. **Licensing of ISU and IPJ press releases for commercial reuse.** Needs a short legal opinion. The current plan is
   facts plus a link, no copied text.
3. **Pre-October-2024 ISU archive.** Ask ISU (request C) or check the Wayback Machine for `isujis.ro` (not checked).
4. **INS reuse terms and the county split of TRN104A–E.** Not checked.
5. **The PMUD GIS layers behind Fig. 37 and Table 2.11.** Who holds them: ZMI, Primăria, or the consultants?
6. **Waze for Cities.** Only Primăria can sign; is anyone at Primăria Iași interested?
7. **CNAIR's 267 hotspots (2015–2019).** Is the list public anywhere? Not found.

## 6. Recommended plan

- **Today (demo):**
  - Ingest ISU releases (2025–2026, about 410 events) with a rule parser and the existing geocoder.
  - Keep the press as a secondary source.
  - Show PMUD Table 2.11 as the "official 2020–2021 IPJ ranking" layer, to validate our ranking.
  - Show the INS/Eurostat trend (Iași 2nd nationally, rising since 2020) on the about/pitch screen.
- **Next week (business):**
  - Send requests A–D.
  - Pitch Primăria Iași with the pricing evidence above.
  - Offer an "audit-ready dossier per intersection" built from ISU, IPJ and OSM data and cameras.

## Sources

Every URL above was opened in this session. Supporting web searches, for context only:
[Prefecture IPJ material](https://is.prefectura.mai.gov.ro/wp-content/uploads/sites/49/2023/07/Material-IPJ-Iasi.pdf),
[PMUD 2017 on zmi.ro](https://zmi.ro/wp-content/uploads/2022/01/01.PMUD-Iasi-Actualizare-finala_sept_2017.pdf),
[BZI, IPJ 2025 assessment](https://www.bzi.ro/evaluarea-activitatii-desfasurate-de-catre-politistii-din-cadrul-ipj-iasi-in-anul-2025-5470911),
[ISU Iași 2025 releases](https://isuis.igsu.ro/comunicate-de-presa/stiri-de-presa-2025-56),
[IGPR 2024 road safety activity](https://politiaromana.ro/ro/stiri/activitati-ale-politiei-romane-pentru-siguranta-rutiera-desfasurate-in-anul-2024),
[Avocatul Poporului special report](https://avp.ro/wp-content/uploads/2025/05/raport-special-siguranta-rutiera-in-Romania.pdf),
[Economedia, CNAIR black spots](https://economedia.ro/bani-din-pnrr-pentru-mai-multa-siguranta-pe-sosele-cnair-ilumineaza-40-de-puncte-negre-cu-energie-verde.html),
[Transilvania 365, Brașov tender](https://transilvania365.ro/primaria-scoate-la-licitatie-lucrari-de-peste-67-milioane-de-lei-pentru-siguranta-traficului-din-brasov/),
[Business24, Sector 1 tender](https://business24.ro/licitatie-publica/licitatie-infrastructura-rutiera-siguranta-elevi-1659986),
[Apix, Iași traffic-light designs](https://apix.ro/noi-intersectii-din-oras-vor-fi-semaforizate-contracte-de-proiectare-semnate-cu-aceeasi-firma/),
[Waze for Cities](https://www.waze.com/ro/wazeforcities),
[Gadget.ro, Bucharest–Waze partnership](https://gadget.ro/primaria-bucuresti-incheiat-un-parteneriat-cu-waze-romania-pentru-fi-informata-de-gropile-din-capitala/).
