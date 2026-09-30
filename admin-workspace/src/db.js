import mysql from 'mysql2/promise';
import { readFileSync } from 'node:fs';
import { InputError, validateReview, methodology } from './review.js';

export function databaseOptions(env = process.env) {
  let url;
  try { url = new URL(env.ADMIN_DATABASE_URL); } catch { throw new Error('Set a valid ADMIN_DATABASE_URL.'); }
  if (url.protocol !== 'mysql:' || !url.hostname || url.pathname.length < 2 || url.search || url.hash) throw new Error('ADMIN_DATABASE_URL must be a MySQL URL with a database name.');
  return { host: url.hostname, port: Number(url.port || 3306), user: decodeURIComponent(url.username), password: decodeURIComponent(url.password), database: decodeURIComponent(url.pathname.slice(1)), timezone: 'Z', charset: 'utf8mb4', supportBigNumbers: true, bigNumberStrings: true, connectionLimit: 5, queueLimit: 30, connectTimeout: 5000, ...(env.ADMIN_MYSQL_SSL_CA ? { ssl: { ca: readFileSync(env.ADMIN_MYSQL_SSL_CA), rejectUnauthorized: true } } : {}) };
}
export const createPool = (env) => mysql.createPool(databaseOptions(env));
// MySQL decodes JSON natively; MariaDB exposes its JSON alias as text.
export const jsonDocument = value => typeof value === 'string' ? JSON.parse(value) : value;
const observed = field => `NULLIF(JSON_UNQUOTE(JSON_EXTRACT(snapshot, '$.${field}')), '')`;
const SORT_ORDERS = Object.freeze({
  record: 'id ASC',
  last_newest: `${observed('last_seen_at')} DESC, id DESC`,
  last_oldest: `(${observed('last_seen_at')} IS NULL) ASC, ${observed('last_seen_at')} ASC, id ASC`,
  first_newest: `${observed('first_seen_at')} DESC, id DESC`,
  first_oldest: `(${observed('first_seen_at')} IS NULL) ASC, ${observed('first_seen_at')} ASC, id ASC`,
});
export function candidateSortOrder(sort) {
  if (!Object.hasOwn(SORT_ORDERS, sort)) throw new InputError('Invalid candidate sort order.');
  return SORT_ORDERS[sort];
}
export async function migrate(pool) {
  const sql = readFileSync(new URL('../../migrations/005_admin_workspace.sql', import.meta.url), 'utf8');
  for (const statement of sql.split(';').map(s => s.trim()).filter(Boolean)) await pool.query(statement);
}
export class Store {
  constructor(pool) { this.pool = pool; }
  async query(sql, params = []) { const [rows] = await this.pool.execute({ sql, timeout: 8000 }, params); return rows; }
  async loginAttempt(bucket) {
    await this.query('DELETE FROM admin_login_limits WHERE reset_at < UTC_TIMESTAMP(3)');
    await this.query('INSERT INTO admin_login_limits (bucket_hash, attempts, reset_at) VALUES (?, 1, DATE_ADD(UTC_TIMESTAMP(3), INTERVAL 15 MINUTE)) ON DUPLICATE KEY UPDATE attempts = attempts + 1', [bucket]);
    return (await this.query('SELECT attempts FROM admin_login_limits WHERE bucket_hash = ?', [bucket]))[0].attempts <= 10;
  }
  async user(email) { return (await this.query('SELECT * FROM admin_users WHERE email = ?', [email]))[0]; }
  async session(tokenHash) {
    return (await this.query('SELECT s.csrf_token, u.id, u.email FROM admin_sessions s JOIN admin_users u ON u.id = s.user_id WHERE token_hash = ? AND expires_at > UTC_TIMESTAMP(3)', [tokenHash]))[0];
  }
  async startSession(tokenHash, csrf, userId) {
    await this.query('DELETE FROM admin_sessions WHERE expires_at <= UTC_TIMESTAMP(3)');
    await this.query('INSERT INTO admin_sessions (token_hash, user_id, csrf_token, expires_at) VALUES (?, ?, ?, DATE_ADD(UTC_TIMESTAMP(3), INTERVAL 8 HOUR))', [tokenHash, userId, csrf]);
  }
  async logout(tokenHash) { await this.query('DELETE FROM admin_sessions WHERE token_hash = ?', [tokenHash]); }
  async dashboard() {
    return this.query('SELECT source_district AS district, status, COUNT(*) AS total FROM admin_candidates GROUP BY source_district, status ORDER BY source_district, status');
  }
  async candidates({ district = '', status = '', search = '', page = '1', sort = 'record' }) {
    const p = Math.max(1, Math.min(10000, Number.parseInt(page) || 1));
    const order = candidateSortOrder(sort);
    // Compare bound values directly with columns. Parameter-to-empty-literal
    // comparisons can have incompatible coercible collations on MariaDB.
    const clauses = [];
    const params = [];
    if (district) { clauses.push('source_district = ?'); params.push(district); }
    if (status) { clauses.push('status = ?'); params.push(status); }
    if (search) { clauses.push('name LIKE ?'); params.push(`%${search}%`); }
    const where = clauses.length ? `WHERE ${clauses.join(' AND ')}` : '';
    const rows = await this.query(`SELECT id, name, source_district, confidence, status, revision,
      ${observed('first_seen_at')} AS first_observed, ${observed('last_seen_at')} AS last_observed
      FROM admin_candidates ${where} ORDER BY ${order} LIMIT 20 OFFSET ${(p - 1) * 20}`, params);
    const [{ total }] = await this.query(`SELECT COUNT(*) AS total FROM admin_candidates ${where}`, params);
    return { rows, total: Number(total), page: p };
  }
  async candidate(id) {
    const record = (await this.query('SELECT * FROM admin_candidates WHERE id = ?', [id]))[0];
    if (!record) throw new InputError('Candidate not found.', 404);
    const revisions = await this.query('SELECT r.revision, r.status, r.document, r.created_at, u.email AS author, e.previous_status, e.reason FROM admin_record_revisions r JOIN admin_users u ON u.id = r.author_id JOIN admin_review_events e ON e.revision_id = r.id WHERE r.candidate_id = ? ORDER BY r.revision DESC', [id]);
    return { ...record, snapshot: jsonDocument(record.snapshot), revisions: revisions.map(row => ({ ...row, document: jsonDocument(row.document) })) };
  }
  async save(id, userId, input) {
    const conn = await this.pool.getConnection();
    try {
      await conn.query('SET SESSION innodb_lock_wait_timeout = 5');
      await conn.beginTransaction();
      const [[record]] = await conn.execute('SELECT revision, status FROM admin_candidates WHERE id = ? FOR UPDATE', [id]);
      if (!record) throw new InputError('Candidate not found.', 404);
      if (record.revision !== input?.version) throw new InputError('This record changed in another tab. Reload it before saving; your unsaved text is still here.', 409);
      const document = validateReview(input, record.status);
      const revision = record.revision + 1;
      const [result] = await conn.execute('INSERT INTO admin_record_revisions (candidate_id, revision, author_id, status, methodology, document) VALUES (?, ?, ?, ?, ?, ?)', [id, revision, userId, document.status, methodology, JSON.stringify(document)]);
      await conn.execute('INSERT INTO admin_review_events (candidate_id, revision_id, author_id, previous_status, new_status, reason) VALUES (?, ?, ?, ?, ?, ?)', [id, result.insertId, userId, record.status, document.status, document.reopenReason || document.rationale || 'Saved draft']);
      await conn.execute('UPDATE admin_candidates SET revision = ?, status = ?, updated_at = UTC_TIMESTAMP(3) WHERE id = ?', [revision, document.status, id]);
      await conn.commit();
      return { revision };
    } catch (error) { await conn.rollback(); throw error; } finally { conn.release(); }
  }
}
