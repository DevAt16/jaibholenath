const { test } = require("node:test");
const assert = require("node:assert/strict");
const { join } = require("node:path");
const { visitSession, requestVisits } = require(join(process.env.SHIVA_UI_TEST_BUILD, "visitCounterClient.js"));

test("visit sessions survive reloads and tolerate blocked storage", () => {
  const id = "57f573d1-7c33-42b8-980f-32cb7fa86ac7";
  let stored;
  const storage = { getItem: () => stored, setItem: (_, value) => { stored = value; } };
  assert.equal(visitSession(storage, () => id), id);
  assert.equal(visitSession(storage, () => { throw new Error("Must reuse session"); }), id);
  const blocked = { getItem() { throw new Error(); }, setItem() { throw new Error(); } };
  assert.equal(visitSession(blocked, () => id), id);
});

test("recording uses a session token, while reading the shared total is read-only", async () => {
  const calls = [];
  const fetcher = async (url, options) => {
    calls.push({ url, ...options });
    return { ok: true, json: async () => ({ total: 127 }) };
  };
  assert.equal(await requestVisits("/api/visits", "session", fetcher), 127);
  assert.equal(await requestVisits("/api/visits", undefined, fetcher), 127);
  assert.equal(calls[0].method, "POST");
  assert.deepEqual(JSON.parse(calls[0].body), { session_id: "session" });
  assert.equal(calls[1].method, "GET");
  assert.equal(calls[1].body, undefined);
  assert.equal(calls[0].credentials, "omit");
});

test("counter failures and invalid totals never become a misleading zero", async () => {
  for (const total of [-1, "12", null, 1.5, Number.MAX_SAFE_INTEGER + 1]) {
    await assert.rejects(requestVisits("/api/visits", undefined, async () => ({
      ok: true, json: async () => ({ total }),
    })));
  }
  await assert.rejects(requestVisits("/api/visits", undefined, async () => ({ ok: false })));
  assert.equal(await requestVisits("/api/visits", undefined, async () => ({
    ok: true, json: async () => ({ total: 0 }),
  })), 0);
});
