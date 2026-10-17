import { Article, CauzaRaportata, Gravitate, PrecizieLoc } from './contract';

export type ReviewDataMode = 'synthetic' | 'observed';
export interface CandidateFields {
  data_eveniment: string | null;
  ora: string | null;
  loc_text: string | null;
  participanti: string[];
  cauza_raportata: CauzaRaportata | null;
  gravitate: Gravitate;
  noapte: boolean | null;
  lat: number | null;
  lon: number | null;
  precizie_loc: PrecizieLoc | null;
  in_iasi: boolean | null;
  location_evidence: string | null;
}
export interface ReviewHistory {
  version: number;
  action: string;
  operator: string;
  at: string;
  note: string;
  changes: Record<string, unknown>;
}
export interface Candidate {
  candidate_id: string;
  import_id: string;
  article_id: string;
  data_mode: ReviewDataMode;
  version: number;
  review_status: 'pending' | 'approved' | 'rejected' | 'linked';
  verificat: boolean;
  canonical_event_id: string | null;
  fields: CandidateFields;
  original_extraction: { dovezi?: Record<string, string>; [key: string]: unknown };
  history: ReviewHistory[];
  article?: Article;
}
export interface ImportRecord {
  import_id: string;
  request_id: string;
  data_mode: ReviewDataMode;
  article: Article;
  candidate_ids: string[];
  extraction: {
    processing_mode?: string;
    model?: string | null;
    prompt_version?: string | null;
    warnings?: string[];
    errors?: unknown[];
    [key: string]: unknown;
  };
}
export interface ImportArticleRequest {
  request_id: string;
  data_mode: ReviewDataMode;
  operator: string;
  pipeline: 'rules' | 'hybrid';
  mode: 'extract';
  article: Article;
}
export interface ReviewedEvent {
  event_id: string;
  data_mode: ReviewDataMode;
  version: number;
  publication_status: 'not_published';
  fields: CandidateFields;
  article_ids: string[];
  urls: string[];
  source_claims: Candidate[];
  history: ReviewHistory[];
}
export interface CandidateCorrection {
  data_mode: ReviewDataMode;
  expected_version: number;
  operator: string;
  reason: string;
  changes: Partial<CandidateFields>;
}
export interface CandidateDecision {
  data_mode: ReviewDataMode;
  expected_version: number;
  operator: string;
  note: string;
  action: 'approve' | 'reject' | 'link';
  source_checked: boolean;
  duplicate_checked: boolean;
  location_checked: boolean;
  canonical_event_id?: string;
  expected_event_version?: number;
}
export interface GeocodingProposal {
  suggestion_id: string;
  expected_version: number;
  loc_text: string;
  proposed_changes: Partial<CandidateFields>;
  report: { metoda?: string; referinte_osm?: string[]; [key: string]: unknown };
  provenance: { source?: string; fingerprint?: string; [key: string]: unknown };
  warnings: string[];
  persisted: false;
}
export interface PublicationFeature {
  type: 'Feature';
  id?: string;
  geometry: { type: 'Point'; coordinates: [number, number] };
  properties: { id: string; nume?: string; tip?: string; [key: string]: unknown };
}
export interface PublicationContext {
  data_mode: ReviewDataMode;
  context: { attribution?: string; fingerprint?: string; [key: string]: unknown };
  total: number;
  filtered_total: number;
  offset: number;
  limit: number;
  features: PublicationFeature[];
}
export interface PublicationSelection {
  event_id: string;
  expected_version: number;
  location_id: string;
  association_checked: true;
  association_note: string;
}
export interface PublicationRequest {
  request_id: string;
  data_mode: ReviewDataMode;
  operator: string;
  note: string;
  period_start: string;
  period_end: string;
  source_conflicts_checked: true;
  selections: PublicationSelection[];
}
export interface PublicationPreview {
  data_mode: ReviewDataMode;
  eligible_event_count: number;
  excluded_event_count: number;
  diagnostics: { event_id: string; location_id: string; status: string; reasons: string[] }[];
  locations: { location_id: string; event_count: number; source_article_count: number; score: number | null; rank: number | null }[];
  warnings: string[];
  publication_status: 'preview';
  persisted: false;
}
