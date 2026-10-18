// streets.geojson from isu/ (proposed contract addition). Sources side by side, never summed:
// ISU Iași interventions 2024–2026, press reports (BZI, Ziarul de Iași) and IPJ totals per artery from PMUD Iași 2022.
export interface StreetSignal {
  tip: 'isu' | 'pmud' | 'gravitate' | 'presa' | 'pietoni';
  text: string;
}

export interface StreetProps {
  id: string;
  nume: string;
  nume_osm: string[];
  isu_evenimente: number;
  isu_deces: number;
  isu_grav: number;
  isu_noapte: number;
  isu_pietoni: number;
  isu_event_ids: string[];
  presa_evenimente: number;
  presa_deces: number;
  presa_grav: number;
  presa_noapte: number;
  presa_pietoni: number;
  presa_event_ids: string[];
  // null = the artery is not in the PMUD table (not "0 accidents").
  pmud_strada: string | null;
  pmud_2020: number | null;
  pmud_2021: number | null;
  pmud_nota: string | null;
  // Fixed reading order for a field check, computed in isu/ (README); null = not on the list.
  prioritate: number | null;
  semnale: StreetSignal[];
  de_verificat: string[];
  // Additive analysis from the existing event membership, separately for each source.
  analiza?: Record<'isu' | 'presa', StreetAnalysis>;
  context_osm?: StreetContext;
  // Saved Claude suggestions (isu/ai.py, `npm run ai`); absent = the street was never sent to the AI.
  recomandari_ai?: StreetAiAdvice;
}

// What to study, chosen only from the measures catalog and backed by this street's events; no cost, no effect.
export interface StreetAiAdvice {
  eticheta: string;
  model: string;
  creat_la: string;
  // false: the street's events changed after the suggestion was made.
  actual: boolean;
  rezumat: string;
  recomandari: { measure_id: string; nume: string; motiv: string; event_ids: string[]; de_verificat: string[] }[];
  date_lipsa: string[];
}

export interface StreetAnalysis {
  event_ids: string[];
  nr_evenimente: number;
  scor: number;
  componente_scor: { evenimente: number; deces: number; grav: number; context: number };
  pe_ore: number[];
  ora_necunoscuta: number;
  noapte: number;
  zi: number;
  necunoscut: number;
  cauze: Record<string, number>;
  perioada: [string | null, string | null];
  data_necunoscuta: number;
  neverificate: number;
  masuri: StreetMeasure[];
}

export interface StreetMeasure {
  measure_id: string;
  titlu: string;
  cauza: string;
  event_ids: string[];
  status: 'studiu_la_nivel_de_strada';
  amplasament_verificat: false;
  cerinte: string[];
  cost_unitar: {
    indicative_rounded_ron: number;
    source_url: string;
    year: number;
    vat: string;
    limitations: string;
  } | null;
  numar_interventii: null;
  cost_total: null;
}

export interface StreetContext {
  status: string;
  treceri_cartografiate: number | null;
  crossing_ids: string[];
  descarcat_la: string[];
  atribute: Record<string, { da: number; nu: number; necunoscut: number }>;
}

export interface StreetFeature {
  type: 'Feature';
  geometry: { type: 'MultiLineString'; coordinates: [number, number][][] };
  properties: StreetProps;
}

export interface StreetCollection {
  type: 'FeatureCollection';
  features: StreetFeature[];
}

// Which source the map and the street list show: ISU events, press events, or PMUD totals (no events).
export type StreetMetric = 'isu' | 'presa' | 'pmud';

export const SOURCE_LABEL: Record<StreetMetric, string> = {
  isu: 'ISU',
  presa: 'Presă',
  pmud: 'IPJ (PMUD)',
};

export const NO_STREETS: StreetCollection = { type: 'FeatureCollection', features: [] };
