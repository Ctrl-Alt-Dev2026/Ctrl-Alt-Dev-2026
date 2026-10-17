"""Read-only, offline proposals from the team's local OSM geocoder.

No coordinates are applied or approved here. The precise review contract is
stricter than the original CLI: a street's representative point stays separate.
"""

import ast
from copy import deepcopy
from datetime import datetime
from functools import lru_cache
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import re
import sys
import threading
from types import CodeType, FunctionType
import zlib


_MODULE = Path(__file__).parents[1] / "coordonate"
_INPUTS = ("osm/index_osm.json.gz", "osm/unitati_admin.geojson", "alias_nume.json", "noduri_cunoscute.json")
_ALGORITHMS = ("__init__.py", "config.py", "geometrie.py", "normalizare.py", "parser_loc.py", "index_osm.py", "granita.py", "noduri.py", "rezolvare.py")
_LOCK = threading.RLock()
_MAX_BYTES = 32 * 1024 * 1024
_MAX_EXPANDED = 64 * 1024 * 1024
_REF = re.compile(r"^(node|way|relation)/[1-9][0-9]{0,19}$")
_ALGORITHM_BASELINE = None


class GeocodingError(Exception):
    def __init__(self, status, code, message):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def _invalid(message="Indexul OSM local sau dovezile sale sunt invalide."):
    raise GeocodingError(503, "invalid_geocoding_inputs", message)


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _json(raw):
    data = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError("nonfinite JSON")))
    json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8")
    return data


def _text(value, maximum=10_000):
    return isinstance(value, str) and 0 < len(value.strip()) <= maximum


def _point(value):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return False
    lat, lon = value
    return (all(type(v) in (int, float) for v in value) and -90 <= lat <= 90 and -180 <= lon <= 180
            and all(math.isfinite(v) for v in value))


def _read_files(root, names):
    root = root.resolve(strict=True)
    paths = {name: root / name for name in names}
    for path in paths.values():
        if path.is_symlink() or not path.resolve(strict=True).is_relative_to(root):
            _invalid("Fișierele geocodării trebuie să rămână în directorul configurat.")
    def signature(path):
        stat = path.stat()
        if not path.is_file() or not 0 < stat.st_size <= _MAX_BYTES:
            _invalid("Fișier geocodare gol sau prea mare.")
        return stat.st_ino, stat.st_size, stat.st_mtime_ns
    before = {name: signature(path) for name, path in paths.items()}
    raw = {name: path.read_bytes() for name, path in paths.items()}
    if before != {name: signature(path) for name, path in paths.items()}:
        raise GeocodingError(503, "geocoding_inputs_changed", "Indexul s-a modificat în timpul citirii; reluați sugestia.")
    return raw


