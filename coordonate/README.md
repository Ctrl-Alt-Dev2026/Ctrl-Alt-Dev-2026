# `coordonate/`: aria C, coordonatele accidentelor

Ghid de integrare pentru oameni și agenți. Modulul primește evenimentele extrase de persoana 2 (`ai/`) și completează **doar** patru câmpuri din contractul `accidents.json`: `lat`, `lon`, `precizie_loc` și `in_iasi`. Toate localizările vin dintr-un index OpenStreetMap local, așa că la rulare nu se face nicio cerere în rețea și nicio coordonată nu e scrisă de mână.

## Pe scurt pentru agenți

```powershell
# rulare neinteractivă (pentru scripturi / run_all.py)
python -m coordonate ruleaza --intrare ai/work/results/hybrid/accidents.json
# rezultat: coordonate/out/<data_mode>/accidents.json + raport_coordonate.json
```

- **Python:** rezolvarea folosește doar biblioteca standard. Merge cu orice Python ≥ 3.12, inclusiv fără `.venv`. Doar `descarca` are nevoie de osmnx (vezi [Actualizarea datelor OSM](#actualizarea-datelor-osm)).
- **Directorul de lucru:** rădăcina repo-ului (`python -m coordonate ...`).
- **Fișierele mock din `false_data/` nu se scriu niciodată.** Scrierea e refuzată în cod (`ScriereInterzisa`).
- **Nu modificați** `lat`/`lon` de mână în ieșire. Corecturile se fac prin noduri cunoscute verificate, alias-uri sau corectarea `loc_text` la sursă (persoana 2), apoi rulați din nou.
- **Datele OSM** (`date_referinta/osm/`) și ieșirile (`out/`) sunt pe Git. Cache-ul brut osmnx (`cache/`, ~20 MB) e ignorat.

## Comenzi

| Comandă | Ce face |
|---|---|
| `python -m coordonate ruleaza` | Cere interactiv calea către `accidents.json` (fișier sau folder; Enter = sugestia). |
| `python -m coordonate ruleaza --intrare <fișier\|folder>` | Rulare fără întrebări. Un folder înseamnă `<folder>/accidents.json`. |
| `python -m coordonate noduri [--propune]` | Starea nodurilor cunoscute (Podu Roș...) și link-urile de verificat. `--propune` regenerează propunerile din OSM, păstrând intrările deja verificate. |
| `python -m coordonate fisa --intrare coordonate/out/observed [--hotspots data/hotspots.json --top 10]` | Fișa de verificare manuală (duminică, V1–V2): `.json` + `.md`, cu link-uri OSM/Street View/Mapillary. |
| `python -m coordonate autotest` | 43 de verificări: cerințele din plan (ev-016, ev-017), regulile validatorului din `api/` și protecția mock-urilor. Nu scrie nimic. |
| `.venv\Scripts\python -m coordonate descarca [--forteaza]` | Reconstruiește indexul OSM (osmnx + Overpass, ~5 min). |

Opțiuni pentru `ruleaza`:

| Opțiune | Implicit | Rol |
|---|---|---|
| `--iesire` | `coordonate/out/<data_mode>/accidents.json` | Raportul se scrie în același folder. |
| `--mod toate\|lipsa` | `toate` | `lipsa` procesează doar evenimentele fără coordonate. |
| `--forteaza` | oprit | Rescrie și evenimentele cu `verificat: true` (implicit sunt sărite). |
| `--mod-date synthetic\|observed` | — | Doar dacă intrarea nu are `manifest.json` alături și nici câmpul `data_mode`. Nu poate contrazice datele. |
| `--limita N`, `--verbos` | — | Pentru depanare. |

**Coduri de ieșire:**
- `0`: ok.
- `2`: intrare lipsă sau invalidă, index OSM lipsă, ori `--intrare` lipsă la o rulare neinteractivă.
- `3`: refuz de siguranță: date `synthetic` și `observed` amestecate, `data_mode` necunoscut sau ieșire în `false_data/`.
- `autotest` întoarce `1` dacă pică o verificare.

## Intrarea

Formatul produs de `ai/` (`python -m ai --pipelines hybrid`, implicit în `ai/work/results/<pipeline>/accidents.json`) este o listă de evenimente cu `lat`, `lon`, `precizie_loc` și `in_iasi` puse pe `null`. Modulul citește:

- `loc_text`: singura sursă pentru localizare, așa cum a fost extras (ex. „pe Bd. Independenței”, „în zona Gării”). Câmpul `dovezi` nu e folosit, prin decizie de echipă. Un `loc_text: null` duce la `vag`, cu `in_iasi: null`.
- `data_mode`: din fiecare eveniment și/sau din `manifest.json` aflat lângă fișier. Orice amestec oprește rularea.
- `verificat`: evenimentele cu `true` nu se recalculează fără `--forteaza`.

Toate celelalte câmpuri (inclusiv cele extra din `ai/`: `issues`, `evidence_refs`, `loc_normalizat` etc.) se păstrează neschimbate. Câmpurile din contract sunt puse primele, în ordinea din plan.

## Ieșirea

`coordonate/out/<data_mode>/`:

| Fișier | Conținut | Cine îl folosește |
|---|---|---|
| `accidents.json` | Aceleași evenimente, cu cele 4 câmpuri completate | persoanele 4 (scor) și 6 (hartă), `run_all.py` |
| `raport_coordonate.json` | Pentru fiecare eveniment: metoda, încrederea, obiectele OSM, avertismente, ce e de verificat; plus statistici | verificarea manuală, manifestul, depanarea |
| `fisa_verificare.{json,md}` | Generată de `fisa` | verificarea de duminică |

### Câmpurile scrise

| Câmp | Valori | Garanții |
|---|---|---|
| `precizie_loc` | `trecere` \| `intersectie` \| `segment` \| `strada` \| `vag` | Niciodată `null`; validatorul din `api/` respinge `null`. |
| `lat`, `lon` | float WGS84 sau `null` | Ambele setate sau ambele `null`. `vag` nu are niciodată coordonate. Orice altă precizie are întotdeauna. |
| `in_iasi` | `true` \| `false` \| `null` | Din poligonul OSM al municipiului (relation/1207838). Pentru `vag` se calculează din punctul zonei sau localității. `null` = nu știm. |

Coordonatele sunt în câmpuri separate. Pentru GeoJSON/deck.gl, ordinea este **[lon, lat]**.

### Ce înseamnă fiecare precizie

| `precizie_loc` | Coordonate | Intră în clasament* | Când apare (`metoda` în raport) |
|---|---|---|---|
| `intersectie` | da | da | Cele două străzi numite au exact un **nod comun** în OSM (`nod_comun_osm`), sau „intersecția/trecerea de la X”, unde X e un nod cunoscut **verificat** (`nod_cunoscut_verificat`). |
| `trecere` | da | da | Singura trecere OSM de pe strada numită (`trecere_unica_pe_strada`), singura de pe stradă în 250 m de reper (`trecere_pe_strada_langa_reper`) sau singura în 90 m de reper (`trecere_unica_langa_reper`). |
| `segment` | da | da | Stradă + număr din adresele OSM (`strada_si_numar_osm`); stradă + reper, cu punctul străzii cel mai apropiat de reper (`strada_langa_reper`); stație numită, aflată la marginea drumului (`statie_osm`). |
| `strada` | da (aproximativ) | **nu** | Știm doar strada; punctul e un nod reprezentativ al ei (`strada_osm`). Sau un reper întins fără stradă, ex. un mall ori o școală (`reper_osm`). Pe hartă se afișează ca „localizat aproximativ”. |
| `vag` | **nu** | **nu** | Doar cartier/zonă (`zona_osm`), doar localitate (`localitate_osm`) sau nimic găsit (`nerezolvat`). |

\*Regula din secțiunea 5 a planului: în clasament intră doar `trecere`/`intersectie`/`segment` **și** `in_iasi: true`. Constanta e `config.PRECIZII_IN_CLASAMENT`.

**`incredere`** (în raport):
- `ridicata`: nod comun, adresă sau trecere unică pe stradă;
- `medie`: deducție din reper sau stradă;
- `scazuta`: zonă sau nimic.

### Reguli de interpretare a textului

- **„pe X”, „de pe X”:** X se caută întâi ca stradă („de pe Alexandru cel Bun” → Bulevardul Alexandru cel Bun).
- **„din X”, „în X”, „zona X”:** dacă X e cartier în OSM, rămâne zonă (`vag`), chiar dacă există o gară sau o stație cu același nume. Excepție: textul spune explicit „gara”, „stația” etc.
- **„de la X”, „la X”:** X se caută întâi în nodurile cunoscute, apoi ca zonă.
- **Cuvinte de reper explicit:** „stația X”, „Spitalul X”, „școala X”, „mall-ul X”...; căutarea se face numai în clasele OSM potrivite.
- **Ambiguitate:** mai multe treceri, străzi omonime în sate diferite sau repere omonime depărtate nu duc la o alegere. Precizia coboară și raportul notează întrebarea în `de_verificat`.
- **Altă localitate:** dacă textul numește o localitate din afara municipiului („în Valea Lupului”), căutarea se restrânge la 3 km în jurul ei. Rezultatul are `in_iasi: false`, plus `unitate_admin` în raport. Decizia echipei: locațiile conexe primesc coordonate, dar nu intră în clasament.
- **Alias-uri confirmate:** sunt în `date_referinta/alias_nume.json`, de exemplu `"repere": {"palas": "Palas Mall"}`. Se aplică doar la repere, nu la străzi.

### Statistici pentru manifest

`raport_coordonate.json` → `statistici`:
- `nr_evenimente`, `nr_localizate_precis` (precizie de clasament + `in_iasi: true` + coordonate);
- `nr_cu_coordonate`, `nr_fara_coordonate`;
- `nr_in_iasi`, `nr_in_afara_iasi`, `nr_in_iasi_necunoscut`;
- `pe_precizie`, `pe_metoda`, `pe_incredere`;
- `nr_de_verificat_manual`, `noduri_neverificate_potrivite`.

`nr_localizate_precis` folosește aceeași definiție ca `api/validate_fixtures.py`. Modulul **nu scrie** `manifest.json`, care are un singur proprietar (persoana 1). Comanda `ruleaza` afișează doar valorile propuse.

## Integrare

### `run_all.py` (persoana 1)

```python
import subprocess, sys
r = subprocess.run([sys.executable, "-m", "coordonate", "ruleaza",
                    "--intrare", "ai/work/results/hybrid/accidents.json"])
if r.returncode != 0:
    raise SystemExit(f"coordonate a eșuat (cod {r.returncode})")
# apoi: coordonate/out/<data_mode>/accidents.json -> data/accidents.json
```

### Din Python (fără subprocess)

```python
from coordonate import granita
from coordonate.aplica import aplica, citeste_json, scrie_json
from coordonate.index_osm import IndexOSM
from coordonate.noduri import NoduriCunoscute
from coordonate.rezolvare import Rezolvator

rez = Rezolvator(IndexOSM.incarca(), granita.incarca(), NoduriCunoscute.incarca())

r = rez.rezolva("pe Bulevardul Socola")      # un singur text
r.precizie_loc, r.lat, r.lon, r.in_iasi       # 'strada', 47.144385, 27.5958, True
r.ca_dict()                                    # înregistrarea completă din raport

evenimente = citeste_json("ai/work/results/hybrid/accidents.json")
completate, raport, _ = aplica(evenimente, rez)   # mod="toate", forteaza=False
scrie_json("coordonate/out/observed/accidents.json", completate)
scrie_json("coordonate/out/observed/raport_coordonate.json", raport.ca_dict())
```

`IndexOSM.incarca()` se încarcă o singură dată pe proces (~1 s) și e reutilizat. Ridică `IndexLipsa` dacă fișierul lipsește.

### Persoana 4 (scor, E1) și persoana 6 (hartă)

- Pentru atașarea la treceri și pentru scor, filtrați: `precizie_loc in ("trecere", "intersectie", "segment")` și `in_iasi is True`.
- `strada` are coordonate aproximative: apare pe hartă cu stil „localizat aproximativ”, dar nu se atașează la treceri.
- `vag` nu are punct. Se numără doar în totaluri, nu pe hartă.

### Ecranul de import (persoana 2 + 6)

Pentru un eveniment nou aprobat:
- se apelează `rez.rezolva(loc_text)` cu un `Rezolvator` creat o singură dată la pornirea serverului;
- se copiază pe eveniment doar cele 4 câmpuri;
- `r.de_verificat` și `r.avertismente` merită afișate operatorului.

## Noduri cunoscute (Podu Roș, Piața Unirii...)

`date_referinta/noduri_cunoscute.json` leagă nume folosite de presă de un **nod OSM real** (`node/<id>`). Fișierul nu conține coordonate.

- Propunerile sunt generate automat din index (`noduri --propune`).
- **Un nod cu `verificat: false` nu e folosit.** Rularea afișează doar `>>> VERIFICARE NECESARĂ`, iar raportul îl listează în `noduri_neverificate_potrivite`.
- Pentru validare:
  1. deschideți `link`;
  2. dacă e corect, puneți `verificat: true`, `verificat_de`, `verificat_la`; dacă e greșit, înlocuiți `osm` sau ștergeți intrarea;
  3. rulați din nou `ruleaza`.
- **Stare la 17.10.2026:** 7 propuse, 0 verificate. Responsabil de verificare: persoana 3. Târgu Cucului, Piața Voievozilor și Piața Gării nu au fost găsite automat în OSM.

## Actualizarea datelor OSM

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r coordonate/requirements.txt
.venv\Scripts\python -m coordonate descarca --forteaza
.venv\Scripts\python -m coordonate noduri --propune   # dacă s-au schimbat id-urile OSM
.venv\Scripts\python -m coordonate autotest
```

- **Zona descărcată:** municipiul Iași și localitățile conexe (`config.BBOX_DATE`: 47.00–47.35 N, 27.30–27.85 E).
- **Conținutul indexului:**
  - străzile cu nume, cu nodurile OSM reale;
  - trecerile (`highway=crossing`), reperele cu nume, cartierele și localitățile;
  - adresele cu număr și granițele `admin_level=8`.
- **Indexul curent:** descărcat pe 17.10.2026, ~1,7 MB pe Git. Conține 1.834 de străzi, 1.614 treceri, 5.160 de repere, 288 de locuri și 45 de unități administrative.
- **Overpass public răspunde des cu 502/504.** Descărcarea reîncearcă automat cu pauze dublate. Ce s-a descărcat rămâne în `coordonate/cache/osmnx`, deci o reluare continuă de unde a rămas.
- **Atribuire obligatorie:** Date © OpenStreetMap contributors, ODbL 1.0.

## Structura

| Fișier | Rol |
|---|---|
| `cli.py`, `__main__.py` | Linia de comandă, promptul pentru cale, protecțiile de `data_mode` |
| `aplica.py` | Aplicarea pe listă, statistici, scriere atomică, refuzul `false_data/` |
| `rezolvare.py` | Regulile de precizie (ordinea din tabelul de mai sus) |
| `parser_loc.py` | Citirea rolurilor din `loc_text` (stradă, zonă, reper, intersecție, număr) |
| `index_osm.py` | Încărcarea indexului și căutările: străzi, nod comun, treceri, repere, locuri, adrese |
| `granita.py` | `in_iasi` și comuna în care cade un punct |
| `noduri.py` | Nodurile cunoscute: propunere, încărcare, raport |
| `normalizare.py` | „Bd.” = „B-dul” = „Bulevardul”, chei fără diacritice, alias-uri |
| `descarca.py` | Construirea indexului cu osmnx (singurul loc cu rețea) |
| `verificare.py` | Fișa de verificare manuală |
| `autotest.py` | Verificările cerute de plan și de validatorul din `api/` |
| `config.py` | Căi, zona descărcată, raze, liste de precizii |
| `date_referinta/` | `osm/index_osm.json.gz`, `osm/unitati_admin.geojson`, `noduri_cunoscute.json`, `alias_nume.json` |

## Limite cunoscute

- **Parserul e bazat pe reguli pentru formulări din presa românească.** Formulările neobișnuite duc la o precizie mai mică și la o notă în `de_verificat`, nu la un punct ghicit.
- **Completitudinea OSM:** o trecere neetichetată în OSM nu poate deveni `trecere`. Lipsa unui tag nu înseamnă lipsa obiectului.
- **Pe datele mock:** 15 din 17 evenimente ies `vag`, pentru că textele numesc doar cartiere sau „Bulevardul Demo”, care nu există. Coordonatele din `false_data/accidents.json` au fost inventate pentru test și nu sunt o referință.
- **Punctul pentru `strada` e ilustrativ.** E nodul străzii cel mai apropiat de centrul ei, ponderat după lungime.
- **Verificare încă nefăcută:** pinii din top 10 trebuie confirmați manual (V1–V2, duminică), cu `fisa`.
