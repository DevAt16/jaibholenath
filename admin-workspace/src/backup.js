import { createHash } from 'node:crypto';
import { migrate } from './db.js';

// Fixed identifiers only. Session tokens and login throttles are intentionally
// excluded: recovering a workspace must not recover authenticated sessions.
export const tables = {
  admin_users: ['id', 'email', 'password_hash', 'created_at'],
  admin_candidates: ['id', 'google_place_id', 'name', 'source_state', 'source_district', 'confidence', 'snapshot', 'snapshot_sha256', 'imported_at', 'status', 'revision', 'updated_at'],
  admin_record_revisions: ['id', 'candidate_id', 'revision', 'author_id', 'status', 'methodology', 'document', 'created_at'],
  admin_review_events: ['id', 'candidate_id', 'revision_id', 'author_id', 'previous_status', 'new_status', 'reason', 'created_at'],
};
export const maxRows = 10000;
export const maxBytes = 64 * 1024 * 1024;
export const digest = value => createHash('sha256').update(JSON.stringify(value)).digest('hex');
const jsonColumns = new Set(['snapshot', 'document']);
function stable(value) {
  if (Array.isArray(value)) return value.map(stable);
  if (value && typeof value === 'object') return Object.fromEntries(Object.keys(value).sort().map(key => [key, stable(value[key])]));
  return value;
}
function cell(value, column) {
  if (value === null) return null;
  if (jsonColumns.has(column)) return JSON.stringify(stable(typeof value === 'string' ? JSON.parse(value) : value));
  if (value instanceof Date) return value.toISOString().replace('T', ' ').replace('Z', '');
  return String(value);
}
export function validateBackup(backup) {
  if (backup?.format !== 'shiva-admin-backup-v1' || backup.sha256 !== digest(backup.data)) throw new Error('Invalid backup format or checksum.');
  if (Buffer.byteLength(JSON.stringify(backup), 'utf8') > maxBytes || !backup.data || Object.keys(backup.data).sort().join() !== Object.keys(tables).sort().join()) throw new Error('Invalid backup table set or size.');
  for (const [table, columns] of Object.entries(tables)) {
    const rows = backup.data[table];
    if (!Array.isArray(rows) || rows.length > maxRows) throw new Error('Backup exceeds pilot row limit.');
    for (const row of rows) {
      if (!Array.isArray(row) || row.length !== columns.length || row.some(value => value !== null && typeof value !== 'string')) throw new Error('Invalid backup row.');
      columns.forEach((column, i) => { if (jsonColumns.has(column)) JSON.parse(row[i]); });
    }
  }
  return backup;
}
export async function snapshot(connection) {
  const data = {};
  for (const [table, columns] of Object.entries(tables)) {
    const [rows] = await connection.query(`SELECT ${columns.join(',')} FROM ${table} ORDER BY id LIMIT ${maxRows + 1}`);
    if (rows.length > maxRows) throw new Error('Backup exceeds pilot row limit; no partial backup was saved.');
    data[table] = rows.map(row => columns.map(column => cell(row[column], column)));
  }
  return data;
}
export async function captureBackup(connection) {
  await connection.query('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ');
  await connection.query('START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY');
  try {
    const data = await snapshot(connection);
    const backup = validateBackup({ format: 'shiva-admin-backup-v1', createdAt: new Date().toISOString(), data, sha256: digest(data) });
    await connection.commit();
    return backup;
  } catch (error) { await connection.rollback(); throw error; }
}
export async function restoreBackup(connection, backup) {
  validateBackup(backup);
  // The CLI only connects to a newly created, local recovery database. This
  // empty-table gate also protects callers invoking this function directly.
  await migrate(connection);
  await connection.beginTransaction();
  try {
    for (const table of [...Object.keys(tables), 'admin_sessions', 'admin_login_limits']) {
      const [[{ total }]] = await connection.query(`SELECT COUNT(*) AS total FROM ${table}`);
      if (Number(total)) throw new Error('Restore requires empty admin tables. Existing data was not replaced.');
    }
    for (const [table, columns] of Object.entries(tables)) {
      for (const row of backup.data[table]) await connection.execute(`INSERT INTO ${table} (${columns.join(',')}) VALUES (${columns.map(() => '?').join(',')})`, row);
    }
    if (digest(await snapshot(connection)) !== backup.sha256) throw new Error('Restore verification failed. Changes rolled back.');
    await connection.commit();
  } catch (error) { await connection.rollback(); throw error; }
}
