// Every backend path in one place. See web/PLAN.md §3.
export const ENDPOINTS = {
  manifest: { http: '/manifest', mock: 'data/manifest.json' },
  accidents: { http: '/accidents', mock: 'data/accidents.json' },
  hotspots: { http: '/hotspots', mock: 'data/hotspots.json' },
  crossings: { http: '/crossings', mock: 'data/crossings.geojson' },
  measures: { http: '/measures', mock: 'data/measures.json' },
  extract: { http: '/extract', mock: 'data/replay/extract-001.json' },
  cameras: { http: '/cameras', mock: 'data/cameras.json' },
  review: { http: (id: string) => `/events/${id}/review` },
  report: { http: (ids: string[]) => `/report?ids=${ids.join(',')}` },
} as const;
