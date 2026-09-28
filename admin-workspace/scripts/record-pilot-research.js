import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { isDeepStrictEqual } from 'node:util';
import { createPool, Store, jsonDocument } from '../src/db.js';
import { captureBackup } from '../src/backup.js';
import { preparePilotReviews } from '../src/pilot-research.js';

const apply = process.argv[2] === '--apply';
let pool;
try {
  if (process.argv.length > (apply ? 3 : 2)) throw new Error('Use no arguments for preview, or --apply to save needs-evidence revisions.');
  if (process.env.NODE_ENV === 'production') throw new Error('This pilot script is for the development workspace only.');
  const root = new URL('../../', import.meta.url);
  const manifest = JSON.parse(await readFile(new URL('docs/pilot-research/six-record-drafts.json', root), 'utf8'));
  const followup = JSON.parse(await readFile(new URL('docs/pilot-research/FOLLOWUP_2026_09_28.json', root), 'utf8'));
  const csv = await readFile(new URL('frontend/public/real-reports/candidate_review.csv', root));
  if (createHash('sha256').update(csv).digest('hex') !== manifest.source_sha256) throw new Error('Original discovery CSV changed; review candidate provenance first.');
  const plan = preparePilotReviews(manifest, followup);
  pool = createPool();
  const store = new Store(pool);
  const owners = await store.query('SELECT id FROM admin_users');
  if (owners.length !== 1) throw new Error('Expected exactly one pilot owner for audit attribution.');
  // Complete preflight for all records before the first mutation.
  for (const item of plan) {
    const rows = await store.query('SELECT id, snapshot FROM admin_candidates WHERE google_place_id = ?', [item.placeId]);
    if (rows.length !== 1) throw new Error(`Missing candidate ${item.dossierId}.`);
    const snapshot = jsonDocument(rows[0].snapshot);
    if (Object.entries(item.snapshot).some(([key, value]) => snapshot[key] !== value)) throw new Error(`Discovery snapshot differs for ${item.dossierId}.`);
    item.id = rows[0].id;
    const record = await store.candidate(item.id);
    item.skip = record.revision === 1 && isDeepStrictEqual(record.revisions[0]?.document, item.document);
    if (record.revision !== 0 && !item.skip) throw new Error(`Existing review for ${item.dossierId}; use the editor to preserve the owner's work.`);
  }
  console.log(JSON.stringify({ apply, records: plan.map(item => ({ dossier: item.dossierId, candidate: item.id, status: 'needs_evidence', action: item.skip ? 'already recorded' : 'create revision 1' })) }));
  if (apply && plan.some(item => !item.skip)) {
    const connection = await pool.getConnection();
    try {
      const backup = await captureBackup(connection);
      const directory = new URL('../private-backups/', import.meta.url);
      await mkdir(directory, { recursive: true, mode: 0o700 });
      const file = new URL(`before-research-${Date.now()}.json`, directory);
      await writeFile(file, JSON.stringify(backup) + '\n', { flag: 'wx', mode: 0o600 });
      console.log(`Private pre-review backup saved: ${file.pathname}`);
    } finally { connection.release(); }
    // Each Store.save is atomic and enforces version 0 under a row lock. A
    // retry skips identical completed records; it never overwrites other work.
    for (const item of plan.filter(item => !item.skip)) {
      await store.save(item.id, owners[0].id, item.input);
      console.log(`${item.dossierId}: needs_evidence revision 1 saved (AI-assisted desk review).`);
    }
  }
} catch (error) {
  console.error(error.code ? `Pilot review failed (${error.code}). Check configuration; rerun preview before retrying.` : error.message);
  process.exitCode = 1;
} finally { if (pool) await pool.end(); }
