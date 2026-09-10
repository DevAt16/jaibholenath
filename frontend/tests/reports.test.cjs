const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync, existsSync } = require("node:fs");
const { join } = require("node:path");
const {
  defaultFilters,
  discoveryStory,
  districtKey,
  filterCandidates,
  districtOptions,
  paginate,
  summarizeCandidates,
  mapsUrl,
  toCsv,
  importReportFiles,
} = require(join(process.env.SHIVA_UI_TEST_BUILD, "reportLogic.js"));
const {
  parseCsv,
  toCandidate,
  validateReportRows,
  loadRealReports,
  loadSampleReports,
} = require(join(process.env.SHIVA_UI_TEST_BUILD, "reportData.js"));
const candidate = (changes = {}) =>
  toCandidate({
    google_place_id: "place-a",
    discovered_name: "Mahadev Temple",
    state: "Uttar Pradesh",
    district: "Varanasi",
    confidence: "high",
    confidence_score: "0.9",
    ...changes,
  });
const file = (name, text) => ({
  name,
  size: text.length,
  text: async () => text,
});
const sample = (name) =>
  readFileSync(
    join(__dirname, "../public/sample-reports", `sample_${name}.csv`),
    "utf8",
  );

test("district stories preserve report totals separately from a partial candidate extract", () => {
  const full = summarizeCandidates([
    candidate(),
    candidate({ google_place_id: "b", confidence: "medium" }),
  ]);
  const story = discoveryStory({ ...full, candidates: full.candidates.slice(0, 1) });
  assert.equal(story.summary.unique_google_place_ids, 2);
  assert.equal(story.districts[0].unique_google_place_ids, 2);
  assert.equal(story.loadedByDistrict.get(districtKey(story.districts[0])), 1);
});

test("district stories distinguish same-named districts and derive candidate-only summaries", () => {
  const story = discoveryStory({
    national: null, states: [], districts: [],
    candidates: [
      candidate({ district: "Pratapgarh" }),
      candidate({ google_place_id: "b", state: "Rajasthan", district: "Pratapgarh" }),
    ],
  });
  assert.equal(story.summary.unique_google_place_ids, 2);
  assert.equal(story.districts.length, 2);
  assert.equal(story.loadedByDistrict.size, 2);
  for (const district of story.districts) {
    assert.equal(story.loadedByDistrict.get(districtKey(district)), 1);
  }
});

test("district stories handle empty and summary-only reports without inventing candidate coverage", () => {
  const empty = discoveryStory({ national: null, states: [], districts: [], candidates: [] });
  assert.equal(empty.summary, null);
  assert.deepEqual(empty.districts, []);
  const data = summarizeCandidates([candidate()]);
  const summaryOnly = discoveryStory({ ...data, candidates: [] });
  assert.equal(summaryOnly.districts.length, 1);
  assert.equal(summaryOnly.loadedByDistrict.size, 0);
});

