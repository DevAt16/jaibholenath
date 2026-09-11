import { test } from 'node:test';
import assert from 'node:assert/strict';
import { randomUUID, createHash } from 'node:crypto';
import request from 'supertest';
import { createApp } from '../src/app.js';
import { databaseOptions } from '../src/store.js';
const origin = 'https://jaibholenath.com';
function setup(store) {
  const sessions = new Set();
  return { sessions, app: createApp({ allowedOrigin: origin, store: store || { async total(hash) {
    if (hash) sessions.add(hash);
    return sessions.size;
  } } }) };
}
test('GET never increments; retries and uppercase UUIDs share the Python-compatible hash', async () => {
  const { app, sessions } = setup();
  const token = randomUUID();
  await request(app).get('/api/visits').expect(200, { total: 0 });
  for (const id of [token, token.toUpperCase()]) {
    await request(app).post('/api/visits').set('Origin', origin).send({ session_id: id }).expect(200, { total: 1 });
  }
  assert.deepEqual([...sessions], [createHash('sha256').update(token).digest('hex')]);
  await request(app).get('/api/visits').expect(200, { total: 1 });
});
test('CORS, preflight, methods and paths are restricted', async () => {
  const { app } = setup();
  await request(app).options('/api/visits').set('Origin', origin).expect('Access-Control-Allow-Origin', origin).expect(200);
  for (const other of ['', 'https://evil.example']) {
    await request(app).post('/api/visits').set('Origin', other).send({ session_id: randomUUID() }).expect(403);
  }
  await request(app).delete('/api/visits').expect(405);
  await request(app).get('/api/private').expect(404);
});
test('invalid or excessive input cannot record visits', async () => {
  const { app, sessions } = setup();
  for (const payload of [{}, [], { session_id: 'bad' }, { session_id: randomUUID(), extra: true }, { session_id: 1 }]) {
    await request(app).post('/api/visits').set('Origin', origin).send(payload).expect(400);
  }
  await request(app).post('/api/visits').set('Origin', origin).set('Content-Type', 'application/json').send('{').expect(400);
  await request(app).post('/api/visits').set('Origin', origin).send({ large: 'x'.repeat(1024) }).expect(413);
  await request(app).post('/api/visits').set('Origin', origin).set('Content-Type', 'text/plain').send('x').expect(415);
  assert.equal(sessions.size, 0);
});
test('failures do not leak credentials or fabricate totals', async () => {
  for (const store of [{ total: async () => { throw new Error('secret password'); } }, { total: async () => -1 }]) {
    await request(setup(store).app).get('/api/visits').expect('Cache-Control', 'no-store').expect(503, { error: 'Counter unavailable' });
  }
});
test('MySQL URL credentials and configured origin are validated', () => {
  const options = databaseOptions({ VISITS_DATABASE_URL: 'mysql://user:p%40ss@localhost:3307/visits' });
  assert.equal(options.password, 'p@ss');
  assert.equal(options.port, 3307);
  assert.throws(() => databaseOptions({ VISITS_DATABASE_URL: 'postgresql://user:SECRET@host/db' }), error => !error.message.includes('SECRET'));
  assert.throws(() => createApp({ allowedOrigin: origin + '/', store: {} }));
});
