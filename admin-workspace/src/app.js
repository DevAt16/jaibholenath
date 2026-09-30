import express from 'express';
import { fileURLToPath } from 'node:url';
import { hash, token, passwordHash, passwordMatches } from './security.js';
import { InputError } from './review.js';

export async function createApp({ store, origin, production = false }) {
  const parsed = new URL(origin);
  if (parsed.origin !== origin || (production && parsed.protocol !== 'https:')) throw new Error('Set ADMIN_ORIGIN to the exact origin (HTTPS in production).');
  const dummyPassword = await passwordHash(token());
  const app = express();
  app.disable('x-powered-by');
  app.use((req, res, next) => {
    res.set({ 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer', 'X-Frame-Options': 'DENY', 'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'", 'Permissions-Policy': 'camera=(), microphone=(), geolocation=()' });
    if (production) res.set('Strict-Transport-Security', 'max-age=31536000');
    next();
  });
  app.use('/api', (req, res, next) => {
    if (!['GET', 'HEAD'].includes(req.method)) {
      if (req.get('Origin') !== origin) return res.status(403).json({ error: 'Request origin is not allowed.' });
      if (!req.is('application/json')) return res.status(415).json({ error: 'Use application/json.' });
    }
    next();
  });
  app.use(express.json({ limit: '96kb' }));
  // One owner: an account-wide, database-backed attempt budget avoids trusting proxy IP headers.
  app.post('/api/login', async (req, res) => {
    if (!await store.loginAttempt(hash('owner-login'))) return res.status(429).json({ error: 'Too many sign-in attempts. Try again in 15 minutes.' });
    const email = typeof req.body?.email === 'string' ? req.body.email.trim().toLowerCase().slice(0, 254) : '';
    const user = await store.user(email);
    const valid = await passwordMatches(req.body?.password, user?.password_hash || dummyPassword);
    if (!user || !valid) return res.status(401).json({ error: 'Email or password is incorrect.' });
    const sessionToken = token();
    const csrf = token();
    await store.startSession(hash(sessionToken), csrf, user.id);
    res.cookie('admin_session', sessionToken, { httpOnly: true, sameSite: 'strict', secure: production, path: '/', maxAge: 8 * 60 * 60 * 1000 });
    res.json({ email: user.email, csrf });
  });
  app.use('/api', async (req, res, next) => {
    const sessionToken = req.headers.cookie?.split(';').map(x => x.trim()).find(x => x.startsWith('admin_session='))?.slice(14) || '';
    req.sessionHash = hash(sessionToken);
    req.owner = /^[a-f0-9]{64}$/.test(sessionToken) ? await store.session(req.sessionHash) : null;
    if (!req.owner) return res.status(401).json({ error: 'Please sign in to the research workspace.' });
    if (!['GET', 'HEAD'].includes(req.method) && req.get('X-CSRF-Token') !== req.owner.csrf_token) return res.status(403).json({ error: 'Session check failed. Reload and try again.' });
    next();
  });
  app.get('/api/session', (req, res) => res.json({ email: req.owner.email, csrf: req.owner.csrf_token }));
  app.post('/api/logout', async (req, res) => { await store.logout(req.sessionHash); res.clearCookie('admin_session', { path: '/', httpOnly: true, sameSite: 'strict', secure: production }); res.json({ ok: true }); });
  app.get('/api/dashboard', async (req, res) => res.json(await store.dashboard()));
  app.get('/api/candidates', async (req, res) => {
    for (const value of Object.values(req.query)) if (typeof value !== 'string' || value.length > 200) throw new InputError('Invalid filter.');
    res.json(await store.candidates(req.query));
  });
  app.param('id', (req, res, next, id) => /^[1-9]\d{0,14}$/.test(id) ? next() : next(new InputError('Invalid candidate ID.')));
  app.get('/api/candidates/:id', async (req, res) => res.json(await store.candidate(req.params.id)));
  app.post('/api/candidates/:id/reviews', async (req, res) => res.json(await store.save(req.params.id, req.owner.id, req.body)));
  app.use('/api', (req, res) => res.status(404).json({ error: 'Route not found.' }));
  app.use(express.static(fileURLToPath(new URL('../public', import.meta.url))));
  app.use((error, req, res, next) => {
    const status = error instanceof InputError ? error.status : error.type === 'entity.too.large' ? 413 : error.type === 'entity.parse.failed' ? 400 : 503;
    res.status(status).json({ error: error instanceof InputError ? error.message : status === 503 ? 'Workspace unavailable. Check the local database and try again.' : 'Invalid or oversized request.' });
  });
  return app;
}
