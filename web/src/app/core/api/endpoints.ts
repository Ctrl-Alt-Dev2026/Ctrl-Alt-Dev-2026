// Every backend path in one place (relative to environment.api.baseUrl). See api/live_router.py.
export const ENDPOINTS = {
  liveStatus: '/live/status',
  liveDataset: '/live/dataset',
  // Served by the UI itself (public/data), relative to <base href>.
  cameras: 'data/cameras.json',
} as const;

export const VISION_ENDPOINTS = {
  status: '/vision/status',
  sessions: '/vision/sessions',
  session: (id: string) => `/vision/sessions/${encodeURIComponent(id)}`,
  frames: (id: string) => `/vision/sessions/${encodeURIComponent(id)}/frames`,
} as const;
