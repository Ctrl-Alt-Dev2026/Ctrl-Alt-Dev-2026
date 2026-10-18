import type { FeatureCollection, Polygon } from 'geojson';

export interface H3Properties {
  h3: string;
  resolution: number;
  event_ids: string[];
  nr_evenimente: number;
}

export type H3Collection = FeatureCollection<Polygon, H3Properties>;
export const NO_H3: H3Collection = { type: 'FeatureCollection', features: [] };
