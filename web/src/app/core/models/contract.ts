// Mirrors Planificare.md §4 (schema 2.0). Field names are the contract's; do not rename.
// `null` always means "unknown".

export interface Manifest {
  schema_version: string;
  data_mode: 'synthetic' | 'observed';
  perioada: [string, string];
  generat_la: string;
  nr_articole: number;
  nr_evenimente: number;
  nr_localizate_precis: number;
  nr_verificate: number;
  avertisment?: string;
}

export interface Article {
  article_id: string;
  sursa: string;
  url: string;
  titlu: string;
  text: string;
  publicat_la: string;
  colectat_la: string;
}

export type PrecizieLoc = 'trecere' | 'intersectie' | 'segment' | 'strada' | 'vag';
export type Gravitate = 'deces' | 'grav' | 'usor' | 'necunoscut';
export type CauzaRaportata = 'viteza' | 'neacordare_prioritate' | 'traversare_neregulamentara' | 'vizibilitate';

export interface Accident {
  event_id: string;
  article_ids: string[];
  urls: string[];
  data_eveniment: string | null;
  ora: string | null;
  loc_text: string;
  precizie_loc: PrecizieLoc;
  lat: number | null;
  lon: number | null;
  in_iasi: boolean | null;
  participanti: string[];
  cauza_raportata: CauzaRaportata | null;
  gravitate: Gravitate;
  noapte: boolean | null;
  dovezi: Partial<Record<string, string>>;
  verificat: boolean;
}

export interface Crossing {
  id: string;
  tip: 'trecere' | 'intersectie';
  nume: string;
  semafor: boolean | null;
  benzi: number | null;
  iluminat: boolean | null;
  tip_strada: string | null;
  scoala_150m: boolean | null;
  statie_100m: boolean | null;
  sursa: string;
  descarcat_la: string;
}

export interface CrossingCollection {
  type: 'FeatureCollection';
  features: { type: 'Feature'; geometry: { type: 'Point'; coordinates: [number, number] }; properties: Crossing }[];
}

export interface HotspotMeasure {
  measure_id: string;
  motiv: string;
  de_verificat: string[];
}

export interface Hotspot {
  id: string;
  crossing_id: string | null;
  nume: string;
  lat: number;
  lon: number;
  h3: string | null;
  scor: number;
  componente_scor: { evenimente: number; deces: number; grav: number; context: number };
  event_ids: string[];
  nr_evenimente: number;
  pe_ore: number[];
  explicatie: string;
  date_lipsa: string[];
  masuri: HotspotMeasure[];
  verificat: boolean;
}

export interface Measure {
  id: string;
  nume: string;
  conditie: string;
  cost_lei_min: number | null;
  cost_lei_max: number | null;
  sursa_cost: string | null;
  reducere_tipica: number | null;
  sursa_reducere: string | null;
  de_verificat: string[];
}