def _validate(index, boundaries, aliases, known):
    if not isinstance(index, dict) or set(index) != {"meta", "noduri", "strazi", "treceri", "poi", "locuri", "adrese"}:
        _invalid()
    meta = index["meta"]
    if not isinstance(meta, dict) or meta.get("versiune_index") != 1 or not _text(meta.get("sursa")):
        _invalid("Indexul necesită versiunea și proveniența OSM.")
    timestamp = datetime.fromisoformat(meta["descarcat_la"])
    if timestamp.tzinfo is None or "OpenStreetMap" not in meta["sursa"]:
        _invalid("Indexul necesită momentul colectării cu fus orar și atribuirea OSM.")
    nodes = index["noduri"]
    if not isinstance(nodes, dict) or not nodes or any(not re.fullmatch(r"[1-9][0-9]{0,19}", key) or not _point(value) for key, value in nodes.items()):
        _invalid("Noduri OSM sau coordonate invalide.")
    if not isinstance(index["strazi"], dict) or not index["strazi"]:
        _invalid("Indexul nu conține străzi.")
    components = set()
    for key, rows in index["strazi"].items():
        if not _text(key) or not isinstance(rows, list) or not rows:
            _invalid()
        for position, row in enumerate(rows):
            if (not isinstance(row, dict) or not _text(row.get("nume")) or not _point(row.get("punct"))
                    or not isinstance(row.get("segmente"), list) or not row["segmente"]
                    or not isinstance(row.get("bbox"), list) or len(row["bbox"]) != 4
                    or not _point(row["bbox"][:2]) or not _point(row["bbox"][2:])):
                _invalid("Componentă de stradă invalidă.")
            for segment in row["segmente"]:
                if not isinstance(segment, list) or len(segment) != 2 or any(type(n) is not int or str(n) not in nodes for n in segment):
                    _invalid("Un segment nu trimite la noduri OSM existente.")
            if (not isinstance(row.get("way_ids"), list) or not row["way_ids"]
                    or any(type(n) is not int or n < 1 for n in row["way_ids"])):
                _invalid("Stradă fără referințe OSM valide.")
            components.add(f"{key}#{position}")
    references = set()
    for field in ("treceri", "poi", "locuri"):
        if not isinstance(index[field], list):
            _invalid()
        seen = set()
        for item in index[field]:
            if (not isinstance(item, dict) or not isinstance(item.get("osm"), str) or not _REF.fullmatch(item["osm"])
                    or item["osm"] in seen or not _point([item.get("lat"), item.get("lon")])):
                _invalid("Obiect punctual OSM invalid sau duplicat.")
            if field != "treceri" and not _text(item.get("nume")):
                _invalid()
            if field == "treceri" and (not isinstance(item.get("strazi"), list) or any(c not in components for c in item["strazi"])):
                _invalid("Trecere cu referință de stradă inexistentă.")
            seen.add(item["osm"])
            references.add(item["osm"])
    if not isinstance(index["adrese"], dict):
        _invalid()
    for street, addresses in index["adrese"].items():
        if not _text(street) or not isinstance(addresses, dict):
            _invalid()
        for number, address in addresses.items():
            if (not _text(number) or not isinstance(address, list) or len(address) != 3 or not _point(address[:2])
                    or not isinstance(address[2], str) or not _REF.fullmatch(address[2])):
                _invalid("Adresă OSM invalidă.")
    if not isinstance(boundaries, dict) or boundaries.get("type") != "FeatureCollection" or not isinstance(boundaries.get("features"), list):
        _invalid("Lipsește colecția de limite administrative.")
    seen = set()
    municipality = None
    for feature in boundaries["features"]:
        p, g = feature.get("properties", {}), feature.get("geometry", {})
        if (not isinstance(p, dict) or not isinstance(p.get("osm"), str) or not _REF.fullmatch(p["osm"])
                or p["osm"] in seen or not isinstance(g, dict) or g.get("type") not in ("Polygon", "MultiPolygon")):
            _invalid("Limită administrativă invalidă sau duplicată.")
        seen.add(p["osm"])
        polygons = [g.get("coordinates")] if g["type"] == "Polygon" else g.get("coordinates")
        if not isinstance(polygons, list) or not polygons:
            _invalid()
        for polygon in polygons:
            if not isinstance(polygon, list) or not polygon:
                _invalid()
            for ring in polygon:
                if not isinstance(ring, list) or len(ring) < 4 or ring[0] != ring[-1] or any(not _point(c[::-1]) for c in ring):
                    _invalid("Coordonate invalide în limita administrativă.")
        if p["osm"] == "relation/1207838":
            if p.get("admin_level") != "8" or str(p.get("nume", "")).replace("ş", "ș") != "Iași":
                _invalid("Limita OSM nu identifică Municipiul Iași.")
            municipality = feature
    if municipality is None:
        _invalid("Lipsește limita verificabilă relation/1207838 a Municipiului Iași.")
    if not isinstance(aliases, dict):
        _invalid()
    for field in ("alias_nume", "repere", "prefixe"):
        if not isinstance(aliases.get(field), dict) or any(not _text(k) or not _text(v) for k, v in aliases[field].items()):
            _invalid("Aliasurile trebuie să fie exclusiv text către text.")
    if not isinstance(known, dict) or not isinstance(known.get("noduri"), list):
        _invalid()
    seen = set()
    for row in known["noduri"]:
        if (not isinstance(row, dict) or not _text(row.get("id")) or row["id"] in seen or not _text(row.get("nume"))
                or type(row.get("verificat")) is not bool or not isinstance(row.get("alias"), list)
                or any(not _text(alias) for alias in row["alias"])
                or row.get("osm") is not None and (not isinstance(row["osm"], str) or not _REF.fullmatch(row["osm"]))):
            _invalid("Nod cunoscut invalid.")
        if row["verificat"] and (not _text(row.get("verificat_de")) or not _text(row.get("verificat_la")) or not row.get("osm")):
            _invalid("Un nod declarat verificat necesită autor, moment și referință OSM.")
        seen.add(row["id"])


