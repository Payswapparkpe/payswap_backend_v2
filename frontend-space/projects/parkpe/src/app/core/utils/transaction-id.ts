/**
 * Client-side ID matching backend `portal.utils.transaction_id.generate_transaction_id`.
 * Format (20 chars): T + YYYYMMDDHHMMSS (UTC) + 4 (ms-based) + 1 random alnum.
 * Example: T2026032007124729791
 */
const RAND = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ';

export function generateTransactionId(prefix = 'T'): string {
  const now = new Date();
  const p = (n: number, w: number) => String(n).padStart(w, '0');
  const ts = `${now.getUTCFullYear()}${p(now.getUTCMonth() + 1, 2)}${p(now.getUTCDate(), 2)}${p(
    now.getUTCHours(),
    2
  )}${p(now.getUTCMinutes(), 2)}${p(now.getUTCSeconds(), 2)}`;
  const micro4 = p(now.getMilliseconds() * 1000, 6).slice(0, 4);
  const rand1 = RAND[Math.floor(Math.random() * RAND.length)] ?? '0';
  const tid = `${prefix}${ts}${micro4}${rand1}`;
  return tid.length > 20 ? tid.slice(0, 20) : tid;
}
