# Test vizibil al stării datelor și al calculului

## Scenariul cerut: OSM real + accidente demo

```powershell
python -m risk.scenario
```

Acest test folosește trecerea reală osm-node-3372032447 de pe Aleea Grigore Ghica
Vodă și severitățile evenimentelor demo ev-001, ev-002, ev-003. Infrastructura
vine numai din context/output/observed/iasi/crossings.geojson și raportul geometric;
NU din false_data/crossings.geojson. Nu folosim coordonatele accidentelor demo:
presupunem explicit că un scenariu cu aceste severități ar exista la trecerea aleasă.
Nu este asociere factuală, hotspot observat sau o afirmație că accidentele au fost acolo.

Calcul actual: 9 puncte din accidente demo + 2 trecere nesemaforizată pe 4 benzi
+ 1 școală la 78,9 m + 1 stație la 14,1 m = 13. Distanțele și tagurile sunt reale,
din snapshot-ul OSM; scorul total este numai rezultatul scenariului. Viteza nu
aduce puncte în formula actuală, iar lipsa iluminatului cartografiat rămâne necunoscută.

Pentru a vedea efectul altor date OSM asupra acelorași accidente:

```powershell
python -m risk.scenario --crossing osm-node-6194970559
python -m unittest risk.test_scenario -v
```

A doua trecere este pe Strada Sfântul Lazăr: 9 din aceleași accidente + 2 din
infrastructura sa = 11. Testele verifică faptul că subtotalul accidentelor rămâne
identic și că diferența vine din infrastructura reală, fără a citi infrastructura
sintetică. Comanda nu scrie fișiere și nu publică rezultate în exportul observat.

## Inspecția și demonstrația anterioară

Actualizare: `python -m risk.inspect` citește acum EXCLUSIV datele OSM reale,
într-un format scurt. Nu citește false_data/ și nu afișează accidente sintetice.
Exemplul demonstrativ descris mai jos necesită explicit `--with-demo`:
`python -m risk.inspect --with-demo`. Opțiunile --demo-location și --fixtures
sunt de asemenea selecții explicite ale demonstrației.
Infrastructura contribuie cu maximum 4 puncte per trecere în formula existentă;
nu am definit un scor nou pe zonă. Scorul 12 din exemplul vechi include accidente.

Din rădăcina repository-ului:

```powershell
python -m risk.inspect
```

Comanda doar citește fișierele locale. Nu face cereri de rețea, nu actualizează
OSM și nu scrie exporturi. Datele afișate sunt snapshot-ul salvat, cu intervalul
descărcării. Folosește dependențele deja necesare contextului (`pyproj`, `shapely`).

Prima secțiune arată municipiul și, implicit, celula de 1 km care conține punctul
Palas. În snapshot-ul actual: 76 de treceri, 29 semaforizate, 32 explicit
nesemaforizate și 15 necunoscute; trei configurații nesemaforizate pe 4+ benzi.
Celula include și alte străzi/zone, nu este o delimitare a complexului Palas.
Scorul real este indisponibil, nu zero: nu avem accidente reale integrate.

A doua secțiune, disponibilă numai cu opțiunea explicită de demo, recalculează prioritizarea exclusiv din `false_data/`, fără a o
combina cu infrastructura OSM reală. Selectează automat scorul maxim dintre
hotspot-urile rezultate din asocierea conservatoare. În snapshot-ul actual:

```text
Demo – Podu Roș:
ev-001 grav:  1 + 2 = 3
ev-002 ușor:  1 + 0 = 1
ev-003 deces: 1 + 4 = 5
Subtotal accidente = 9
Trecere fără semafor pe 4+ benzi = +2
Școală la sub 150 m = +0
Stație la sub 100 m = +1
Total demo = 12
```

Fixture-ul de referință declară 13 deoarece include și ev-004. Acesta are
precizie de intersecție lângă un obiect de tip trecere; runnerul îl semnalează
`precision_mismatch` și nu îl asociază automat. Comanda afișează această
diferență, valorile infrastructurii folosite, evenimentele și câmpurile lipsă.
Nu modifică fixture-urile și nu prezintă exemplul drept cea mai periculoasă
locație reală. Viteza nu are pondere în formula actuală.

Alte selecții:

```powershell
python -m risk.inspect --demo-location x-002
python -m risk.inspect --zone utm35n-1000-544000-5222000
python -m risk.inspect --json
```

ID-urile zonelor sunt în `context/output/observed/iasi/zones.csv`. O selecție
necunoscută dă eroare explicită. `--city` și `--fixtures` permit alte directoare
pentru snapshot-uri, păstrând observatul și sinteticul separate; demonstrația
acceptă numai fixture-uri marcate `synthetic` pe schema 2.0.

Verificări automate:

```powershell
python -m unittest risk.test_inspect -v
python -m context.validate_city
```

Prima comandă verifică raportul și calculul pe snapshot-ul actual. A doua
verifică geometria, asocierea unică la zone și reproducerea integrală din cache.
