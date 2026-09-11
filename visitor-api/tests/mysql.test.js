import { test } from 'node:test';
import assert from 'node:assert/strict';
import { randomUUID, createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import mysql from 'mysql2/promise';
import { MySQLVisitStore, databaseOptions } from '../src/store.js';

test('real MySQL: concurrency, retries, rollback, and migration preserve totals', { skip: !process.env.MYSQL_TEST_DATABASE_URL }, async () => {
  const options = databaseOptions({ VISITS_DATABASE_URL: process.env.MYSQL_TEST_DATABASE_URL });
  const admin = await mysql.createConnection(options);
  const name = 'shiva_node_test_' + randomUUID().replaceAll('-', '');
  let pool;
  try {
    await admin.query(`CREATE DATABASE \`${name}\``);
    pool = mysql.createPool({ ...options, database: name });
    const statements = (await readFile(new URL('../../migrations/004_portal_visits.sql', import.meta.url), 'utf8')).split(';').filter(s => s.trim());
    for (const sql of statements) await pool.query(sql);
    const store = new MySQLVisitStore(pool);
    assert.equal(await store.total(), 0);
    const hashes = Array.from({ length: 8 }, () => createHash('sha256').update(randomUUID()).digest('hex'));
    await Promise.all([...hashes, ...hashes, ...hashes].map(h => store.total(h)));
    assert.equal(await store.total(), 8);
    assert.equal(await store.total(hashes[0]), 8);
    for (const sql of statements) await pool.query(sql);
    assert.equal(await store.total(), 8);
    // Force a failure after the session insert; transaction must undo that insert.
    await pool.query("CREATE TRIGGER reject_increment BEFORE UPDATE ON portal_visit_totals FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'test failure'");
    const failedHash = 'a'.repeat(64);
    await assert.rejects(store.total(failedHash));
    const [rows] = await pool.query('SELECT COUNT(*) AS count FROM portal_visit_sessions WHERE session_hash = ?', [failedHash]);
    assert.equal(Number(rows[0].count), 0);
    assert.equal(await store.total(), 8);
  } finally {
    if (pool) await pool.end();
    await admin.query(`DROP DATABASE IF EXISTS \`${name}\``);
    await admin.end();
  }
});
