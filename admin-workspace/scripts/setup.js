import { createPool, migrate } from '../src/db.js';
import { passwordHash } from '../src/security.js';
import { createHash } from 'node:crypto';
import { createInterface } from 'node:readline/promises';
const pool = createPool();
try {
  const command = process.argv[2];
  if (command === 'migrate') {
    await migrate(pool);
    console.log('Admin tables ready. Discovery and visitor tables were not modified.');
  } else if (command === 'owner') {
    const rl = createInterface({ input: process.stdin, output: process.stdout });
    const email = (await rl.question('Owner email: ')).trim().toLowerCase();
    rl.close();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) || email.length > 254) throw new Error('Enter a valid email.');
    if (!process.stdin.isTTY) throw new Error('Run owner setup in an interactive terminal.');
    const hidden = () => new Promise(resolve => {
      process.stdout.write('Password (14+ characters, hidden): ');
      process.stdin.setRawMode(true); process.stdin.resume();
      let value = '';
      const onData = bytes => {
        for (const ch of bytes.toString()) {
          if (ch === '\u0003') process.exit(130);
          if (ch === '\r' || ch === '\n') { process.stdin.off('data', onData); process.stdin.setRawMode(false); process.stdin.pause(); process.stdout.write('\n'); resolve(value); return; }
          if (ch === '\u007f') value = value.slice(0, -1); else if (ch >= ' ') value += ch;
        }
      };
      process.stdin.on('data', onData);
    });
    const password = await hidden();
    const confirmation = await hidden();
    if (password !== confirmation) throw new Error('Passwords did not match.');
    const encoded = await passwordHash(password);
    const conn = await pool.getConnection();
    try {
      await conn.beginTransaction();
      const [users] = await conn.execute('SELECT id, email FROM admin_users FOR UPDATE');
      if (users.length && users[0].email !== email) throw new Error('This workspace already has an owner.');
      await conn.execute('INSERT INTO admin_users (email, password_hash) VALUES (?, ?) ON DUPLICATE KEY UPDATE password_hash = VALUES(password_hash)', [email, encoded]);
      await conn.execute('DELETE FROM admin_sessions');
      await conn.commit();
    } catch (error) { await conn.rollback(); throw error; } finally { conn.release(); }
    console.log('Owner ready. Existing sessions have been revoked.');
  } else if (command === 'seed') {
    if (process.env.NODE_ENV === 'production') throw new Error('Pilot snapshot seeding is for local development only.');
    let input = '';
    for await (const chunk of process.stdin) { input += chunk; if (input.length > 20_000_000) throw new Error('Seed exceeds safe limit.'); }
    const rows = JSON.parse(input);
    if (!Array.isArray(rows) || rows.length > 2000) throw new Error('Seed exceeds 2,000 candidates.');
    let added = 0;
    for (const row of rows) {
      if (row.state !== 'Madhya Pradesh' || !['Ujjain', 'Khandwa', 'Gwalior'].includes(row.district)) throw new Error('Outside pilot scope.');
      const snapshot = JSON.stringify(row);
      const [result] = await pool.execute('INSERT INTO admin_candidates (google_place_id, name, source_state, source_district, confidence, snapshot, snapshot_sha256) VALUES (?, ?, ?, ?, ?, ?, ?) ON DUPLICATE KEY UPDATE id = id', [row.google_place_id, row.discovered_name, row.state, row.district, row.confidence, snapshot, createHash('sha256').update(snapshot).digest('hex')]);
      if (result.affectedRows === 1) added++;
    }
    console.log(`Pilot snapshot loaded (${rows.length} input rows). Existing snapshots and reviews retained.`);
  } else throw new Error('Use migrate, owner or seed.');
} catch (error) { console.error(error.code ? `Setup failed (${error.code}). Check local configuration.` : error.message); process.exitCode = 1; }
finally { await pool.end(); }
