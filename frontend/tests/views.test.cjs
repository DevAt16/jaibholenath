const { test } = require("node:test");
const assert = require("node:assert/strict");
const { join } = require("node:path");
const { createElement } = require("react");
const { renderToStaticMarkup } = require("react-dom/server");
const { Overview, Candidates, Geography, Reports, CandidateDetail } = require(
  join(process.env.SHIVA_UI_TEST_BUILD, "App.js"),
);
const { defaultFilters, summarizeCandidates } = require(
  join(process.env.SHIVA_UI_TEST_BUILD, "reportLogic.js"),
);
const { toCandidate } = require(
  join(process.env.SHIVA_UI_TEST_BUILD, "reportData.js"),
);
const noop = () => {};
const rows = Array.from({ length: 61 }, (_, index) =>
  toCandidate({
    google_place_id: `id-${index}`,
    discovered_name: `Temple record ${index}`,
    district: "Sri Potti Sriramulu Nellore",
    state: "Andhra Pradesh",
    confidence: "high",
    confidence_score: "0.9",
    first_seen_at: "2026-05-05 10:00:00+05:30",
    last_seen_at: "2026-05-07 10:00:00+05:30",
  }),
);
const reports = summarizeCandidates(rows);
const empty = { national: null, candidates: [], states: [], districts: [] };
const render = (component, props) =>
  renderToStaticMarkup(createElement(component, props));
const candidateProps = {
  reports,
  filters: defaultFilters,
  onFilters: noop,
  page: 2,
  onPage: noop,
  pageSize: 25,
  onPageSize: noop,
  onSelect: noop,
  matches: rows,
};

test("candidate rendering shows the requested page and preserves full location names", () => {
  const html = render(Candidates, candidateProps);
  assert.match(html, /View Temple record 25,/);
  assert.match(html, /View Temple record 49,/);
  assert.doesNotMatch(html, /View Temple record 24,/);
  assert.doesNotMatch(html, /View Temple record 50,/);
  assert.match(html, /Sri Potti Sriramulu Nellore/);
  assert.match(html, /61<\/strong> matching candidates/);
  assert.match(html, /aria-label="Next page"/);
});
test("candidate rendering handles an empty filtered result without stale rows", () => {
  const html = render(Candidates, {
    ...candidateProps,
    filters: { ...defaultFilters, state: "Bihar" },
    matches: [],
  });
  assert.match(html, /No candidates match these filters/);
  assert.doesNotMatch(html, /View Temple record/);
  assert.match(html, /Clear filters/);
});
test("the overview distinguishes unavailable confidence summaries from zero counts", () => {
  const html = render(Overview, {
    reports: { ...empty, states: reports.states },
    onBrowse: noop,
    onSelect: noop,
    onGeography: noop,
  });
  assert.match(html, /No confidence summary loaded/);
  assert.match(html, /<strong>—<\/strong>/);
});
test("public-facing views explain the discovery dataset and observed window", () => {
  const html = render(Overview, {
    reports,
    onBrowse: noop,
    onSelect: noop,
    onGeography: noop,
  });
  assert.match(html, /Discovery dataset/);
  assert.match(html, /Google Places is a discovery source/);
  assert.match(html, /Observed/);
  assert.match(html, /May 2026/);
});
test("the opening story explains candidates and connects district counts to confidence evidence", () => {
  const html = render(Overview, {
    reports, onBrowse: noop, onSelect: noop, onGeography: noop,
  });
  assert.match(html, /Discovering Shiva temples/);
  assert.match(html, /A candidate is a place returned by our searches/);
  assert.match(html, /Explore your district/);
  assert.match(html, /Sri Potti Sriramulu Nellore, Andhra Pradesh/);
  assert.match(html, /61<\/strong><span>candidate records in the district summary/);
  assert.match(html, /View district records/);
  assert.match(html, /District labels come from the search location/);
  assert.match(html, /How discovery works/);
});
test("the district story explains unloaded records and disables browsing an unavailable extract", () => {
  const html = render(Overview, {
    reports: { ...reports, candidates: [] },
    onBrowse: noop, onSelect: noop, onGeography: noop,
  });
  assert.match(html, /button class="button primary" disabled="">View district records/);
  assert.match(html, /Individual records for this district are not loaded/);
  assert.match(html, /61<\/strong><span>candidate records in the district summary/);
});
test("report notes render with 100,000 candidates without exceeding argument limits", () => {
  const data = summarizeCandidates(
    Array.from({ length: 100_000 }, (_, index) => ({
      ...rows[0],
      google_place_id: `large-${index}`,
    })),
  );
  for (const [component, props] of [
    [Overview, { onBrowse: noop, onSelect: noop, onGeography: noop }],
    [Reports, { source: "Test reports", busy: false, onUpload: noop, onLoad: noop }],
  ]) {
    const html = render(component, { ...props, reports: data });
    assert.match(html, /5 May 2026 – 7 May 2026/);
    assert.match(html, /1,00,000 candidate records/);
  }
});
test("all workspace views render both populated and empty datasets", () => {
  for (const data of [reports, empty]) {
    assert.ok(
      render(Overview, {
        reports: data,
        onBrowse: noop,
        onSelect: noop,
        onGeography: noop,
      }),
    );
    assert.ok(render(Geography, { reports: data, onBrowse: noop }));
    assert.ok(
      render(Reports, {
        reports: data,
        source: "Test reports",
        busy: false,
        onUpload: noop,
        onLoad: noop,
      }),
    );
  }
});
test("detail panel includes complete evidence and accessible close/navigation controls", () => {
  const html = render(CandidateDetail, {
    candidate: {
      ...rows[0],
      classification_reason: "Matched high-confidence Shiva terms: mahadev",
      source_query: "Mahadev temple in Nellore",
    },
    onClose: noop,
    onNext: noop,
  });
  assert.match(html, /aria-labelledby="detail-title"/);
  assert.match(html, /Matched high-confidence Shiva terms: mahadev/);
  assert.match(html, /Mahadev temple in Nellore/);
  assert.match(html, /aria-label="Close candidate details"/);
  assert.match(html, /query_place_id=id-0/);
  assert.match(html, /class="mark-dot"/);
});
