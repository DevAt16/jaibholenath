import express from 'express';
import { createHash } from 'node:crypto';

export function createApp({ store, allowedOrigin }) {
  const origin = new URL(allowedOrigin);
  if (origin.origin !== allowedOrigin || !['https:', 'http:'].includes(origin.protocol)) {
    throw new Error('VISITS_ALLOWED_ORIGIN must be an exact http(s) origin without a trailing slash.');
  }
  const app = express();
  app.disable('x-powered-by');
  app.use((req, res, next) => {
    res.set({ 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', Vary: 'Origin' });
    const supplied = req.get('Origin');
    if (supplied === allowedOrigin) res.set('Access-Control-Allow-Origin', allowedOrigin);
    next();
  });
  app.get('/health', (req, res) => res.json({ status: 'ok' }));
  app.all('/api/visits', (req, res, next) => {
    const origin = req.get('Origin');
    if ((origin && origin !== allowedOrigin) || (['POST', 'OPTIONS'].includes(req.method) && !origin)) {
      return res.status(403).json({ error: 'Origin not allowed' });
    }
    if (req.method === 'OPTIONS') {
      res.set({ 'Access-Control-Allow-Methods': 'GET, POST, OPTIONS', 'Access-Control-Allow-Headers': 'Content-Type' });
      return res.json({});
    }
    if (!['GET', 'POST'].includes(req.method)) return res.set('Allow', 'GET, POST, OPTIONS').status(405).json({ error: 'Method not allowed' });
    if (req.method === 'POST' && !req.is('application/json')) return res.status(415).json({ error: 'JSON required' });
    next();
  }, express.json({ limit: 1024, inflate: false }), async (req, res) => {
    let hash;
    if (req.method === 'POST') {
      const body = req.body;
      if (!body || Array.isArray(body) || Object.keys(body).length !== 1 ||
          typeof body.session_id !== 'string' || !/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(body.session_id)) {
        return res.status(400).json({ error: 'Invalid session ID' });
      }
      hash = createHash('sha256').update(body.session_id.toLowerCase()).digest('hex');
    }
    try {
      const total = await store.total(hash);
      if (!Number.isSafeInteger(total) || total < 0) throw new Error('Invalid total');
      res.json({ total });
    } catch {
      res.status(503).json({ error: 'Counter unavailable' });
    }
  });
  app.use((req, res) => res.status(404).json({ error: 'Not found' }));
  app.use((error, req, res, next) => {
    const status = error.type === 'entity.too.large' ? 413 : error.type === 'encoding.unsupported' ? 415 : 400;
    res.status(status).json({ error: 'Invalid request body' });
  });
  return app;
}
