import { test } from 'node:test';
import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';
import mysql from 'mysql2/promise';
import { databaseOptions, migrate, Store, jsonDocument } from '../src/db.js';
import { captureBackup, restoreBackup, tables, digest, validateBackup } from '../src/backup.js';
import { draft } from './fixtures.js';

test('backup rejects corruption, unexpected tables and malformed rows', () => {
  const data = Object.fromEntries(Object.keys(tables).map(table => [table, []]));
  const backup = { format: 'shiva-admin-backup-v1', data, sha256: digest(data) };
  assert.equal(validateBackup(backup), backup);
  assert.throws(() => validateBackup({ ...backup, sha256: 'bad' }));
  const extra = { ...data, admin_sessions: [] };
  assert.throws(() => validateBackup({ ...backup, data: extra, sha256: digest(extra) }));
  const bad = { ...data, admin_users: [['1']] };
  assert.throws(() => validateBackup({ ...backup, data: bad, sha256: digest(bad) }));
});

test('JSON documents work with MySQL objects and MariaDB text', () => {
  const doc = { name: 'महादेव', sources: [] };
  assert.deepEqual(jsonDocument(JSON.stringify(doc)), doc);
  assert.equal(jsonDocument(doc), doc);
  assert.throws(() => jsonDocument('malformed JSON'));
});

test('real MySQL: backup restores full revisions, audit and snapshot; rejects nonempty targets and rolls back failures', { skip: !process.env.MYSQL_TEST_DATABASE_URL }, async () => {
  const options = databaseOptions({ ADMIN_DATABASE_URL: process.env.MYSQL_TEST_DATABASE_URL });
  const admin = await mysql.createConnection(options);
  const names = ['source', 'restore', 'failure'].map(label => `shiva_admin_test_${label}_${randomUUID().replaceAll('-', '')}`);
  const connections = [];
  let pool;
  try {
    for (const name of names) {
      await admin.query(`CREATE DATABASE \`${name}\` CHARACTER SET utf8mb4`);
      connections.push(await mysql.createConnection({ ...options, database: name }));
    }
    const [source, target, failure] = connections;
    await migrate(source);
    await source.execute('INSERT INTO admin_users (email, password_hash) VALUES (?, ?)', ['owner@example.test', 'private-password-hash']);
    await source.execute('INSERT INTO admin_candidates (google_place_id, name, source_state, source_district, confidence, snapshot, snapshot_sha256) VALUES (?, ?, ?, ?, ?, ?, ?)', ['restore-place', 'महादेव', 'Madhya Pradesh', 'Ujjain', 'high', JSON.stringify({ discovered_name: 'महादेव', latitude: '23.18' }), 'b'.repeat(64)]);
    pool = mysql.createPool({ ...options, database: names[0] });
    const store = new Store(pool);
    await store.save(1, 1, { ...draft(), name: 'महादेव', status: 'needs_evidence', rationale: 'Exact pin unresolved' });
    await store.startSession('a'.repeat(64), 'b'.repeat(64), 1);
    const backup = await captureBackup(source);
    assert.equal(backup.data.admin_record_revisions.length, 1);
    assert.equal(backup.data.admin_review_events.length, 1);
    assert.equal(backup.data.admin_sessions, undefined);
    await restoreBackup(target, backup);
    assert.equal((await captureBackup(target)).sha256, backup.sha256);
    assert.equal(Number((await target.query('SELECT COUNT(*) AS total FROM admin_sessions'))[0][0].total), 0);
    await assert.rejects(restoreBackup(target, backup), /empty admin tables/);
    assert.equal((await captureBackup(target)).sha256, backup.sha256);
    // A failure after users and candidates were inserted must roll everything back.
    const broken = structuredClone(backup);
    broken.data.admin_record_revisions[0][3] = '999999';
    broken.sha256 = digest(broken.data);
    await assert.rejects(restoreBackup(failure, broken));
    for (const table of Object.keys(tables)) assert.equal(Number((await failure.query(`SELECT COUNT(*) AS total FROM ${table}`))[0][0].total), 0);
  } finally {
    if (pool) await pool.end();
    for (const connection of connections) await connection.end();
    for (const name of names) await admin.query(`DROP DATABASE IF EXISTS \`${name}\``);
    await admin.end();
  }
});
