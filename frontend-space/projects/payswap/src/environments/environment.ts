/**
 * Payswap app environment (development).
 * API key: run `python manage.py create_internal_api_keys` and set the key here.
 */
export const environment = {
  production: false,
  apiUrl: 'http://127.0.0.1:8000/api/v2',
  apiKey: '', // e.g. psk_live_xxxxxxxxxxxxx from create_internal_api_keys
};
