import { test } from 'node:test';
import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';
import mysql from 'mysql2/promise';
import request from 'supertest';
import { createApp } from '../src/app.js';
import { Store, databaseOptions, migrate } from '../src/db.js';
import { passwordHash } from '../src/security.js';
import { draft } from './fixtures.js';

test('real MySQL: login, CSRF, private routes, version conflict, audit rollback and logout', { skip: !process.env.MYSQL_TEST_DATABASE_URL }, async () => {
  const options = databaseOptions({ ADMIN_DATABASE_URL: process.env.MYSQL_TEST_DATABASE_URL });
  const admin = await mysql.createConnection(options);
  const database = 'shiva_admin_test_' + randomUUID().replaceAll('-', '');
  let pool;
  try {
    await admin.query(`CREATE DATABASE \`${database}\``);
    pool = mysql.createPool({ ...options, database });
    await migrate(pool); await migrate(pool);
    await pool.execute('INSERT INTO admin_users (email, password_hash) VALUES (?, ?)', ['owner@example.test', await passwordHash('local test password only')]);
    await pool.execute('INSERT INTO admin_candidates (google_place_id, name, source_state, source_district, confidence, snapshot, snapshot_sha256) VALUES (?, ?, ?, ?, ?, ?, ?)', ['test-place', 'Pilot temple', 'Madhya Pradesh', 'Ujjain', 'high', '{"discovered_name":"Original name"}', 'a'.repeat(64)]);
    const origin = 'http://127.0.0.1:5176';
    const store = new Store(pool); const app = await createApp({ store, origin }); const agent = request.agent(app);
    for (const path of ['/session', '/dashboard', '/candidates', '/candidates/1']) await request(app).get('/api' + path).expect(401);
    await request(app).post('/api/login').send({}).expect(403);
    await request(app).post('/api/login').set('Origin', 'https://evil.example').send({}).expect(403);
    await request(app).post('/api/login').set('Origin', origin).send({ email: 'owner@example.test', password: 'wrong' }).expect(401);
    const login = await agent.post('/api/login').set('Origin', origin).send({ email: 'owner@example.test', password: 'local test password only' }).expect(200);
    assert.match(login.headers['set-cookie'][0], /HttpOnly/); assert.match(login.headers['set-cookie'][0], /SameSite=Strict/);
    const csrf = login.body.csrf;
    await agent.get('/api/session').expect(200);
    await agent.post('/api/candidates/1/reviews').set('Origin', origin).send(draft()).expect(403);
    await agent.post('/api/candidates/1/reviews').set('Origin', 'https://evil.example').set('X-CSRF-Token', csrf).send(draft()).expect(403);
    const save = payload => agent.post('/api/candidates/1/reviews').set('Origin', origin).set('X-CSRF-Token', csrf).send(payload);
    await save({ ...draft(), status: 'verified' }).expect(400);
    const attempts = await Promise.all([save(draft()), save(draft())]);
    assert.deepEqual(attempts.map(r => r.status).sort(), [200, 409]);
    let record = (await agent.get('/api/candidates/1').expect(200)).body;
    assert.equal(record.revision, 1); assert.equal(record.revisions.length, 1);
    assert.equal(record.snapshot.discovered_name, 'Original name'); assert.equal(record.revisions[0].author, 'owner@example.test');
    assert.ok(Math.abs(Date.now() - Date.parse(record.revisions[0].created_at)) < 60000, 'Audit timestamps represent UTC');
    // A database audit failure must roll back the revision and candidate status together.
    await pool.query("CREATE TRIGGER fail_audit BEFORE INSERT ON admin_review_events FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'private failure detail'");
    const failed = await save({ ...draft(), version: 1, status: 'needs_evidence', rationale: 'Need independent evidence' }).expect(503);
    assert.ok(!JSON.stringify(failed.body).includes('private failure'));
    record = (await agent.get('/api/candidates/1')).body;
    assert.equal(record.revision, 1); assert.equal(record.revisions.length, 1);
    await pool.query('DROP TRIGGER fail_audit');
    await save({ ...draft(), version: 1, status: 'needs_evidence', rationale: 'Need independent evidence' }).expect(200);
    const dash = (await agent.get('/api/dashboard')).body;
    assert.equal(dash[0].status, 'needs_evidence'); assert.equal(Number(dash[0].total), 1);
    assert.equal((await agent.get('/api/candidates?district=Khandwa')).body.total, 0);
    for (const query of ['', '?district=Ujjain', '?status=needs_evidence', '?search=Pilot', '?district=Ujjain&status=needs_evidence&search=Pilot']) {
      const queue = (await agent.get('/api/candidates' + query).expect(200)).body;
      assert.equal(queue.total, 1);
      assert.equal(queue.rows.length, 1);
    }
    const pageTwo = (await agent.get('/api/candidates?page=2').expect(200)).body;
    assert.equal(pageTwo.total, 1);
    assert.equal(pageTwo.rows.length, 0);
    for (const [placeId, first, last] of [
      ['early', '2026-01-01T00:00:00+00:00', '2026-06-01T00:00:00+00:00'],
      ['late', '2026-02-01T00:00:00+00:00', '2026-05-01T00:00:00+00:00'],
    ]) await pool.execute('INSERT INTO admin_candidates (google_place_id, name, source_state, source_district, confidence, snapshot, snapshot_sha256) VALUES (?, ?, ?, ?, ?, ?, ?)', [placeId, placeId, 'Madhya Pradesh', 'Ujjain', 'high', JSON.stringify({ first_seen_at: first, last_seen_at: last }), 'b'.repeat(64)]);
    for (const [sort, expected] of [
      ['first_newest', ['late', 'early', 'Pilot temple']],
      ['first_oldest', ['early', 'late', 'Pilot temple']],
      ['last_newest', ['early', 'late', 'Pilot temple']],
      ['last_oldest', ['late', 'early', 'Pilot temple']],
    ]) {
      const queue = (await agent.get('/api/candidates?sort=' + sort).expect(200)).body;
      assert.deepEqual(queue.rows.map(row => row.name), expected);
      assert.equal(queue.rows[2].first_observed, null);
    }
    await agent.get('/api/candidates?sort=id%20DESC').expect(400);
    assert.equal((await agent.get('/api/candidates?search=%27%20OR%201%3D1--').expect(200)).body.total, 0);
    await agent.post('/api/logout').set('Origin', origin).set('X-CSRF-Token', csrf).send({}).expect(200);
    await agent.get('/api/candidates/1').expect(401);
    for (let i = 0; i < 8; i++) await request(app).post('/api/login').set('Origin', origin).send({}).expect(401);
    await request(app).post('/api/login').set('Origin', origin).send({}).expect(429);
    const restarted = await createApp({ store: new Store(pool), origin });
    await request(restarted).post('/api/login').set('Origin', origin).send({}).expect(429);
  } finally {
    if (pool) await pool.end();
    await admin.query(`DROP DATABASE IF EXISTS \`${database}\``); await admin.end();
  }
});
