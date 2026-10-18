# Fluxul aplicației — surse, AI, geolocalizare și analiză

Diagrama descrie implementarea actuală. Se poate vizualiza în preview-ul Markdown
cu suport Mermaid sau direct pe GitHub.

**Legendă:** albastru = procesare fără AI; portocaliu = apel nou la model;
mov = reutilizarea unui răspuns AI salvat. Săgețile punctate indică pornirea
separată a pasului AI de către operator.

```mermaid
flowchart TB
    TIMER["Colector periodic<br/>La pornire și la 30 min, când este activ"]

    subgraph SOURCES["1. Colectarea și sursele — fără AI"]
        ISU["ISU Iași<br/>Listări și PDF-uri noi prin HTTP"]
        PDF["pypdf: PDF → text<br/>Reguli: relevanță și extragerea parametrilor"]
        PRESS["BZI / Ziarul de Iași<br/>scraping.scraper_stiri"]
        CSV["Articole colectate în CSV<br/>Prefiltre de relevanță"]
        IPJ["IPJ prin PMUD<br/>CSV local: totaluri pe artere, 2020–2021<br/>Nu este un flux live direct IPJ"]
        ISU --> PDF
        PRESS --> CSV
    end

    TIMER --> ISU
    TIMER --> PRESS

    subgraph PRESS_PROCESSING["2. Interpretarea articolelor de presă"]
        CACHE{"Există răspuns Claude<br/>salvat pentru articol?"}
        REPLAY["Replay AI: verdict de relevanță<br/>și parametrii extrași cu citate"]
        RELEVANT{"Verdict:<br/>accident_actual?"}
        EXCLUDED["Exclus din evenimente<br/>Urmare judiciară / alt subiect / neclar"]
        VALIDATE["Python: verificarea citatelor<br/>și a formatelor câmpurilor"]
        FALLBACK["Reguli Python provizorii<br/>Pentru articole fără răspuns AI"]
        CSV --> CACHE
        CACHE -->|Da| REPLAY
        CACHE -->|Nu| FALLBACK
        REPLAY --> RELEVANT
        RELEVANT -->|Da| VALIDATE
        RELEVANT -->|Nu| EXCLUDED
    end

    subgraph GEO["3. Evenimente și localizare — fără AI"]
        EVENTS["Deduplicare în interiorul surselor<br/>ISU și presa rămân separate<br/>Posibile corespondențe sunt doar marcate"]
        OSM["Date OSM locale<br/>Index, aliasuri, limită administrativă,<br/>noduri cunoscute și geometria străzilor"]
        GEOCODE["Modulul coordonate<br/>resolver.rezolva: localizare și precizie"]
        STREETS["Agregare pe stradă și sursă<br/>Potrivirea și geometriile existente"]
        H3["H3, rezoluția 9<br/>Numai accidente cu locație precisă<br/>Fără celule atribuite accidentelor pe stradă"]
        CONTEXT["Context OSM descriptiv al străzii<br/>Fără asocierea infrastructurii la accidente"]
        PDF --> EVENTS
        VALIDATE --> EVENTS
        FALLBACK --> EVENTS
        EVENTS --> GEOCODE
        OSM --> GEOCODE
        GEOCODE --> STREETS
        GEOCODE --> H3
        OSM --> CONTEXT
        IPJ --> STREETS
    end

    subgraph ANALYSIS["4. Analiză și recomandări"]
        SCORE["Python: scor și statistici<br/>N + 4 × evenimente cu deces + 2 × evenimente grave<br/>Context 0 pentru scorul străzii<br/>Ore, zi/noapte și cauze: statistici separate"]
        RULES["Recomandări prin reguli Python<br/>Bazate pe cauzele raportate"]
        COSTS["Repere unitare documentate<br/>Fără AI; cost necunoscut dacă nu există sursă<br/>Fără număr presupus de lucrări sau cost total"]
        ADVICE["Replay sugestii Claude pe stradă<br/>Măsuri de studiat din catalog<br/>Evenimente citate și indicator de actualitate"]
        STREETS --> SCORE
        STREETS --> RULES
        COSTS --> RULES
    end

    subgraph AI_STEP["Pas AI separat — pornit de operator prin npm run ai"]
        OPERATOR["Operator: npm run ai<br/>Nu este lansat de colectorul periodic"]
        ARTICLE_AI["Claude: relevanță și extracție<br/>în același răspuns structurat<br/>Primește textul colectat; fără căutare web"]
        ARTICLE_CACHE["isu/seed/ai/articole.json<br/>Răspunsuri salvate pentru replay"]
        CATALOG["Catalogul de măsuri<br/>Nu permite măsuri inventate"]
        STREET_AI["Claude: studii pe stradă<br/>Evenimente + semnale + PMUD + catalog<br/>Fără costuri sau amplasamente concrete"]
        STREET_CACHE["isu/seed/ai/strazi.json<br/>Sugestii salvate pentru replay"]
        OPERATOR -.-> ARTICLE_AI
        OPERATOR -.-> STREET_AI
        CSV --> ARTICLE_AI
        ARTICLE_AI --> ARTICLE_CACHE
        ARTICLE_CACHE --> CACHE
        STREETS --> STREET_AI
        CATALOG --> STREET_AI
        STREET_AI --> STREET_CACHE
        STREET_CACHE --> ADVICE
    end

    subgraph DISPLAY["5. Persistență și afișare — fără AI"]
        DATASET["Dataset derivat<br/>Evenimente, străzi, scoruri, statistici,<br/>context, H3 și recomandări"]
        DB["SQLite<br/>Documente, rulări și dataset-uri"]
        API["Backend FastAPI<br/>/api/v1/live/status<br/>/api/v1/live/dataset"]
        UI["Angular + hartă<br/>Geometria străzii pentru locații grosiere<br/>Puncte / H3 numai pentru locații precise<br/>Surse și rezultate AI etichetate separat"]
        SCORE --> DATASET
        RULES --> DATASET
        ADVICE --> DATASET
        CONTEXT --> DATASET
        H3 --> DATASET
        DATASET --> DB
        DB --> API
        API --> UI
    end

    classDef deterministic fill:#e0f2fe,stroke:#0369a1,color:#0c4a6e;
    classDef inference fill:#ffedd5,stroke:#c2410c,color:#7c2d12;
    classDef replay fill:#f3e8ff,stroke:#7e22ce,color:#581c87;
    classDef storage fill:#f1f5f9,stroke:#64748b,color:#0f172a;
    class TIMER,ISU,PDF,PRESS,CSV,IPJ,VALIDATE,FALLBACK,EVENTS,GEOCODE,STREETS,H3,CONTEXT,SCORE,RULES,COSTS,API,UI deterministic;
    class ARTICLE_AI,STREET_AI inference;
    class REPLAY,ADVICE replay;
    class OSM,ARTICLE_CACHE,STREET_CACHE,CATALOG,DATASET,DB storage;
```

Colectarea periodică reutilizează răspunsurile AI salvate. `npm run ai`
procesează articolele noi, reconstruiește dataset-ul, generează/actualizează
sugestiile eligibile și salvează rezultatele în SQLite și în `isu/seed/`.
Modelul configurat implicit în `isu/ai.py` este `claude-haiku-5-5`.

IPJ/PMUD rămâne un total separat; nu fabricăm evenimente individuale, ore sau
cauze pentru acel tabel. Scorul prioritizează evenimentele documentate și nu
reprezintă probabilitatea unui accident. Recomandările pe stradă sunt studii;
o modificare de trecere sau amplasarea unui limitator cere un loc verificat și
evaluare tehnică.

Diagrama arată fluxul existent, inclusiv regulile provizorii. Problemele de
prefiltrare, validare, deduplicare și verificare a nodurilor OSM sunt descrise
în [auditul fluxului](../risk/PIPELINE_AUDIT.md); nu sunt prezentate ca rezolvate.

Puncte de intrare în cod: [colector periodic](../isu/live.py),
[colectare ISU](../isu/collect.py), [pas AI](../isu/ai.py),
[asamblare și geolocalizare](../isu/build.py),
[analiză pe străzi](../risk/streets.py), [API live](../api/live_router.py).
