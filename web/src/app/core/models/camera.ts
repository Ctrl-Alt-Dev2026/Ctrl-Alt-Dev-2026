// Live cameras on the map. Not in Planificare.md §4 — TBD: agree with Person 1.
// 'public' = a free webcam shown through its provider's own embed player (we never touch the stream);
// 'primarie' = a city-hall CCTV feed, only after an access agreement.
export type CameraSource = 'public' | 'primarie';

export interface Camera {
  id: string;
  nume: string;
  lat: number;
  lon: number;
  // Where lat/lon come from (e.g. the provider's listing); the exact mount point and view direction are unknown.
  sursa_coordonate: string;
  sursa: CameraSource;
  furnizor: string;
  pagina_url: string;
  embed_url: string;
  // Raw HLS stream (CORS-open); sampled frames go to the Python detector. null = embed only.
  stream_url: string | null;
}
