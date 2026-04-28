/**
 * Payswap app environment (production).
 */
export const environment = {
  production: true,
  apiUrl: '/api/v2',
  apiKey: '', // Set via build/deploy or runtime config
  sentry: {
    dsn: '',
    environment: 'production',
    tracesSampleRate: 0.1
  },
};
