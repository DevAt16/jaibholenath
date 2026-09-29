import { test } from 'node:test';
import assert from 'node:assert/strict';
import { Store } from '../src/db.js';

test('candidate date order is selected from a fixed list and applies before pagination', async () => {
  const calls = [];
  const store = new Store({ execute: async ({ sql }, params) => {
    calls.push({ sql, params });
    return [calls.length % 2 ? [] : [{ total: 0 }]];
  } });
  for (const sort of ['first_newest', 'first_oldest', 'last_newest', 'last_oldest']) {
    calls.length = 0;
    await store.candidates({ sort, district: 'Ujjain', page: '2' });
    assert.match(calls[0].sql, /ORDER BY .* LIMIT 20 OFFSET 20/s);
    assert.match(calls[0].sql, sort.startsWith('first') ? /\$\.first_seen_at/ : /\$\.last_seen_at/);
    assert.match(calls[0].sql, sort.endsWith('oldest') ? / IS NULL\) ASC, .* ASC, id ASC/s : / DESC, id DESC/);
    assert.deepEqual(calls[0].params, ['Ujjain']);
  }
  calls.length = 0;
  await assert.rejects(store.candidates({ sort: 'id DESC; DROP TABLE admin_candidates' }), /Invalid candidate sort order/);
  assert.equal(calls.length, 0);
});
