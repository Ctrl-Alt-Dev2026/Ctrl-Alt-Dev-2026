export const environment = {
  api: {
    // 'mock' reads public/data/*.json; 'http' calls the backend at baseUrl.
    mode: 'http' as 'mock' | 'http',
    baseUrl: '/api/v1',
    // Makes mock POSTs fail, to exercise error states.
    mockFail: false,
  },
};
