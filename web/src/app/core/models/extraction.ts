import { Accident, PrecizieLoc } from './contract';

// TBD: agree with Person 2 — not in Planificare.md §4 yet. Proposal from web/PLAN.md §3.
export interface ExtractRequest {
  text?: string;
  url?: string;
}

export interface ExtractionResult {
  mode: 'live' | 'replay';
  model: string | null;
  prompt_version: string | null;
  article: { url: string | null; titlu: string | null; text: string };
  campuri: Partial<Accident>;
  // field → verbatim quote from article.text; the UI highlights it with indexOf.
  dovezi: Record<string, string>;
  avertismente: string[];
  // From the geocoding step (Person 3), never from the LLM. null = could not locate.
  localizare_propusa: { lat: number; lon: number; precizie_loc: PrecizieLoc; metoda: string } | null;
}

// TBD: agree with Person 1/2 — the plan has no database; review endpoint is a proposal.
export interface ReviewRequest {
  decision: 'approve' | 'reject';
  corrections: Partial<Accident>;
}
