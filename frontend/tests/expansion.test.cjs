const {test} = require('node:test');
const assert = require('node:assert/strict');
const {join} = require('node:path');
const {loadExpandedReports} = require(join(process.env.SHIVA_UI_TEST_BUILD, 'expansionData.js'));
const {summarizeCandidates} = require(join(process.env.SHIVA_UI_TEST_BUILD, 'reportLogic.js'));
const {toCandidate} = require(join(process.env.SHIVA_UI_TEST_BUILD, 'reportData.js'));

const manifest = {schema_version: 1, snapshot_id: 'a'.repeat(64), generated_at: '2026-09-29T00:00:00Z',
  baseline_candidates: 1, database_candidates: 1, overlapping_place_ids: 0,
  added_since_baseline: 1, combined_candidates: 2, geography_high_priority: 0};
const reports = summarizeCandidates(['a','b'].map(id => toCandidate({google_place_id: id,
  discovered_name: 'Shiva temple', state: 'Uttar Pradesh', district: 'Agra', confidence: 'high', confidence_score: '0.95'})));
const response = data => ({ok: true, status: 200, json: async () => structuredClone(data)});

test('missing expansion falls back without requesting a snapshot', async t => {
  t.mock.method(global, 'fetch', async () => ({ok:false, status:404}));
  assert.equal(await loadExpandedReports(), null);
});
test('unchanged manifest avoids downloading all candidates again', async t => {
  const fetch = t.mock.method(global, 'fetch', async () => response(manifest));
  assert.equal(await loadExpandedReports(manifest.snapshot_id), null);
  assert.equal(fetch.mock.calls.length, 1);
});
test('one immutable snapshot supplies candidates and matching reports', async t => {
  const urls = [];
  t.mock.method(global, 'fetch', async url => {urls.push(url); return response(url.endsWith('latest.json') ? manifest : {schema_version:1,reports});});
  const data = await loadExpandedReports();
  assert.equal(data.reports.candidates.length, 2);
  assert.equal(urls[1], `/local-expansion/snapshots/${manifest.snapshot_id}.json`);
});
test('manifest paths cannot escape the snapshot directory', async t => {
  t.mock.method(global, 'fetch', async () => response({...manifest, snapshot_id:'../../.env'}));
  await assert.rejects(loadExpandedReports(), /manifest/);
});
test('incomplete or mismatched snapshots are rejected', async t => {
  t.mock.method(global, 'fetch', async url => response(url.endsWith('latest.json') ? manifest :
    {schema_version:1, reports:{...reports,candidates:reports.candidates.slice(0,1)}}));
  await assert.rejects(loadExpandedReports(), /counts/);
});
test('transient failures reject without returning a replacement dataset', async t => {
  t.mock.method(global, 'fetch', async () => ({ok:false,status:503}));
  await assert.rejects(loadExpandedReports(), /unavailable/);
});
test('missing or partial coordinates render as unrecorded instead of a fabricated pin', async t => {
  const input = structuredClone(reports);
  input.candidates[0].latitude = '';
  input.candidates[0].longitude = 78.1;
  t.mock.method(global, 'fetch', async url => response(url.endsWith('latest.json') ? manifest : {schema_version:1,reports:input}));
  const data = await loadExpandedReports();
  assert.equal(data.reports.candidates[0].latitude, 0);
  assert.equal(data.reports.candidates[0].longitude, 0);
  assert.equal(typeof data.reports.candidates[0].confidence_score, 'number');
});