def _defaults(source):
    names = {"PREFIXE", "ALIAS_NUME", "ALIAS_REPERE"}
    values = {}
    for node in ast.parse(source).body:
        target = node.target if isinstance(node, ast.AnnAssign) else node.targets[0] if isinstance(node, ast.Assign) else None
        if isinstance(target, ast.Name) and target.id in names:
            values[target.id] = ast.literal_eval(node.value)
    if set(values) != names:
        _invalid("Configurația normalizării nu poate fi verificată.")
    return values


def _verify_algorithms(sources):
    """Reject disk/code drift; compile trusted source without executing it."""
    global _ALGORITHM_BASELINE
    hashes = {name: hashlib.sha256(raw).hexdigest() for name, raw in sources.items()}
    if _ALGORITHM_BASELINE is not None and hashes != _ALGORITHM_BASELINE:
        raise GeocodingError(503, "geocoding_restart_required", "Algoritmul geocodării s-a schimbat; reporniți serverul.")
    for name, raw in sources.items():
        module = sys.modules["api.geocoding" if name == "api/geocoding.py" else "coordonate" if name == "__init__.py" else "coordonate." + name[:-3]]
        compiled = compile(raw, module.__file__, "exec", dont_inherit=True, optimize=sys.flags.optimize)
        codes = {}
        def collect(code):
            codes[code.co_qualname] = code
            for constant in code.co_consts:
                if isinstance(constant, CodeType):
                    collect(constant)
        collect(compiled)
        objects = list(vars(module).values())
        for value in list(objects):
            if isinstance(value, type) and value.__module__ == module.__name__:
                objects.extend(vars(value).values())
        for value in objects:
            value = value.__func__ if isinstance(value, (classmethod, staticmethod)) else value.fget if isinstance(value, property) else getattr(value, "__wrapped__", value)
            if isinstance(value, FunctionType) and value.__module__ == module.__name__ and value.__code__.co_filename != "<string>":
                if codes.get(value.__qualname__) != value.__code__:
                    raise GeocodingError(503, "geocoding_restart_required", "Codul încărcat al geocodării diferă de sursă; reporniți serverul.")
    _ALGORITHM_BASELINE = hashes


