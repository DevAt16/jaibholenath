import mysql from 'mysql2/promise';
import { readFile, writeFile, stat } from 'node:fs/promises';
import { randomUUID } from 'node:crypto';
import { databaseOptions } from '../src/db.js';
import { captureBackup, restoreBackup, validateBackup, maxBytes } from '../src/backup.js';

const [command, file] = process.argv.slice(2);
let connection;
try {
  if (!file || !['backup', 'restore-check', 'restore'].includes(command) || process.argv.length !== 4) throw new Error('Use backup.js backup FILE, restore-check FILE or restore FILE.');
  if (command === 'backup') {
    connection = await mysql.createConnection(databaseOptions());
    const backup = await captureBackup(connection);
    await writeFile(file, JSON.stringify(backup) + '\n', { flag: 'wx', mode: 0o600 });
    console.log(JSON.stringify({ file, sha256: backup.sha256, rows: Object.fromEntries(Object.entries(backup.data).map(([table, rows]) => [table, rows.length])) }));
  } else {
    if ((await stat(file)).size > maxBytes) throw new Error('Backup exceeds 64 MiB.');
    const backup = validateBackup(JSON.parse(await readFile(file, 'utf8')));
    const options = databaseOptions({ ADMIN_DATABASE_URL: process.env.ADMIN_RESTORE_DATABASE_URL });
    if (!['localhost', '127.0.0.1', '[::1]'].includes(options.host)) throw new Error('Recovery checks require a local disposable MySQL server.');
    connection = await mysql.createConnection(options);
    const database = 'shiva_admin_restore_' + randomUUID().replaceAll('-', '');
    await connection.query(`CREATE DATABASE \`${database}\` CHARACTER SET utf8mb4`);
    let verified = false;
    try {
      await connection.query(`USE \`${database}\``);
      await restoreBackup(connection, backup);
      verified = true;
      console.log(JSON.stringify({ restored: true, checksumVerified: backup.sha256, database, retained: command === 'restore' }));
    } finally { if (!verified || command === 'restore-check') await connection.query(`DROP DATABASE \`${database}\``); }
  }
} catch (error) {
  console.error(error.code ? `Backup operation failed (${error.code}); check configuration and permissions.` : error.message);
  process.exitCode = 1;
} finally { if (connection) await connection.end(); }
