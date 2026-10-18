export const environment = {
  api: {
    // Same origin: `npm start` proxies /api to :8000 (proxy.conf.json), docker-compose's nginx does the same.
    baseUrl: '/api/v1',
  },
};