class GeocodingService:
    def __init__(self, reference_directory=None):
        self.reference_directory = Path(reference_directory) if reference_directory is not None else _MODULE / "date_referinta"
        self._fingerprint, self._resolver, self._provenance, self._aliases = None, None, None, None

    def _load(self):
        raw = _read_files(self.reference_directory, _INPUTS)
        algorithms = _read_files(_MODULE, _ALGORITHMS)
        input_hashes = {name: hashlib.sha256(value).hexdigest() for name, value in raw.items()}
        algorithm_hashes = {f"coordonate/{name}": hashlib.sha256(value).hexdigest() for name, value in algorithms.items()}
        algorithm_hashes["api/geocoding.py"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        fingerprint = hashlib.sha256(json.dumps({"inputs": input_hashes, "algorithms": algorithm_hashes}, sort_keys=True).encode()).hexdigest()
        if self._fingerprint == fingerprint:
            return
        with gzip.GzipFile(fileobj=io.BytesIO(raw["osm/index_osm.json.gz"])) as stream:
            expanded = stream.read(_MAX_EXPANDED + 1)
        if len(expanded) > _MAX_EXPANDED:
            _invalid("Indexul OSM decomprimat depășește limita locală.")
        index, boundaries, aliases, known = (_json(expanded), _json(raw["osm/unitati_admin.geojson"]), _json(raw["alias_nume.json"]), _json(raw["noduri_cunoscute.json"]))
        _validate(index, boundaries, aliases, known)
        from coordonate import granita, normalizare
        from coordonate.index_osm import IndexOSM
        from coordonate.noduri import NodCunoscut, NoduriCunoscute
        from coordonate.rezolvare import Rezolvator
        _verify_algorithms(algorithms | {"api/geocoding.py": Path(__file__).read_bytes()})
        alias_values = _defaults(algorithms["normalizare.py"])
        for field, name in (("alias_nume", "ALIAS_NUME"), ("repere", "ALIAS_REPERE"), ("prefixe", "PREFIXE")):
            alias_values[name].update({normalizare._cheie_simpla(key): value for key, value in aliases[field].items()})
        units = [granita._Unitate(f["properties"]["nume"], f["properties"]["osm"], f["geometry"], granita.bbox_geometrie(f["geometry"])) for f in boundaries["features"]]
        municipality = next(unit for unit in units if unit.osm == "relation/1207838")
        boundary = granita.Granita([municipality] + [unit for unit in units if unit is not municipality], municipality)
        if boundary.verifica(47.1564, 27.5877).in_iasi is not True:
            _invalid("Limita administrativă nu acoperă centrul municipiului.")
        saved = {name: getattr(normalizare, name) for name in alias_values}
        try:
            for name, values in alias_values.items():
                setattr(normalizare, name, deepcopy(values))
            resolver = Rezolvator(IndexOSM(index), boundary, NoduriCunoscute([NodCunoscut(**{k: v for k, v in row.items() if k in NodCunoscut.__dataclass_fields__}) for row in known["noduri"]]))
        finally:
            for name, values in saved.items():
                setattr(normalizare, name, values)
        self._resolver, self._aliases = resolver, alias_values
        self._provenance = {"data_mode": "observed", "source": index["meta"]["sursa"], "downloaded_at": index["meta"]["descarcat_la"],
                            "input_hashes": input_hashes, "algorithm_hashes": algorithm_hashes, "fingerprint": fingerprint,
                            "boundary_osm": "relation/1207838", "network_requests": 0}
        self._fingerprint = fingerprint

    def suggest(self, loc_text, data_mode):
        if data_mode == "synthetic":
            raise GeocodingError(422, "synthetic_geocoding_unavailable", "Resolverul OSM observat nu se aplică evenimentelor sintetice; este necesar un resolver sintetic separat.")
        if data_mode != "observed":
            raise GeocodingError(422, "invalid_data_mode", "Geocodarea necesită data_mode observed.")
        if not _text(loc_text, 10_000):
            raise GeocodingError(422, "invalid_location_text", "Introduceți un text de localizare între 1 și 10.000 de caractere.")
        try:
            loc_text.encode("utf-8")
            with _LOCK:
                self._load()
                from coordonate import normalizare
                saved = {name: getattr(normalizare, name) for name in self._aliases}
                try:
                    for name, values in self._aliases.items():
                        setattr(normalizare, name, deepcopy(values))
                    report = self._resolver.rezolva(loc_text).ca_dict()
                finally:
                    for name, values in saved.items():
                        setattr(normalizare, name, values)
                changes = {key: report[key] for key in ("lat", "lon", "precizie_loc", "in_iasi")}
                warnings = ["Sugestie deterministă din OSM local; operatorul verifică sursa, sensul textului și poziția înainte de aplicare.",
                            "OSM descrie infrastructura cartografiată; lipsa unui obiect nu dovedește absența sa."]
                if changes["precizie_loc"] not in ("trecere", "intersectie", "segment"):
                    changes["lat"] = changes["lon"] = None
                    warnings.append("Punctul orientativ al străzii/zonei este separat; nu este coordonata evenimentului.")
                changes["location_evidence"] = None
                from api.review_models import CandidateFields
                CandidateFields.model_validate(changes)
                result = {"proposed_changes": changes, "report": report, "provenance": deepcopy(self._provenance),
                          "needs_operator_confirmation": True, "warnings": warnings, "persisted": False,
                          "publication_status": "not_published"}
                json.dumps(result, ensure_ascii=False, allow_nan=False).encode("utf-8")
                return result
        except GeocodingError:
            raise
        except (OSError, EOFError, ValueError, TypeError, KeyError, AttributeError, IndexError, OverflowError, RecursionError, SyntaxError, zlib.error) as error:
            raise GeocodingError(503, "geocoding_unavailable", "Indexul OSM local sau algoritmul nu poate fi verificat; nu s-a aplicat nicio coordonată.") from error


@lru_cache(maxsize=1)
def get_service():
    """Factory only: creating the service performs no IO, imports or downloads."""
    return GeocodingService()
