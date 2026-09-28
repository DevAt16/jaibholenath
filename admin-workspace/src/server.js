import { createPool, Store } from './db.js';
import { createApp } from './app.js';
const pool = createPool();
const production = process.env.NODE_ENV === 'production';
const app = await createApp({ store: new Store(pool), origin: process.env.ADMIN_ORIGIN || 'http://127.0.0.1:5176', production });
const server = app.listen(Number(process.env.PORT || 5176), process.env.HOST || '127.0.0.1', () => console.log('Research workspace listening on configured host and port.'));
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => server.close(async () => { await pool.end(); process.exit(0); }));
