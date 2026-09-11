import { createApp } from './app.js';
import { createStore } from './store.js';

const port = Number(process.env.PORT || 3000);
if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('Invalid PORT');
const { store, close } = createStore();
const app = createApp({ store, allowedOrigin: process.env.VISITS_ALLOWED_ORIGIN });
const server = app.listen(port, '0.0.0.0', () => console.log(`Visitor API listening on port ${port}`));
for (const signal of ['SIGTERM', 'SIGINT']) {
  process.once(signal, () => {
    server.close(async () => { await close(); process.exit(0); });
    setTimeout(() => process.exit(1), 10000).unref();
  });
}
