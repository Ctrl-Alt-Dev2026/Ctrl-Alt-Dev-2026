import { Accident, Article, CrossingCollection, Hotspot, Manifest, Measure } from './contract';

export type DataMode = 'synthetic' | 'observed';

// Backend publication-1 contracts. Review fields and source articles remain separate.
export interface PublishedFields {
  data_eveniment: string | null;
  ora: string | null;
  loc_text: string | null;
  participanti: string[];
  cauza_raportata: Accident['cauza_raportata'];
  gravitate: Accident['gravitate'];
  noapte: boolean | null;
  lat: number | null;
  lon: number | null;
  precizie_loc: Accident['precizie_loc'] | null;
  in_iasi: boolean | null;
  location_evidence: string | null;
}

export interface PublishedEvent {
  event_id: string;
  data_mode: DataMode;
  version: number;
  verificat: true;
  publication_status: 'published';
  fields: PublishedFields;
  candidate_ids: string[];
  article_ids: string[];
  urls: string[];
  source_articles: Article[];
  source_claims: Record<string, unknown>[];
  history: Record<string, unknown>[];
  association: { location_id: string; checked: true; note: string; operator: string };
}

export interface PublishedLocation {
  location_id: string;
  feature: CrossingCollection['features'][number];
  event_ids: string[];
  event_count: number;
  source_article_count: number;
  score: number | null;
  rank: number | null;
  sufficient_for_score: boolean;
  score_details: {
    scor: number;
    componente_scor: Hotspot['componente_scor'];
    explicatie: string;
    date_lipsa: string[];
    pe_ore: number[];
    event_ids: string[];
  } | null;
  unknowns: string[];
  association_status: 'operator_checked';
}

export interface PublicationSnapshot {
  schema_version: 'publication-1';
  snapshot_id: string;
  data_mode: DataMode;
  publication_status: 'published';
  published_at: string;
  period: { start: string; end: string };
  content_sha256: string;
  eligible_event_count: number;
  warnings: string[];
  events: PublishedEvent[];
  locations: PublishedLocation[];
  provenance: {
    context: { attribution: string; fingerprint: string; [key: string]: unknown };
    formula_sha256: string;
    [key: string]: unknown;
  };
  [key: string]: unknown;
}

export interface LocationDossierPayload {
  snapshot_id: string;
  data_mode: DataMode;
  publication_status: 'published';
  published_at: string;
  period: PublicationSnapshot['period'];
  content_sha256: string;
  warnings: string[];
  location: PublishedLocation;
  events: PublishedEvent[];
  provenance: PublicationSnapshot['provenance'];
  context_attribution: string;
  candidate_measures: unknown[];
  measures_status: string;
}

// UI projections preserve the immutable snapshot and do not calculate scores.
export interface LoadedDataset {
  publication: PublicationSnapshot | null;
  manifest: Manifest;
  accidents: Accident[];
  hotspots: Hotspot[];
  crossings: CrossingCollection;
  measures: Measure[];
}

export function projectPublication(snapshot: PublicationSnapshot): LoadedDataset {
  const uniqueEvents = new Map(snapshot.events.map((event) => [event.event_id, event]));
  if (uniqueEvents.size !== snapshot.events.length ||
      new Set(snapshot.locations.map((row) => row.location_id)).size !== snapshot.locations.length ||
      snapshot.locations.some((row) => row.event_ids.some((id) => !uniqueEvents.has(id)))) {
    throw new Error('Publicația conține identificatori duplicați sau referințe la evenimente inexistente.');
  }
  const events = [...uniqueEvents.values()];
  const articleIds = new Set(events.flatMap((event) => event.article_ids));
  const accidents: Accident[] = events.map((event) => ({
    ...event.fields,
    event_id: event.event_id,
    article_ids: event.article_ids,
    urls: event.urls,
    loc_text: event.fields.loc_text ?? 'Loc necunoscut',
    precizie_loc: event.fields.precizie_loc ?? 'vag',
    dovezi: {},
    verificat: event.verificat,
  }));
  const hotspots: Hotspot[] = snapshot.locations
    .filter((row) => row.score !== null && row.rank !== null && row.score_details !== null)
    .map((row) => {
      const [lon, lat] = row.feature.geometry.coordinates;
      const details = row.score_details!;
      return {
        id: row.location_id,
        crossing_id: row.feature.properties.id,
        nume: row.feature.properties.nume || row.location_id,
        lat, lon, h3: null,
        scor: row.score!, rank: row.rank,
        componente_scor: details.componente_scor,
        event_ids: row.event_ids,
        nr_evenimente: row.event_count,
        pe_ore: details.pe_ore,
        explicatie: details.explicatie,
        date_lipsa: details.date_lipsa,
        masuri: [],
        verificat: false,
        association_status: row.association_status,
      };
    });
  return {
    publication: snapshot,
    manifest: {
      schema_version: snapshot.schema_version,
      data_mode: snapshot.data_mode,
      perioada: [snapshot.period.start, snapshot.period.end],
      generat_la: snapshot.published_at,
      nr_articole: articleIds.size,
      nr_evenimente: events.length,
      nr_localizate_precis: events.filter((event) =>
        event.fields.lat !== null && event.fields.lon !== null &&
        (event.fields.precizie_loc === 'trecere' || event.fields.precizie_loc === 'intersectie' || event.fields.precizie_loc === 'segment'),
      ).length,
      nr_verificate: events.filter((event) => event.verificat).length,
      avertisment: snapshot.warnings.join(' '),
    },
    accidents, hotspots,
    crossings: { type: 'FeatureCollection', features: snapshot.locations.map((row) => row.feature) },
    measures: [],
  };
}
