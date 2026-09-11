import mysql from 'mysql2/promise';
import { readFileSync } from 'node:fs';

export function databaseOptions(env = process.env) {
  let url;
  try {
    url = new URL(env.VISITS_DATABASE_URL);
    if (url.protocol !== 'mysql:' || !url.hostname || url.pathname.length < 2 || url.search || url.hash) throw new Error();
  } catch {
    throw new Error('VISITS_DATABASE_URL must be a mysql://user:password@host:3306/database URL.');
  }
  return {
    host: url.hostname, port: Number(url.port || 3306),
    user: decodeURIComponent(url.username), password: decodeURIComponent(url.password),
    database: decodeURIComponent(url.pathname.slice(1)),
    charset: 'utf8mb4_bin', timezone: 'Z',
    supportBigNumbers: true, bigNumberStrings: true,
    connectionLimit: 5, queueLimit: 25, connectTimeout: 5000,
    ...(env.VISITS_MYSQL_SSL_CA ? { ssl: { ca: readFileSync(env.VISITS_MYSQL_SSL_CA), rejectUnauthorized: true, verifyIdentity: true } } : {}),
  };
}

function safeTotal(value) {
  const total = Number(value);
  if (!Number.isSafeInteger(total) || total < 0) throw new Error('Invalid counter total');
  return total;
}

export class MySQLVisitStore {
  constructor(pool) { this.pool = pool; }
  async total(sessionHash) {
    const conn = await this.pool.getConnection();
    const query = (sql, values = []) => conn.query({ sql, values, timeout: 4000 });
    let transaction = false;
    try {
      await query("SET time_zone = '+00:00', innodb_lock_wait_timeout = 3");
      if (sessionHash) { await conn.beginTransaction(); transaction = true; }
      const [rows] = await query('SELECT total FROM portal_visit_totals WHERE singleton = 1' + (sessionHash ? ' FOR UPDATE' : ''));
      if (rows.length !== 1) throw new Error('Counter migration missing');
      let total = safeTotal(rows[0].total);
      if (sessionHash) {
        // Lock the singleton before checking the token, exactly like the Python
        // service. Both implementations can safely share existing counter data.
        const [sessions] = await query('SELECT session_hash FROM portal_visit_sessions WHERE session_hash = ?', [sessionHash]);
        if (!sessions.length) {
          total = safeTotal(total + 1);
          await query('INSERT INTO portal_visit_sessions (session_hash) VALUES (?)', [sessionHash]);
          await query('UPDATE portal_visit_totals SET total = total + 1 WHERE singleton = 1');
        }
        await conn.commit(); transaction = false;
      }
      return total;
    } catch (error) {
      if (transaction) {
        try { await conn.rollback(); } catch { conn.destroy(); }
      }
      throw error;
    } finally { conn.release(); }
  }
}

export function createStore(env = process.env) {
  const pool = mysql.createPool(databaseOptions(env));
  return { store: new MySQLVisitStore(pool), close: () => pool.end() };
}
