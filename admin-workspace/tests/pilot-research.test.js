import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { preparePilotReviews } from '../src/pilot-research.js';
const read = name => JSON.parse(readFileSync(new URL(`../../docs/pilot-research/${name}`, import.meta.url), 'utf8'));
const manifest = read('six-record-drafts.json');
const followup = read('FOLLOWUP_2026_09_28.json');
test('six dossiers become needs-evidence reviews without promoting discovery geography or excluded sources', () => {
  const rows = preparePilotReviews(manifest, followup);
  assert.equal(rows.length, 6);
  for (const row of rows) {
    assert.equal(row.document.status, 'needs_evidence');
    for (const field of ['state', 'district', 'latitude', 'longitude']) assert.equal(row.document[field], '');
    assert.equal(row.document.duplicateChecked, false);
    assert.match(row.document.rationale, /AI-assisted desk review/);
    assert.match(row.document.rationale, /not an owner verification/);
    assert.ok(row.document.sources.every(source => source.visibility === 'private'));
  }
  assert.deepEqual(rows.find(row => row.dossierId === 'K01').document.sources, []);
  assert.equal(rows[0].document.sources[0].accessed, manifest.sources.intach.accessed);
});
test('conversion refuses expanded scope, duplicate places, changed outcomes and missing follow-up', () => {
  const change = fn => { const copy = structuredClone(manifest); fn(copy); return copy; };
  assert.throws(() => preparePilotReviews(change(m => m.records.push(m.records[0])), followup));
  assert.throws(() => preparePilotReviews(change(m => m.records[1] = m.records[0]), followup));
  assert.throws(() => preparePilotReviews(change(m => m.records[0].suggested_review_status = 'verified'), followup));
  const missing = structuredClone(followup); missing.records[0].dossier_id = 'missing';
  assert.throws(() => preparePilotReviews(manifest, missing));
});
