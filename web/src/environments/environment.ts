export const environment = {
  api: {
    // 'mock' reads public/data/*.json; 'http' calls the backend at baseUrl.
    mode: 'mock' as 'mock' | 'http',
    baseUrl: '/api',
    // Makes mock POSTs fail, to exercise error states.
    mockFail: false,
  },
};
