import { randomBytes, scrypt as scryptCallback, timingSafeEqual, createHash } from 'node:crypto';
import { promisify } from 'node:util';
const scrypt = promisify(scryptCallback);
export const token = () => randomBytes(32).toString('hex');
export const hash = value => createHash('sha256').update(value).digest('hex');
export async function passwordHash(password) {
  if (typeof password !== 'string' || password.length < 14 || password.length > 256) throw new Error('Use a password between 14 and 256 characters.');
  const salt = token();
  const key = await scrypt(password, salt, 64, { N: 32768, r: 8, p: 1, maxmem: 64 * 1024 * 1024 });
  return `scrypt$${salt}$${key.toString('hex')}`;
}
export async function passwordMatches(password, encoded) {
  if (typeof password !== 'string' || password.length > 256) return false;
  const [, salt, saved] = encoded.split('$');
  const key = await scrypt(password, salt, 64, { N: 32768, r: 8, p: 1, maxmem: 64 * 1024 * 1024 });
  return timingSafeEqual(key, Buffer.from(saved, 'hex'));
}
