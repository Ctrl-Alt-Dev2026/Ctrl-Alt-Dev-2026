import { CauzaRaportata, Gravitate, PrecizieLoc } from '../models/contract';

export const GRAVITATE: Record<Gravitate, string> = {
  deces: 'deces',
  grav: 'rănit grav',
  usor: 'rănit ușor',
  necunoscut: 'gravitate necunoscută',
};

export const PRECIZIE: Record<PrecizieLoc, string> = {
  trecere: 'pe trecere',
  intersectie: 'în intersecție',
  segment: 'pe segment de stradă',
  strada: 'doar strada (aproximativ)',
  vag: 'loc vag',
};

export const CAUZA: Record<CauzaRaportata, string> = {
  viteza: 'viteză',
  neacordare_prioritate: 'neacordare de prioritate',
  traversare_neregulamentara: 'traversare neregulamentară',
  vizibilitate: 'vizibilitate redusă',
};

export const PARTICIPANT: Record<string, string> = {
  pieton: 'Pietoni',
  autoturism: 'Autoturisme',
  autobuz: 'Autobuze',
  tramvai: 'Tramvaie',
  biciclist: 'Bicicliști',
  motocicleta: 'Motociclete',
  trotineta: 'Trotinete',
  camion: 'Vehicule grele',
};

export function participantLabel(p: string): string {
  return PARTICIPANT[p] ?? p.charAt(0).toUpperCase() + p.slice(1);
}

// Ranking only uses precisely located events (Planificare.md §5).
export const PRECISE: ReadonlySet<PrecizieLoc> = new Set(['trecere', 'intersectie', 'segment']);

export const COMPONENTE: Record<string, string> = {
  evenimente: 'evenimente',
  deces: 'decese',
  grav: 'răniți grav',
  context: 'context stradă',
};

export function lei(n: number): string {
  return n.toLocaleString('ro-RO') + ' lei';
}

export function dateRo(iso: string | null): string {
  if (!iso) return 'dată necunoscută';
  const [y, m, d] = iso.split('-');
  return `${d}.${m}.${y}`;
}
