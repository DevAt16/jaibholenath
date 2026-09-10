const { test } = require("node:test");
const assert = require("node:assert/strict");
const { join } = require("node:path");
const { observedWindow } = require(
  join(process.env.SHIVA_UI_TEST_BUILD, "reportLogic.js"),
);

test("observed dates distinguish missing data from valid observations", () => {
  assert.equal(observedWindow([]), "Not recorded");
  assert.equal(
    observedWindow([{ first_seen_at: "", last_seen_at: "invalid" }]),
    "Not recorded",
  );
  assert.equal(
    observedWindow([{ first_seen_at: "", last_seen_at: "2026-05-07T10:00:00+05:30" }]),
    "7 May 2026",
  );
});

test("observed dates find both extremes in unordered records and ignore invalid dates", () => {
  assert.equal(
    observedWindow([
      { first_seen_at: "2026-05-07T10:00:00+05:30", last_seen_at: "2026-05-09T10:00:00+05:30" },
      { first_seen_at: "2026-05-05T10:00:00+05:30", last_seen_at: "invalid" },
      { first_seen_at: "2026-05-06T10:00:00+05:30", last_seen_at: "2026-05-08T10:00:00+05:30" },
    ]),
    "5 May 2026 – 9 May 2026",
  );
});

test("observed dates use India time and collapse observations on the same local day", () => {
  assert.equal(
    observedWindow([
      { first_seen_at: "2026-05-06T20:00:00Z", last_seen_at: "2026-05-07T18:00:00Z" },
    ]),
    "7 May 2026",
  );
});
