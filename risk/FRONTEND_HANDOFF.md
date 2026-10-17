# Integrarea datelor Persoanei 4

## Actualizare după push-ul 7c1a193

Frontend-ul implicit folosește acum HTTP și publicații versionate. Setul mixt
de mai jos este destinat exclusiv preview-ului static cu configurația mock,
nu importului în publicațiile backend. Backend-ul separă strict synthetic și
observed și nu acceptă accidente sintetice cu infrastructură OSM reală.
Helper-ul `python -m risk.preview` compilează explicit development,mock într-un
director nou frontend-app-mock, separat de compilarea HTTP și de copia veche.

Pentru integrarea observată, backend-ul consumă deja exportul nostru original
`context/output/observed/iasi/` și apelează risk.pipeline.score_location.
GET /api/v1/publication-context?data_mode=observed&limit=200&offset=0 oferă
infrastructura cu paginare: citește toate paginile până la total. Acest catalog
este separat de /api/v1/locations.geojson, care descrie locațiile publicației,
nu inventarul complet de treceri. Stratul OSM trebuie să fie independent de
existența unei publicații și să fie etichetat ca infrastructură reală.

Nu există încă o rută H3 în noul backend. Fișierul H3 al scenariului rămâne
pentru mock; integrarea H3 observată trebuie legată de aceleași evenimente și
aceeași versiune de publicație, cu acordul colegului de backend.
Suplimentul de o trecere și intersecțiile candidate NU sunt acceptate automat
de validatorul observed actual: acesta cere tip trecere și highway=crossing în
dovezi. Nu se schimbă tagurile sursă pentru a trece validarea. Rămân straturi
opționale distincte până la o integrare agreată.

## Setul de date

Folosește întregul director `risk/output/frontend-scenario/data/` ca un singur
set. Conține 1.210 treceri OSM reale, 9 accidente sintetice și 3 hotspot-uri de
scenariu. Nu amesteca accidents/hotspots din false_data/ cu aceste crossings.
Păstrează inclusiv listele goale articles.json, measures.json și cameras.json:
împiedică folosirea accidentală a fixture-urilor vechi.

Frontend-ul actual sincronizează data/ sau false_data/ la npm start/build;
nu selectează automat acest director. Adaugă în mecanismul tău de încărcare o
opțiune explicită pentru acest dataset și servește fișierele la /data/.
Include și accidents_h3.geojson în copiere/încărcare. Nu este suficient să copiezi
manual fișierele înainte de npm start, care le poate suprascrie.
Pentru preview fără modificări frontend: `python -m risk.preview`, port 4201.

## Pași de implementat în frontend

1. **Treceri OSM:** strat separat de puncte din toate features ale
   crossings.geojson, cu toggle „Treceri OSM”. Folosește geometry.coordinates
   în ordinea [lon, lat], ID-ul din properties.id și culoare neutră. Stratul
   rămâne vizibil independent de filtrele accidentelor. Nu crea hotspot-uri
   artificiale pentru trecerile fără accidente.
2. **Popup trecere:** afișează numele/ID-ul, semafor, benzi, iluminat,
   școală și stație apropiată din proprietățile disponibile. null = „necunoscut”,
   nu false. Fără scor asociat: „scor indisponibil”, nu 0 sau „sigur”.
3. **Scenarii:** păstrează stratul existent de hotspot-uri deasupra punctelor.
   Leagă hotspot.crossing_id de crossing.properties.id și event_ids de
   accidents.event_id. Afișează scor, componente_scor, explicatie, date_lipsa și
   distribuția pe_ore. Nu recalcula formula în frontend. Rezultatele așteptate:
   Grigore Ghica Vodă 13, Dacia 11, Sfântul Lazăr 9.
4. **H3:** încarcă accidents_h3.geojson și desenează poligoanele existente ca
   coloane extrudate, de exemplu GeoJsonLayer cu extruded=true și înălțime
   proporțională cu properties.nr_evenimente. Sunt celule H3 r9; nu regrupa
   punctele cu HexagonLayer radius=140. Popup: h3, nr_evenimente și statisticile
   din properties. Înălțimea exprimă număr de accidente demo, nu scor de risc.
5. **Etichetare:** afișează manifest.avertisment permanent sau foarte vizibil:
   „SCENARIU: OSM real + accidente sintetice”. Păstrează marcajele SCENARIU
   în fișe; nu prezenta evenimentele ca știri ori accidente reale verificate.

## Suplimente OSM opționale

În `context/output/observed/index-review-complete/`:

- additional_crossings.geojson: o trecere suplimentară confirmată. Pentru
  afișare, concatenează features cu crossings și deduplică după properties.id:
  rezultatul este 1.211 treceri. Nu are accidente/scor atribuite.
- intersection_candidates.geojson: 1.569 noduri cu tip=intersectie. Strat separat,
  opțional, inițial oprit, etichetat „Intersecții candidate — nevalidate manual”.
  Nu le introduce în scoruri/hotspot-uri și nu le confunda cu trecerile.
- intersection_review.csv și review_report.json: dovezi pentru audit; nu sunt
  necesare la încărcarea hărții. confirmed_additional_crossings_raw.geojson
  păstrează tagurile sursă. crossing_candidates.geojson este gol în acest set.

## Verificare finală

- 1.210 puncte de trecere, sau 1.211 cu suplimentul, cu ID-uri unice.
- 3 scenarii, 9 accidente demo, scoruri 13/11/9.
- Suma nr_evenimente din celulele H3 este 9.
- Toggle-ul și filtrele accidentelor nu ascund involuntar trecerile OSM.
- Valorile null rămân necunoscute; avertismentul de scenariu este vizibil.
- Candidații de intersecție rămân separați și fără scor.
