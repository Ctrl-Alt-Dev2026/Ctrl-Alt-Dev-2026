# Costuri și efecte: ce susțin sursele

Cercetare la 17 octombrie 2026, exclusiv în measures/. Registrul structurat este
research.json, livrat și ca output/three-scenarios/research_evidence.json.
Citire offline, fără cereri și fără scrieri:

```powershell
python -m measures.research
python -m unittest measures.test_rules measures.test_research -v
```

## Aproximări autorizate ulterior de utilizator

Putem folosi media proiectului ca ordin de mărime, fără a o prezenta ca ofertă:

- Semaforizare: 881.010,27 / 3 = 293.670,09 lei pe trecere, rotunjit **aproximativ 294.000 lei fără TVA**, la baza de preț a proiectului din 2020.
- Iluminat: 26.312.475,50 / 188 = 139.959,98 lei pe trecere, rotunjit **aproximativ 140.000 lei**, cotă medie din bugetul proiectului început în 2024; tratamentul TVA nu este explicit pe pagină.

Acestea sunt estimări pentru lucrare, nu costul analizei propuse de catalog.
Sunt incluse în `research_evidence.json`, secțiunea `indicative_unit_estimates`,
și afișate de `python -m measures.research`. Nu reprezintă un interval min/max,
nu sunt ajustate la 2026 și nu se însumează cu baze TVA diferite. Variația între
amplasamente rămâne necunoscută. Pentru celelalte măsuri nu avem încă o bază
suficientă de calcul. Regulile și scorurile nu sunt schimbate.

## Costuri reale publicate, cu limitele lor

| Măsură | Reper din sursă | Ce putem spune |
|---|---|---|
| Iluminat | 26.312.475,50 lei pentru 188 treceri, proiect CJ Cluj început în 2024 | Buget de proiect, nu preț unitar și nu valoare finală executată; TVA nu este explicit pe pagină |
| Semaforizare | 881.010,27 lei fără TVA pentru trei treceri, HCL Cluj 251/2020 | Investiție aprobată istoric, cu mai multe componente; nu ofertă actuală pentru Iași |
| Trecere înălțată | Total general 127.949,70 lei cu TVA istoric 19%, deviz din documentația Sectorului 3, prețuri iulie 2023 | Cantitatea aferentă subtotalului nu este confirmată vizual; nu publicăm lei/trecere |
| Limitator | 99 lei cu TVA pentru un modul DGK200G de cauciuc | Preț afișat de furnizor, fără stoc; nu cost instalat complet și nu tranzacție executată |

Surse directe: [CJ Cluj](https://cjcluj.ro/proiect/iluminarea-trecerilor-pentru-pietoni-pe-drumurile-judetene-din-judetul-cluj-etapa-i/),
[HCL Cluj](https://primariaclujnapoca.ro/consiliu-local/hotarare-de-consiliu/hotararea-251-din-2020/),
[documentație Sector 3](https://www.primarie3.ro/images/uploads/consiliu_local/Punctul_12_din_22.02.2024.pdf),
[furnizor](https://www.protrafic.ro/p/bumper-pentru-viteza-500-x-300-x-45-mm-din-cauciuc-galben).

Nu am găsit un cost românesc izolat și suficient documentat pentru insula de
refugiu. Analiza intersecției, analiza stației și observația în teren necesită
un volum de servicii definit și ofertat; nu primesc prețul unei lucrări.
Nu actualizăm prin inflație și nu convertim monede. Împărțirea proiectelor oferă
mediile orientative de mai sus, fără a fabrica intervale. Nu sunt tarife 2026.

## Reduceri din studii, fără transfer automat

CMF este raportul modelat al accidentelor cu/fără intervenție; CRF=1−CMF.
Exemplu: CMF 0,54 corespunde CRF 46% în condițiile înregistrării, nu 46% din
scor și nu 46% din accidentele citite din presă. Nu cumulăm procentele.

| Măsură | Fișa de studiu | Decizie pentru noi |
|---|---|---|
| Iluminat | [CMF 2873](https://cmfclearinghouse.fhwa.dot.gov/detail.php?facid=2873): 0,30, CRF 70%, pietoni noaptea pe drumuri rurale inițial neiluminate | Respins pentru aceste scenarii urbane; iluminatul nostru este necunoscut |
| Semafor | [CMF 1370](https://cmfclearinghouse.fhwa.dot.gov/detail.php?facid=1370): 0,75, CRF 25%, toate accidentele; Cannot Be Rated | Numai referință bibliografică, nu efect pietonal local |
| Mediană la trecere | [CMF 175](https://cmfclearinghouse.fhwa.dot.gov/detail.php?facid=175): 0,54, CRF 46%, pietoni; arteră urbană/suburbană 3–8 benzi, minimum 15.000 vehicule/zi | Lipsesc traficul și confirmarea medianei; nu orice insulă este echivalentă |
| Trecere înălțată | [CMF 1703](https://cmfclearinghouse.fhwa.dot.gov/detail.php?facid=1703): 0,92, CRF 8%, pietoni; Cannot Be Rated | Referință cu limite importante, nu procent universal |
| Speed hump | [CMF 132](https://cmfclearinghouse.fhwa.dot.gov/detail.php?facid=132): 0,60, CRF 40%, accidente cu vătămări pe drumuri locale cu două benzi | Nu se aplică celor trei drumuri cu patru benzi și nu este automat efectul unui modul scurt de cauciuc |

Erorile standard, studiile și condițiile sunt salvate unde au fost disponibile.
Nu am dedus stele de calitate din punctajele numerice ale paginilor. Pentru
alegerea unui CMF trebuie confruntate intervenția, tipul accidentelor, geometria,
traficul și calitatea studiului: [ghidul Clearinghouse](https://cmfclearinghouse.fhwa.dot.gov/faqs.php).

## Acces la dovezi și ce mai lipsește

Unele pagini CMF și HCL au răspuns cu timeout/502 la deschidere directă; datele
lor au fost citite din rezultatele indexate ale aceleiași surse oficiale.
PDF-ul Sectorului 3 a fost identificat/deschis, dar verificarea vizuală a
devizului nu a reușit. Registrul marchează explicit aceste limite. Nu pretindem
arhivarea integrală sau verificarea vizuală a documentelor. Înainte de folosirea
unui preț în ofertă trebuie revăzut originalul, cantitățile și devizul complet.

Catalogul păstrează costurile și reducerile null: sursele cercetate nu justifică
încă o estimare transferabilă pentru măsurile candidate din cele trei locații.
Acestea sunt în plus măsuri de analiză; o analiză nu are efectul lucrării pe care
o poate recomanda. Efectele nu sunt aplicate scenariilor și nu schimbă scorurile.

Pentru următoarea etapă: devize/oferte comparabile în lei pentru amplasamentele
selectate; inventarul infrastructurii existente și fluxuri măsurate; alegerea
exactă a intervenției; evaluarea aplicabilității studiului. F2/F3 au acum dovezi
și lipsuri explicite, dar nu sunt finalizate pentru costarea unui pilot Iași.
