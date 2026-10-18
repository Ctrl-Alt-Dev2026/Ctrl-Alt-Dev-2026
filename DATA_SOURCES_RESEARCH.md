# Research brief: where to get real crash and risk data for Iași

Brief for the agents (Claude Code and Codex) that will search in parallel. Read all of it before you start.
Written 2026-10-18.

## 1. Why this matters

SafeIași has to become a business. We sell reports and recommendations ("these 10 locations, why, what to check,
what to do") to the people who pay for road safety: Primăria Iași, the metropolitan area, county councils, CNAIR/DRDP,
insurers, fleet operators, developers who need traffic studies, and engineering firms bidding on public tenders.
A buyer pays for **real, traceable data**: fewer than one crash a week scraped from the press is a demo, not a product.

We need sources that answer at least one of these:
1. **Where and when did crashes happen?** One event per row, located to a street, intersection or coordinates.
2. **Which areas are officially known to be dangerous?** Black spots, high-risk zones, lists of planned works.
3. **Why do crashes happen there?** Cause, participants, severity, light conditions, speed.
4. **Exposure and context.** Traffic volumes, speeds, pedestrian flows, infrastructure (lighting, signals, lanes).
5. **Who buys this and for how much?** Past tenders, studies and contracts for road safety work in Iași and Romania.

## 2. What we already know (don't repeat it, build on it)

All of this was probed live on 2026-10-18. Details are in the user's session notes and in `scraping/`.

| Source | Status |
|---|---|
| Ziarul de Iași WordPress API `https://www.ziaruldeiasi.ro/wp-json/wp/v2/posts?search=accident` | Works. Full text as JSON. Slow (about 40 s). |
| BZI `https://www.bzi.ro/?s=accident&feed=rss2` | Works. About 50 items per week, national news mixed in. Its `wp-json` search returned 0 results. |
| Google News RSS `news.google.com/rss/search?q=accident+Iași+when:30d&hl=ro&gl=RO&ceid=RO:ro` | Works. Many outlets. Links are Google redirect URLs. |
| IPJ Iași `https://is.politiaromana.ro/ro/stiri-si-media/stiri` (plus `/comunicate` and `/ro/rss`) | Daily "BULETIN DE PRESĂ". The TLS certificate chain is incomplete, so you need certifi or an unverified context. Out of 30 bulletins, one contained a crash; the rest are enforcement actions. |
| data.gov.ro CKAN API (`/api/3/action/package_search`) | No accident dataset for "accidente", "rutier", "poliția" or "iasi trafic". Only noise maps. |
| IGPR national statistics | Annual national totals reported in the press. No coordinates. |
| OSM (already in `context/`, `coordonate/`) | Crossings, lanes, signals and the Iași street index. Infrastructure only, no crashes. |
| Repo pipelines | `scraping/` (BZI/ZDI scraper), `ai/` (rules + Ollama extraction), `coordonate/` (offline geocoding), `risk/`, `measures/`, `safecross/` (YOLOX video). |

## 3. Search tracks

Each track lists leads, not conclusions: confirm everything yourself.

### Track A: official, legal and institutional sources

- **Police (IGPR, IPJ Iași, Poliția Locală Iași).** Do they publish statistics per county or city, yearly road safety
  reports ("analiza activității", "bilanț"), "puncte negre", or crash maps? Do they publish the daily speed camera
  locations ("radare", "locații radar"), which show where police see speeding risk? Is there an "e-SIGUR" public
  dataset? Check the "Informații publice" and "Rapoarte" sections of `politiaromana.ro` and `is.politiaromana.ro`.
- **National statistics.** INS TEMPO Online (`statistici.insse.ro/tempoins`): which tables cover road accidents, and
  can they be broken down by county or municipality? Is there an API or CSV export? Also check the INS "Transporturi"
  yearbooks.
- **EU sources.** Eurostat (`tran_sf_roadse`, `tran_sf_roadnu` and related tables, NUTS level), the CARE database, the
  EU Road Safety Observatory country profile for Romania, and the EU Urban Mobility Indicators (SUMI). Did Iași take part?
- **Road authorities.** CNAIR and DRDP Iași: black spot lists ("puncte negre"), network safety assessments under
  Directive 2019/1936 ("evaluarea siguranței rutiere la nivelul întregii rețele"), and iRAP/EuroRAP star ratings for
  roads around Iași (DN24, DN28, the ring road). Also the Ministry of Transport and the national road safety council
  (CIRSR), with the Strategia Națională de Siguranță Rutieră 2022–2030 and its annexes and monitoring reports.
- **Primăria Iași and the metropolitan area.**
  - **PMUD Iași** (Planul de Mobilitate Urbană Durabilă) and its updates. These plans usually include a crash analysis
    with maps and tables. This is a strong lead: find the PDF and its annexes.
  - Traffic studies, the traffic-light modernisation project (ITS / "management trafic"), and Smart City projects.
  - Council decisions (HCL) and Comisia de circulație minutes about crossings, traffic lights and speed bumps. These
    show which places the city already treats as problems.
  - The ADI Zona Metropolitană Iași studies.
- **Free public-information requests (Legea 544/2001).** Draft exact request texts for IPJ Iași (Serviciul Rutier),
  Poliția Locală Iași and Primăria Iași. Ask for crashes per street or intersection for 2021–2026, with date, hour,
  severity, participants and cause, and the list of black spots. These requests take 10–30 days, so they are a
  business path, not a demo path. The deliverable here is the text and the address to send it to, not a sent request.
- **Courts.** `portal.just.ro`: is there a public SOAP/web service (`portalquery.just.ro/query.asmx`)? Can you search
  Iași courts for "ucidere din culpă" and "vătămare corporală din culpă"? Do ReJust (`rejust.ro`) or ROLII (`rolii.ro`)
  publish anonymised judgments with crash locations and circumstances? Note the GDPR implications.
- **Emergency services.** Do ISU Iași or SMURD publish intervention statistics ("descarcerări", "accidente")?
- **Insurance.** Do ASF or BAAR (motor insurance claims, RCA) publish claim statistics per county? Do insurers
  publish accident-prone area reports?
- **Market evidence.** On SICAP / e-licitatie.ro (also available as SEAP datasets on data.gov.ro), find past tenders
  for "audit de siguranță rutieră", "studiu de trafic", "puncte negre", "semaforizare", "PMUD" in Iași and other
  cities. Record the buyer, the value and the date. This proves that someone pays and gives us price anchors.

### Track B: non-official, crowd, academic and commercial-free sources

- **Other local media.** Find every Iași outlet with an RSS feed or WordPress API (`/wp-json/wp/v2/posts`): Radio
  Iași, Iași TV Life, Ziarul de Iași, BZI, 7iasi, iasi4u, Salut Iași, Iași Plus, Știri de Iași, Evenimentul de Iași,
  Agerpres (Iași tag), News.ro, Mediafax. For each one: how far back does the archive go, can you search it, is the
  full text included?
- **Crowd sources.**
  - Facebook groups and pages ("Info Trafic Iași" and similar). Check whether there is any legal, public access; do
    not scrape logged-in content.
  - Reddit r/iasi, Telegram channels, and YouTube dashcam channels from Iași.
  - Waze: the Waze for Cities programme is free for public partners, so record what a city partner would get (this is
    a business path through Primăria). Also check whether there is any public Waze alerts feed.
  - OSM notes, and Mapillary imagery for crossings.
- **Academic sources.** TUIASI (Facultatea de Construcții / Căi Ferate, Drumuri și Poduri) theses and papers on
  accidents, black spots or traffic in Iași. Search Google Scholar, ResearchGate and the "Buletinul Institutului
  Politehnic din Iași". These often contain crash tables per intersection taken from police data.
- **NGOs and civic projects.** Asociația Pietonilor din România, Iași Velo / Bicicliști Iași, "Străzi pentru oameni",
  geo-spatial.org (Romanian open GIS data), Code for Romania, and any existing "harta accidentelor" project in
  Romania. Do they have data or methods we can reuse?
- **Traffic and exposure data with a free tier.**
  - TomTom (Traffic Index, Traffic Stats / MOVE), HERE (free tier), Google (Routes API free tier), Strava Metro (free
    for cities).
  - Iași public transport (CTP Iași GTFS feed, if any) to give tram and bus stop context.
  - For each one: what is free, what needs a contract, and what the licence allows commercially.
- **Weather and light.** Historical weather and sunset times for Iași (Open-Meteo is free). This lets us derive
  "night" and "rain" from the date and hour when the article doesn't say.
- **International comparison.** How do other cities build crash maps (UK STATS19, France BAAC/ONISR open data,
  Germany Unfallatlas)? Use this as a template for the format to request in a Legea 544 request, and as a pitch
  argument ("Romania lacks what France publishes openly").

## 4. Must-check list (both agents, first 20 minutes)

1. PMUD Iași: find the latest version and check whether it has a crash map or table.
2. IPJ Iași and IGPR: any annual road safety report or statistics page with data per county or city.
3. INS TEMPO: the road accident tables and their finest geographic level.
4. CNAIR/DRDP: a black spot list or network safety assessment covering Iași.
5. `portal.just.ro` web service: does it answer, and can you search Iași cases by subject?
6. SICAP: at least three past road safety tenders, with buyer, value and date.

## 5. How to check a source (rules)

- **Verify, don't assume.** A source counts only if you opened it in this session. Record the exact URL, the HTTP
  status, the format (JSON/CSV/PDF/HTML/SOAP), and one real sample record, quoted or saved.
- **Never invent** URLs, datasets, counts, licences or contacts. If you couldn't confirm something, write
  `UNVERIFIED` and say why (timeout, login wall, 403, PDF not found).
- **Prefer APIs and bulk files over HTML.** For HTML, note whether `robots.txt` allows it and how stable the structure
  looks.
- **Be polite.** At least one second between requests per domain, a clear User-Agent, no logins, no CAPTCHA bypass,
  no paywall bypass.
- **Record the licence.** Can we use this commercially, and can we redistribute it? Press text is copyrighted: we may
  store extracted facts and the link, not republish articles. Court and police records contain personal data, so note
  what GDPR means for that source.
- **No repo code changes.** This is research only. Put downloads under `research/samples/<agent>/` (keep each sample
  under 5 MB) and write nothing else in the repo.

## 6. Scoring each source (1–5 per criterion)

| Criterion | 5 means |
|---|---|
| Granularity | Coordinates or intersection for each crash |
| Coverage | All crashes (not just the ones the press picked), municipality and county |
| History | Five or more years |
| Freshness | Updated daily or weekly, automatically reachable |
| Provenance | Official institution, signed or published document |
| Access | Free API or bulk download, no login |
| Commercial licence | Reuse and resale allowed (or facts are reusable) |
| Effort | Usable in under 3 hours of work |

Also give a single verdict: **use now** (demo today), **use for the business** (needs a request, contract or
partnership), or **dead end**.

## 7. Deliverable (one file per agent)

Write `research/sources_<agent>.md` (`claude` or `codex`) with:

1. **Top 5**, ranked, one paragraph each: what it is, the exact URL or endpoint, a sample record, the scores, the
   verdict, and the next step.
2. **Full table** of every source checked, including dead ends. Columns: name, URL, track, format, status, granularity,
   history, licence, scores, verdict, notes.
3. **Legea 544 request drafts**, in Romanian, ready to send: addressee, email or address, and the exact fields asked
   for.
4. **Market evidence**: the tenders found, with buyer, object, value, date and link.
5. **Open questions** that need a human: a phone call, a partnership, a legal opinion.

Time box: 60–90 minutes. Stop earlier if the must-check list turns up something strong, and report it first.

## 8. Romanian search terms

`accidente rutiere Iași statistică`, `puncte negre Iași`, `zone cu risc ridicat accidente Iași`,
`harta accidentelor rutiere România`, `PMUD Iași accidente`, `plan mobilitate urbană durabilă Iași analiză siguranță`,
`raport activitate Serviciul Rutier Iași`, `bilanț IPJ Iași accidente`, `accidente grave județul Iași anul`,
`CNAIR puncte negre`, `evaluare siguranță rutieră rețea CNAIR`, `iRAP România`, `audit siguranță rutieră licitație`,
`studiu de trafic Iași licitație`, `INS accidente rutiere județ`, `ucidere din culpă accident Iași sentință`,
`trecere de pietoni periculoasă Iași`, `intersecție periculoasă Iași`, `Comisia de circulație Iași proces-verbal`,
`HCL Iași semaforizare trecere pietoni`, `Waze for Cities România primărie`, `TUIASI accidente rutiere Iași studiu`.