test("state shortcuts exclude cross-state source-query and address matches", () => {
  const rows = [
    candidate(),
    candidate({
      google_place_id: "b",
      state: "Bihar",
      district: "Siwan",
      source_query: "Uttar Pradesh temples",
      discovered_address: "near Uttar Pradesh",
    }),
  ];
  assert.deepEqual(
    filterCandidates(rows, { ...defaultFilters, state: "Uttar Pradesh" }).map(
      (row) => row.google_place_id,
    ),
    ["place-a"],
  );
});
test("district and confidence filters intersect with the selected state", () => {
  const rows = [
    candidate({ district: "Pratapgarh" }),
    candidate({
      google_place_id: "b",
      state: "Rajasthan",
      district: "Pratapgarh",
    }),
    candidate({
      google_place_id: "c",
      district: "Pratapgarh",
      confidence: "medium",
    }),
  ];
  assert.equal(
    filterCandidates(rows, {
      ...defaultFilters,
      state: "Uttar Pradesh",
      district: "Pratapgarh",
      confidence: "high",
    }).length,
    1,
  );
});
test("district options only include the selected state's districts", () => {
  assert.deepEqual(
    districtOptions(
      [candidate(), candidate({ state: "Bihar", district: "Siwan" })],
      "Uttar Pradesh",
    ),
    ["Varanasi"],
  );
});
test("search matches words across names and locations without matching source evidence", () => {
  const rows = [
    candidate(),
    candidate({
      google_place_id: "b",
      discovered_name: "Temple",
      state: "Bihar",
      district: "Siwan",
      source_query: "Mahadev Varanasi",
    }),
  ];
  assert.equal(
    filterCandidates(rows, { ...defaultFilters, query: " VARANASI mahadev " })
      .length,
    1,
  );
});
test("multilingual names remain searchable", () => {
  const rows = [candidate({ discovered_name: "श्री शिव मंदिर" })];
  assert.equal(
    filterCandidates(rows, { ...defaultFilters, query: "शिव" }).length,
    1,
  );
});
test("sorting is deterministic and does not mutate the input", () => {
  const rows = [
    candidate({
      google_place_id: "b",
      discovered_name: "B temple",
      confidence: "medium",
    }),
    candidate({ discovered_name: "A temple" }),
  ];
  assert.equal(
    filterCandidates(rows, defaultFilters)[0].google_place_id,
    "place-a",
  );
  assert.equal(
    filterCandidates(rows, { ...defaultFilters, sort: "name" })[0]
      .discovered_name,
    "A temple",
  );
  assert.equal(rows[0].google_place_id, "b");
});
test("recent sort orders valid observations before missing dates", () => {
  const rows = [
    candidate(),
    candidate({
      google_place_id: "b",
      last_seen_at: "2026-05-07T10:00:00+05:30",
    }),
  ];
  assert.equal(
    filterCandidates(rows, { ...defaultFilters, sort: "recent" })[0]
      .google_place_id,
    "b",
  );
});
test("every match is accessible through bounded pages, including the last partial page", () => {
  const rows = Array.from({ length: 61 }, (_, i) => i);
  const retrieved = [1, 2, 3].flatMap((page) => paginate(rows, page, 25).rows);
  assert.deepEqual(retrieved, rows);
  assert.deepEqual(paginate(rows, 9, 25), {
    rows: rows.slice(50),
    page: 3,
    pages: 3,
    start: 51,
    end: 61,
  });
});
test("pagination handles empty results and invalid page sizes", () => {
  assert.deepEqual(paginate([], 7), {
    rows: [],
    page: 1,
    pages: 1,
    start: 0,
    end: 0,
  });
  assert.equal(paginate([1, 2], -2, -10).page, 1);
});
test("summaries deduplicate Place IDs and keep identically named districts separate", () => {
  const a = candidate({ district: "Pratapgarh" });
  const b = candidate({
    google_place_id: "b",
    state: "Rajasthan",
    district: "Pratapgarh",
    confidence: "medium",
  });
  const result = summarizeCandidates([a, a, b]);
  assert.equal(result.candidates.length, 2);
  assert.equal(result.national.duplicates_removed, 1);
  assert.equal(result.national.high_confidence_shiva, 1);
  assert.equal(result.national.medium_confidence_shiva_candidates, 1);
  assert.equal(result.districts.length, 2);
});
test("Google Maps links preserve trusted source links and reject unsafe destinations", () => {
  const trusted = "https://maps.google.com/?cid=123";
  assert.equal(mapsUrl(candidate({ google_maps_uri: trusted })), trusted);
  for (const uri of [
    "javascript:alert(1)",
    "https://maps.google.com.evil.test",
    "https://evil.test",
    "https://user:secret@maps.google.com/",
  ]) {
    const url = new URL(mapsUrl(candidate({ google_maps_uri: uri })));
    assert.equal(url.hostname, "www.google.com");
    assert.equal(url.searchParams.get("query_place_id"), "place-a");
  }
});
test("CSV parser handles BOM, CRLF, quoted commas, escaped quotes and multiline fields", () => {
  const rows = parseCsv(
    '\uFEFFname,address\r\n"Shiva, temple","Line 1\r\nLine ""2"""\r\n',
  );
  assert.deepEqual(rows, [
    { name: "Shiva, temple", address: 'Line 1\r\nLine "2"' },
  ]);
});
test("malformed CSVs fail with useful errors", () => {
  assert.throws(() => parseCsv('name,address\n"unclosed,address'), /unclosed/);
  assert.throws(() => parseCsv("name,name\nx,y"), /unique/);
  assert.throws(() => parseCsv("name,address\nx,y,z"), /columns/);
});
test("CSV export preserves multilingual and multiline content", () => {
  const rows = [{ name: 'शिव "Temple", mandir', address: "A\nB", score: 0.9 }];
  assert.deepEqual(parseCsv(toCsv(rows)), [{ ...rows[0], score: "0.9" }]);
});
test("CSV export treats spreadsheet formulas as text while keeping numeric coordinates", () => {
  const csv = toCsv([{ name: '=HYPERLINK("bad")', latitude: -12.1 }]);
  const parsed = parseCsv(csv)[0];
  assert.equal(parsed.name[0], "'");
  assert.equal(parsed.latitude, "-12.1");
});
test("validation rejects misleading filenames, invalid scores, and negative report counts", () => {
  assert.throws(
    () => validateReportRows("candidates", [{ arbitrary: "data" }]),
    /Missing columns/,
  );
  assert.throws(
    () =>
      validateReportRows("candidates", [
        { ...candidate(), confidence_score: "NaN" },
      ]),
    /Invalid/,
  );
  const row = parseCsv(sample("national_summary"))[0];
  assert.throws(
    () =>
      validateReportRows("national", [{ ...row, duplicates_removed: "-1" }]),
    /Invalid count/,
  );
});
test("candidate-only imports generate all summaries", async () => {
  const result = await importReportFiles([
    file("candidates.csv", sample("candidate_review")),
  ]);
  assert.equal(result.reports.candidates.length, 3);
  assert.equal(result.reports.national.unique_google_place_ids, 3);
  assert.ok(result.reports.districts.length > 0);
});
test("full report imports preserve supplied observation and duplicate counts", async () => {
  const result = await importReportFiles([
    file("candidates.csv", sample("candidate_review")),
    file("national.csv", sample("national_summary")),
    file("states.csv", sample("state_counts")),
    file("districts.csv", sample("district_counts")),
  ]);
  assert.equal(result.reports.national.total_discovered_candidates, 9);
  assert.equal(result.reports.national.duplicates_removed, 5);
});
test("summary-only imports do not retain stale candidates", async () => {
  const result = await importReportFiles([
    file("national.csv", sample("national_summary")),
  ]);
  assert.deepEqual(result.reports.candidates, []);
  assert.deepEqual(result.reports.states, []);
});
test("imports reject ambiguous, oversized and invalid batches before returning data", async () => {
  await assert.rejects(
    importReportFiles(Array(5).fill(file("x.csv", "a\nb"))),
    /one to four/,
  );
  await assert.rejects(
    importReportFiles([
      {
        name: "x.csv",
        size: 101 * 1024 * 1024,
        text: async () => {
          throw new Error("must not read");
        },
      },
    ]),
    /100 MB/,
  );
  await assert.rejects(
    importReportFiles([
      file("national.csv", sample("national_summary")),
      file("second-national.csv", sample("national_summary")),
    ]),
    /one report/,
  );
  await assert.rejects(
    importReportFiles([
      file("candidates.csv", sample("candidate_review")),
      file("national.csv", "x\ny"),
    ]),
    /Missing columns/,
  );
});
test("both report loaders detect missing files and HTML fallback responses", async () => {
  const original = global.fetch;
  try {
    global.fetch = async () => ({ ok: false });
    await assert.rejects(loadRealReports(), /unavailable/);
    await assert.rejects(loadSampleReports(), /unavailable/);
    global.fetch = async () => ({
      ok: true,
      text: async () => "<!doctype html><html></html>",
    });
    await assert.rejects(loadRealReports(), /no data rows/);
  } finally {
    global.fetch = original;
  }
});
test(
  "real baseline CSVs parse and validate when available locally",
  {
    skip: !existsSync(
      join(__dirname, "../public/real-reports/candidate_review.csv"),
    ),
  },
  () => {
    for (const [type, name] of [
      ["national", "national_summary"],
      ["states", "state_counts"],
      ["districts", "district_counts"],
      ["candidates", "candidate_review"],
    ]) {
      const rows = parseCsv(
        readFileSync(
          join(__dirname, "../public/real-reports", `${name}.csv`),
          "utf8",
        ),
      );
      validateReportRows(type, rows);
      if (type === "candidates") {
        assert.ok(rows.length > 0);
        assert.equal(
          new Set(rows.map((row) => row.google_place_id)).size,
          rows.length,
        );
      }
    }
  },
);
