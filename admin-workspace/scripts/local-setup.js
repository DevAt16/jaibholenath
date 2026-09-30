// Explicitly local-only convenience setup. Never reads the project's production .env.
import mysql from 'mysql2/promise';
import { randomBytes } from 'node:crypto';
import { writeFile, access } from 'node:fs/promises';
import { migrate } from '../src/db.js';
import { passwordHash } from '../src/security.js';
const root = new URL('../', import.meta.url);
try { await access(new URL('.env', root)); throw new Error('Local .env already exists; use migrate/owner instead of overwriting it.'); }
catch (error) { if (error.code !== 'ENOENT') throw error; }
const connection = await mysql.createConnection({ host: '127.0.0.1', port: 33316, user: 'root' });
const database = 'shiva_admin_dev';
const password = randomBytes(24).toString('hex');
const ownerPassword = randomBytes(20).toString('base64url');
try {
  // Fail if a development database already exists. Never reset existing reviews.
  await connection.query(`CREATE DATABASE ${database} CHARACTER SET utf8mb4`);
  await connection.query(`USE ${database}`);
  await migrate(connection);
  await connection.execute('INSERT INTO admin_users (email, password_hash) VALUES (?, ?)', ['pawar.devashish@gmail.com', await passwordHash(ownerPassword)]);
  await connection.query("CREATE USER 'shiva_admin_dev'@'127.0.0.1' IDENTIFIED BY ?", [password]);
  await connection.query("GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, REFERENCES ON shiva_admin_dev.* TO 'shiva_admin_dev'@'127.0.0.1'");
  await writeFile(new URL('.env', root), `ADMIN_DATABASE_URL=mysql://shiva_admin_dev:${password}@127.0.0.1:33316/${database}\nADMIN_ORIGIN=http://127.0.0.1:5176\nHOST=127.0.0.1\nPORT=5176\n`, { mode: 0o600, flag: 'wx' });
  await writeFile(new URL('.local-owner-password', root), ownerPassword + '\n', { mode: 0o600, flag: 'wx' });
  console.log('Local owner and isolated database ready. Temporary password saved in ignored .local-owner-password; use npm run owner to replace it.');
} finally { await connection.end(); }
