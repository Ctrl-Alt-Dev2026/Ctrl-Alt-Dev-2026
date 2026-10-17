# Context OSM Palas — Persoana 4

Actualizare: extinderea municipală este finalizată în `context/output/observed/iasi/`.
Rezultatele și reproducerea ei sunt în `context/CITY.md`; acest document păstrează
detaliile pilotului Palas.

## Punct atins

Colectare reală finalizată pe 17 octombrie 2026: trei răspunsuri Overpass separate,
757 obiecte highway (inclusiv căi pietonale, care nu sunt folosite drept carosabil),
5 școli/grădinițe și 17 obiecte de transport public. Acestea nu sunt numere de
instituții sau stații unice: o stație poate avea platformă și stop_position.
Răspunsurile brute și proveniența sunt în `context/cache/palas/`.

Output: `context/output/observed/palas/crossings.geojson` și raportul separat
`geometry_report.json`. Schema proprietăților GeoJSON rămâne cea existentă.

- 27/27 treceri au drumuri cu nod comun și coordonate compatibile.
- 12 au număr de benzi explicit și coerent între drumurile conectate.
- 4 au geometria unei școli la mai puțin de 150 m.
- 6 au un obiect de transport public la mai puțin de 100 m.
- Nicio geometrie POI nu a fost respinsă în acest răspuns real.

Celelalte valori de proximitate rămân null: nu există o dovadă suficientă pentru
false. Numărul de benzi descrie way-ul conectat, nu o măsurătoare în teren a
întregii traversări. Carosabilele separate nu sunt însumate. Două cazuri concrete
de neconcordanță sunt nodurile 6194970558 (3/4/1 benzi) și 11553251503 (4/2/4).

## Reproducere

Dependențe locale verificate: requests 2.34.2, shapely 2.2.0, pyproj 3.8.0.
Nu am modificat requirements-urile comune. Dacă lipsesc pe alt laptop:

```powershell
python -m pip install requests==2.34.2 shapely==2.2.0 pyproj==3.8.0
python -m context.collect --offline
python -m context.enrich --crossing-downloaded 2026-10-17 --output context/output/observed/palas-rerun
python -m unittest context.test_context risk.test_pipeline -v
```

Pentru prima colectare: `python -m context.collect`. Un cache prezent este
reutilizat fără rețea. Pentru o actualizare deliberată, selectează alt director
prin `--cache`; păstrează vechiul snapshot. Endpoint-ul poate fi schimbat cu
`--endpoint https://.../api/interpreter`. Nu există presupunerea că maps.mail.ru
va fi disponibil permanent. Timeout-ul este limitat și nu se fac retry-uri în
buclă. Un răspuns HTTP eronat, JSON invalid sau cu remark Overpass nu intră în
cache. `--offline` eșuează explicit dacă lipsește o interogare.

Output-ul trebuie să fie un director nou, pentru a proteja exporturile existente.
Data trecerilor este cea comunicată pentru experimentul inițial; fișierul brut
nu avea timestamp propriu. Datele noilor cereri sunt păstrate separat, cu fus UTC
și timestamp_osm_base. Nu prezentăm toate datele ca fiind descărcate simultan.

## Cum verificăm geometria

Folosim UTM 35N (EPSG:32635), pentru distanțe în metri. Aria interogată este mai
mare decât aria trecerilor cu peste 200 m pe fiecare latură, pentru vecinătăți.
Un drum este eligibil numai dacă este un highway carosabil, conține ID-ul nodului
trecerii și coordonata acelui nod este la cel mult 0,5 m de coordonata inițială.
Un pasaj care doar intersectează linia în plan nu trece verificarea de nod comun.
Lipsa unui tag pe unul dintre drumurile conectate blochează consensul acelui tag.

Pentru școli folosim punctul sau poligonul complet disponibil, inclusiv contururi
de relații multipolygon. Geometriile incomplete nu sunt înlocuite cu centre.
Grădinițele sunt în raport, separat de bonusul pentru școală din formula comună.
Pentru transport folosim obiectele bus_stop, platform, stop_position și tram_stop;
numărul lor nu reprezintă automat numărul de stații distincte.

Tagurile brute ale drumului, inclusiv maxspeed/oneway/lit când există, se păstrează
în raport. Iluminatul drumului nu devine automat iluminat al trecerii. tip_strada
primește clasificarea OSM reală, de exemplu secondary; nu inventăm o conversie la
„bulevard”. Regula pentru lanes urmează definiția OSM: număr total de benzi pentru
trafic motorizat pe way, fără însumare între way-uri.
Surse: https://wiki.openstreetmap.org/wiki/Key:lanes și
https://dev.overpass-api.de/blog/loop_and_group.html .

## Distanța până la obiectivul Persoanei 4

Baza de scor offline și pilotul de context Palas sunt funcționale. Urmează
integrarea unui snapshot de accidente reale de la Persoana 3, verificarea
asocierilor ambigue și generarea hotspots observate. Runnerul de risc actual
acceptă intenționat numai fixture-uri sintetice; nu combina aceste accidente cu
exportul OSM observat. Acest pas nu a extins aria, nu a generat intersecții noi,
nu a implementat recomandări și nu a modificat componente comune.
