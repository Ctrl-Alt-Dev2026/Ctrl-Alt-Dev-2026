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
