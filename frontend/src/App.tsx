import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import {
  ArrowDownToLine,
  ArrowRight,
  ArrowUpRight,
  Building2,
  CalendarDays,
  Check,
  ChevronLeft,
  ChevronRight,
  Compass,
  Copy,
  Database,
  FileSpreadsheet,
  FolderOpen,
  Info,
  LayoutDashboard,
  MapPin,
  Search,
  ShieldCheck,
  Upload,
  X,
} from "lucide-react";
import { loadRealReports, loadSampleReports } from "./reportData";
import { portalVersion } from "./portalVersion";
import { VisitCounter } from "./VisitCounter";
import type { Candidate, ReportData, StateCount } from "./reportData";
import {
  defaultFilters,
  discoveryStory,
  districtKey,
  districtOptions,
  filterCandidates,
  formatNumber,
  mapsUrl,
  importReportFiles,
  observedWindow,
  paginate,
  percent,
  summarizeCandidates,
  toCsv,
} from "./reportLogic";
import type { CandidateFilters } from "./reportLogic";

type View = "overview" | "candidates" | "geography" | "reports";
const navigation = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "candidates", label: "Candidates", icon: Compass },
  { id: "geography", label: "Geography", icon: MapPin },
  { id: "reports", label: "Reports", icon: FileSpreadsheet },
] as const;
const emptyReports: ReportData = {
  national: null,
  states: [],
  districts: [],
  candidates: [],
};
const reportNames: Record<keyof ReportData, string> = {
  national: "National summary",
  states: "State counts",
  districts: "District counts",
  candidates: "Candidate records",
};
const confidenceLabels: Record<string, string> = {
  high: "High",
  medium: "Medium",
  low: "Low",
};
const getView = (): View =>
  navigation.some((item) => item.id === location.hash.slice(1))
    ? (location.hash.slice(1) as View)
    : "overview";

function ShivaMark({ size = 30 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M4 27.5h24" />
      <path d="M7 27.5V13.8L16 5l9 8.8v13.7" />
      <path d="M10 13.8h12M12.2 10.8h7.6M14.3 7.9h3.4" />
      <path d="M16 2.6v7.1" />
      <path d="M12.8 4.8c0 2.2 1.2 3.8 3.2 3.8s3.2-1.6 3.2-3.8" />
      <path d="M12 27.5v-5.7a4 4 0 0 1 8 0v5.7" />
      <circle className="mark-dot" cx="25.5" cy="24" r="3" />
    </svg>
  );
}

function Badge({ confidence }: { confidence: string }) {
  return (
    <span className={`confidence-badge confidence-${confidence}`}>
      <span aria-hidden="true" />
      {confidenceLabels[confidence] ?? "Unclassified"}
    </span>
  );
}

function download(filename: string, rows: object[]) {
  const url = URL.createObjectURL(
    new Blob(["\uFEFF", toCsv(rows)], { type: "text/csv;charset=utf-8;" }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function EmptyState({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="empty-state">
      <Search size={28} strokeWidth={1.4} />
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}

function DataScopeNote({ reports }: { reports: ReportData }) {
  const observed = useMemo(
    () => observedWindow(reports.candidates),
    [reports.candidates],
  );
  const source = reports.national?.source || (reports.candidates.length ? "Google Places API" : "Not recorded");
  return (
    <section className="methodology-note data-scope-note" aria-label="About these counts">
      <span className="methodology-icon"><Info size={19} /></span>
      <div className="methodology-copy">
        <div className="methodology-heading">
          <h2>About these counts</h2>
          <span className="scope-badge">Discovery dataset</span>
        </div>
        <p>
          Google Places is a discovery source, not a verified temple census. Place IDs are deduplicated; confidence describes automated name matching and still needs independent verification.
        </p>
        <div className="methodology-facts">
          <span><strong>Source</strong>{source}</span>
          <span><CalendarDays size={14} /><strong>Observed</strong>{observed}</span>
          <span><strong>Coverage</strong>{reports.candidates.length ? `${formatNumber(reports.candidates.length)} candidate records` : "No candidate records loaded"}</span>
        </div>
      </div>
    </section>
  );
}

function Pagination({
  page,
  pages,
  start,
  end,
  total,
  onChange,
}: {
  page: number;
  pages: number;
  start: number;
  end: number;
  total: number;
  onChange: (page: number) => void;
}) {
  return (
    <div className="pagination">
      <span>
        {formatNumber(start)}–{formatNumber(end)} of {formatNumber(total)}
      </span>
      <div>
        <button
          className="icon-button"
          aria-label="Previous page"
          disabled={page <= 1}
          onClick={() => onChange(page - 1)}
        >
          <ChevronLeft size={18} />
        </button>
        <span>
          Page <strong>{formatNumber(page)}</strong> of {formatNumber(pages)}
        </span>
        <button
          className="icon-button"
          aria-label="Next page"
          disabled={page >= pages}
          onClick={() => onChange(page + 1)}
        >
          <ChevronRight size={18} />
        </button>
      </div>
    </div>
  );
}

function StateRanking({
  states,
  onSelect,
  limit = 5,
}: {
  states: StateCount[];
  onSelect: (state: string) => void;
  limit?: number;
}) {
  const sorted = useMemo(
    () =>
      [...states]
        .sort((a, b) => b.unique_google_place_ids - a.unique_google_place_ids)
        .slice(0, limit),
    [states, limit],
  );
  const max = sorted[0]?.unique_google_place_ids ?? 0;
  return (
    <div className="state-ranking">
      {sorted.length ? (
        sorted.map((state, index) => (
          <button
            key={state.state}
            className="state-rank"
            onClick={() => onSelect(state.state)}
            aria-label={`Browse candidates in ${state.state}`}
          >
            <span className="rank-number">
              {String(index + 1).padStart(2, "0")}
            </span>
            <span className="rank-body">
              <span className="rank-label">
                <span>{state.state}</span>
                <strong>{formatNumber(state.unique_google_place_ids)}</strong>
              </span>
              <span className="rank-track">
                <span
                  style={{
                    width: `${percent(state.unique_google_place_ids, max)}%`,
                  }}
                />
              </span>
            </span>
            <ChevronRight size={16} />
          </button>
        ))
      ) : (
        <EmptyState title="No geographic report loaded">
          Import a state report or candidate records to explore locations.
        </EmptyState>
      )}
    </div>
  );
}

function CandidateRows({
  candidates,
  onSelect,
}: {
  candidates: Candidate[];
  onSelect: (candidate: Candidate) => void;
}) {
  return (
    <div className="candidate-list">
      <div className="candidate-columns" aria-hidden="true">
        <span>Candidate</span>
        <span>Location</span>
        <span>Confidence</span>
        <span />
      </div>
      {candidates.map((candidate) => (
        <button
          type="button"
          className="candidate-row"
          key={candidate.google_place_id}
          onClick={() => onSelect(candidate)}
          aria-label={`View ${candidate.discovered_name}, ${candidate.district}, ${candidate.state}`}
          aria-haspopup="dialog"
        >
          <span className="candidate-identity">
            <span className="place-icon">
              <Building2 size={18} strokeWidth={1.4} />
            </span>
            <span className="candidate-name">{candidate.discovered_name}</span>
          </span>
          <span className="candidate-location">
            <span>{candidate.district}</span>
            <span>{candidate.state}</span>
          </span>
          <Badge confidence={candidate.confidence} />
          <ChevronRight className="row-chevron" size={17} />
        </button>
      ))}
    </div>
  );
}

function CandidateDetail({
  candidate,
  onClose,
  onPrevious,
  onNext,
}: {
  candidate: Candidate;
  onClose: () => void;
  onPrevious?: () => void;
  onNext?: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState(false);
  useEffect(() => {
    const dialog = ref.current!;
    const focused = document.activeElement as HTMLElement | null;
    dialog.showModal();
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = overflow;
      dialog.close();
      focused?.focus();
    };
  }, []);
  useEffect(() => {
    setCopied(false);
    setCopyError(false);
    ref.current?.querySelector(".detail-body")?.scrollTo(0, 0);
  }, [candidate.google_place_id]);
  async function copyId() {
    try {
      await navigator.clipboard.writeText(candidate.google_place_id);
      setCopied(true);
    } catch {
      setCopyError(true);
    }
  }
  const date = (value: string) =>
    Number.isNaN(Date.parse(value))
      ? "Not recorded"
      : new Intl.DateTimeFormat("en-IN", { dateStyle: "medium" }).format(
          new Date(value),
        );
  return (
    <dialog
      ref={ref}
      className="detail-panel"
      aria-labelledby="detail-title"
      onCancel={onClose}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="detail-shell">
        <div className="detail-toolbar">
          <span>
            <Compass size={17} /> Candidate details
          </span>
          <button
            autoFocus
            className="icon-button"
            onClick={onClose}
            aria-label="Close candidate details"
          >
            <X size={20} />
          </button>
        </div>
        <div className="detail-body">
          <span className="detail-place-icon">
          <ShivaMark size={34} />
          </span>
          <h2 id="detail-title">{candidate.discovered_name}</h2>
          <p className="detail-location">
            <MapPin size={16} />
            {candidate.district}, {candidate.state}
          </p>
          <a
            className="button primary maps-button"
            href={mapsUrl(candidate)}
            target="_blank"
            rel="noreferrer"
          >
            Open in Google Maps
            <ArrowUpRight size={17} />
          </a>
          <section className="confidence-evidence">
            <div>
              <h3>Shiva confidence</h3>
              <Badge confidence={candidate.confidence} />
            </div>
            <p>
              Classification score{" "}
              <strong>{candidate.confidence_score.toFixed(2)} / 1.00</strong>
            </p>
            <div
              className={`evidence-track confidence-${candidate.confidence}`}
            >
              <span
                style={{
                  width: `${Math.max(0, Math.min(1, candidate.confidence_score)) * 100}%`,
                }}
              />
            </div>
            <h4>Why this classification?</h4>
            <p>
              {candidate.classification_reason ||
                "No classification evidence was recorded."}
            </p>
            <small>
              Automated classification, pending independent verification.
            </small>
          </section>
          <section className="detail-section">
            <h3>Location</h3>
            <dl>
              <dt>Address</dt>
              <dd>{candidate.discovered_address || "Not recorded"}</dd>
              <dt>Coordinates</dt>
              <dd>
                {candidate.latitude || candidate.longitude
                  ? `${candidate.latitude.toFixed(5)}, ${candidate.longitude.toFixed(5)}`
                  : "Not recorded"}
              </dd>
            </dl>
          </section>
          <section className="detail-section">
            <h3>Discovery evidence</h3>
            <dl>
              <dt>Source</dt>
              <dd>Google Places API</dd>
              <dt>Search query</dt>
              <dd>{candidate.source_query || "Not recorded"}</dd>
            </dl>
            <div className="date-grid">
              <div>
                <span>First observed</span>
                <strong>{date(candidate.first_seen_at)}</strong>
              </div>
              <div>
                <span>Last observed</span>
                <strong>{date(candidate.last_seen_at)}</strong>
              </div>
            </div>
          </section>
          <section className="detail-section">
            <h3>Google Place ID</h3>
            <div className="place-id">
              <code>{candidate.google_place_id}</code>
              <button
                className="icon-button"
                aria-label={copied ? "Place ID copied" : "Copy Place ID"}
                onClick={copyId}
              >
                {copied ? <Check size={16} /> : <Copy size={16} />}
              </button>
            </div>
            <span role="status" className="copy-status">
              {copied
                ? "Place ID copied."
                : copyError
                  ? "Copy unavailable. Select the Place ID to copy it."
                  : ""}
            </span>
          </section>
        </div>
        <div className="detail-footer">
          <button
            className="button secondary"
            disabled={!onPrevious}
            onClick={onPrevious}
          >
            <ChevronLeft size={16} />
            Previous
          </button>
          <button
            className="button secondary"
            disabled={!onNext}
            onClick={onNext}
          >
            Next candidate
            <ChevronRight size={16} />
          </button>
        </div>
      </div>
    </dialog>
  );
}

function Overview({
  reports,
  onBrowse,
  onSelect,
  onGeography,
}: {
  reports: ReportData;
  onBrowse: (filters?: Partial<CandidateFilters>) => void;
  onSelect: (candidate: Candidate) => void;
  onGeography: () => void;
}) {
  const story = useMemo(() => discoveryStory(reports), [reports]);
  const [selectedDistrict, setSelectedDistrict] = useState("");
  const district = story.districts.find((row) => districtKey(row) === selectedDistrict)
    ?? story.districts[0];
  const storyStates = [...new Set(story.districts.map((row) => row.state))].sort();
  const localDistricts = story.districts
    .filter((row) => row.state === district?.state)
    .sort((a, b) => a.district.localeCompare(b.district));
  const loadedInDistrict = district
    ? story.loadedByDistrict.get(districtKey(district)) ?? 0
    : 0;
  const national = reports.national;
  const hasSummary = national !== null || reports.candidates.length > 0;
  const summary = story.summary ?? summarizeCandidates([]).national!;
  const stateCount = new Set(
    [...reports.states, ...reports.districts, ...reports.candidates].map(
      (record) => record.state,
    ),
  ).size;
  const preview = useMemo(
    () => filterCandidates(reports.candidates, defaultFilters).slice(0, 4),
    [reports.candidates],
  );
  const confidence = [
    {
      id: "high",
      name: "High confidence",
      count: summary.high_confidence_shiva,
      description: "Strong Shiva name matches",
    },
    {
      id: "medium",
      name: "Medium confidence",
      count: summary.medium_confidence_shiva_candidates,
      description: "Candidates for closer review",
    },
    {
      id: "low",
      name: "Low confidence",
      count: summary.low_confidence_possible_temples,
      description: "Limited Shiva-specific evidence",
    },
  ];
  return (
    <>
      <section className="story-hero" aria-labelledby="story-title">
        <div className="story-introduction">
          <span className="eyebrow">THE STORY BEHIND THE DISCOVERY</span>
          <h1 id="story-title">Discovering Shiva temples,<br /> district by district.</h1>
          <p>
            What can local searches tell us about likely Shiva temples across India?
            This project brings together Google Places results so you can explore
            the names, places and evidence behind each discovery.
          </p>
          <p className="story-definition">
            A candidate is a place returned by our searches. Its name is checked
            for Shiva-related terms; its identity still needs independent verification.
          </p>
          <button className="button story-browse" onClick={() => onBrowse()}>
            Browse all records <ArrowRight size={17} />
          </button>
        </div>
        <div className="district-story" aria-labelledby="district-story-title">
          <span className="eyebrow">MAKE IT LOCAL</span>
          <h2 id="district-story-title">Explore your district</h2>
          <p>Choose a district to see what its searches brought into this report.</p>
          {district ? (
            <>
              <div className="story-selectors">
                <label>
                  State / union territory
                  <select
                    value={district.state}
                    onChange={(event) => {
                      const first = story.districts.find((row) => row.state === event.target.value);
                      if (first) setSelectedDistrict(districtKey(first));
                    }}
                  >
                    {storyStates.map((state) => <option key={state}>{state}</option>)}
                  </select>
                </label>
                <label>
                  District
                  <select
                    value={districtKey(district)}
                    onChange={(event) => setSelectedDistrict(event.target.value)}
                  >
                    {localDistricts.map((row) => (
                      <option key={districtKey(row)} value={districtKey(row)}>{row.district}</option>
                    ))}
                  </select>
                </label>
              </div>
              <div className="district-story-result" role="status" aria-live="polite" aria-atomic="true">
                <h3>{district.district}, {district.state}</h3>
                <p className="district-story-total">
                  <strong>{formatNumber(district.unique_google_place_ids)}</strong>
                  <span>{district.unique_google_place_ids === 1 ? "candidate record" : "candidate records"} in the district summary</span>
                </p>
                <div className="confidence-distribution district-story-chart" aria-hidden="true">
                  <span className="segment-high" style={{ flexGrow: district.high_confidence_shiva }} />
                  <span className="segment-medium" style={{ flexGrow: district.medium_confidence_shiva_candidates }} />
                  <span className="segment-low" style={{ flexGrow: district.low_confidence_possible_temples }} />
                </div>
                <p>
                  <strong>{formatNumber(district.high_confidence_shiva)}</strong>{" "}
                  {district.high_confidence_shiva === 1 ? "has" : "have"} strong Shiva name matches;
                  {" "}<strong>{formatNumber(district.medium_confidence_shiva_candidates)}</strong>{" "}
                  {district.medium_confidence_shiva_candidates === 1 ? "has" : "have"} medium confidence
                  and <strong>{formatNumber(district.low_confidence_possible_temples)}</strong>{" "}
                  {district.low_confidence_possible_temples === 1 ? "has" : "have"} limited Shiva-specific evidence.
                </p>
              </div>
              <button
                className="button primary"
                disabled={!loadedInDistrict}
                onClick={() => onBrowse({ state: district.state, district: district.district })}
              >
                View district records <ArrowRight size={17} />
              </button>
              {loadedInDistrict < district.unique_google_place_ids && (
                <p className="story-extract-note">
                  {loadedInDistrict
                    ? `${formatNumber(loadedInDistrict)} of these candidate records ${loadedInDistrict === 1 ? "is" : "are"} loaded for browsing.`
                    : "Individual records for this district are not loaded. Import its candidate CSV in Reports to inspect the evidence."}
                </p>
              )}
            </>
          ) : (
            <p className="story-empty">Load a district report or candidate CSV in Reports to begin exploring.</p>
          )}
        </div>
        <p className="story-location-note">
          <Info size={16} aria-hidden="true" />
          District labels come from the search location. They have not been checked
          against district boundaries. These are discovery counts, not a verified temple census.
        </p>
      </section>
      <div className="metrics-grid">
        <section>
          <span>
            <Database size={16} />
            Unique candidates
          </span>
          <strong>
            {hasSummary ? formatNumber(summary.unique_google_place_ids) : "—"}
          </strong>
          <small>Distinct Google Place IDs</small>
        </section>
        <section>
          <span>
            <ShieldCheck size={16} />
            High confidence
          </span>
          <strong>
            {hasSummary ? formatNumber(summary.high_confidence_shiva) : "—"}
            {hasSummary && (
              <em>
                {percent(
                  summary.high_confidence_shiva,
                  summary.unique_google_place_ids,
                )}
                %
              </em>
            )}
          </strong>
          <small>Automated Shiva classification</small>
        </section>
        <section>
          <span>
            <MapPin size={16} />
            States & union territories
          </span>
          <strong>{formatNumber(stateCount)}</strong>
          <small>Represented in this report</small>
        </section>
        <section>
          <span>
            <MapPin size={16} />
            Districts in this report
          </span>
          <strong>
            {story.districts.length ? formatNumber(story.districts.length) : "—"}
          </strong>
          <small>Grouped by search location</small>
        </section>
      </div>
      <section className="story-insights" aria-labelledby="story-insights-title">
        <div className="story-section-heading">
          <span className="eyebrow">READING THE PATTERNS</span>
          <h2 id="story-insights-title">What does this discovery tell us?</h2>
        </div>
        <div className="story-insight-grid">
          <article>
            <span className="story-chapter">01 / REACH</span>
            <h3>A broad starting point</h3>
            <p>{story.districts.length
              ? `The loaded report groups discoveries under ${formatNumber(story.districts.length)} districts. Each group opens a different set of places to investigate.`
              : "District summaries will show how discoveries are distributed across search locations."}</p>
            <button className="text-button" onClick={onGeography}>Explore the geography <ArrowRight size={16} /></button>
          </article>
          <article>
            <span className="story-chapter">02 / EVIDENCE</span>
            <h3>Names offer clues</h3>
            <p>{hasSummary && summary.unique_google_place_ids > 0
              ? `${percent(summary.high_confidence_shiva, summary.unique_google_place_ids)}% of candidate records have strong Shiva name matches. This measures an automated naming signal, not the chance that a temple is verified.`
              : "Confidence describes how strongly a place name matches Shiva-related terms. It does not verify the place."}</p>
            <button className="text-button" onClick={() => onBrowse({ confidence: "high" })}>Inspect strong matches <ArrowRight size={16} /></button>
          </article>
          <article>
            <span className="story-chapter">03 / INTERPRETATION</span>
            <h3>Fewer results leave questions</h3>
            <p>A smaller district count does not establish that it has fewer temples. Search wording, available listings and result limits can affect what is discovered.</p>
            <p className="story-insight-takeaway">Use these patterns to guide further investigation.</p>
          </article>
        </div>
      </section>
      <div className="overview-grid">
        <section className="panel geography-preview">
          <div className="panel-heading">
            <div>
              <h2>How discovery varies by state</h2>
              <p>Most candidate records by assigned search state</p>
            </div>
            <button className="text-button" onClick={onGeography}>
              View all
              <ArrowUpRight size={16} />
            </button>
          </div>
          <StateRanking
            states={reports.states}
            onSelect={(state) => onBrowse({ state })}
          />
        </section>
        <section className="panel">
          <div className="panel-heading">
            <div>
              <h2>Confidence at a glance</h2>
              <p>How the candidate names were classified</p>
            </div>
            <ShieldCheck size={19} />
          </div>
          {hasSummary ? (
            <>
              <div
                className="confidence-distribution"
                aria-label="Confidence distribution"
              >
                {confidence.map((item) => (
                  <span
                    key={item.id}
                    className={`segment-${item.id}`}
                    style={{ flexGrow: item.count }}
                  />
                ))}
              </div>
              <div className="confidence-rows">
                {confidence.map((item) => (
                  <button
                    key={item.id}
                    className="confidence-summary"
                    onClick={() => onBrowse({ confidence: item.id })}
                  >
                    <span className={`confidence-dot segment-${item.id}`} />
                    <span>
                      <strong>{item.name}</strong>
                      <small>{item.description}</small>
                    </span>
                    <span>
                      <strong>{formatNumber(item.count)}</strong>
                      <small>
                        {percent(item.count, summary.unique_google_place_ids)}%
                      </small>
                    </span>
                    <ChevronRight size={15} />
                  </button>
                ))}
              </div>
            </>
          ) : (
            <EmptyState title="No confidence summary loaded">
              Import a national summary or candidate records to see the
              breakdown.
            </EmptyState>
          )}
          <div className="panel-note">
            <Info size={15} />
            <span>
              Confidence indicates a likely match. It does not confirm a
              temple’s identity.
            </span>
          </div>
        </section>
      </div>
      <section className="panel preview-panel">
        <div className="panel-heading">
          <div>
            <h2>The places behind the numbers</h2>
            <p>Open a record to read its name, source query and classification evidence.</p>
          </div>
          <button className="text-button" onClick={() => onBrowse()}>
            View candidates
            <ArrowRight size={16} />
          </button>
        </div>
        {preview.length ? (
          <CandidateRows candidates={preview} onSelect={onSelect} />
        ) : (
          <EmptyState title="No candidate records loaded">
            Open Reports to load a candidate CSV.
          </EmptyState>
        )}
      </section>
      <section className="story-method" aria-labelledby="story-method-title">
        <div className="story-section-heading">
          <span className="eyebrow">FROM A SEARCH TO A RECORD</span>
          <h2 id="story-method-title">How discovery works</h2>
        </div>
        <ol>
          <li><strong>Search locations</strong><p>Look for Shiva-related names through Google Places.</p></li>
          <li><strong>Combine results</strong><p>Bring the search observations into one dataset.</p></li>
          <li><strong>Remove repeats</strong><p>Keep one candidate per Google Place ID.</p></li>
          <li><strong>Classify names</strong><p>Group candidates by the strength of their name matches.</p></li>
          <li><strong>Review evidence</strong><p>Explore each record. Independent verification is still needed.</p></li>
        </ol>
      </section>
      <DataScopeNote reports={reports} />
    </>
  );
}

function Candidates({
  reports,
  filters,
  onFilters,
  page,
  onPage,
  pageSize,
  onPageSize,
  onSelect,
  matches,
}: {
  reports: ReportData;
  filters: CandidateFilters;
  onFilters: (filters: Partial<CandidateFilters>) => void;
  page: number;
  onPage: (page: number) => void;
  pageSize: number;
  onPageSize: (size: number) => void;
  onSelect: (candidate: Candidate) => void;
  matches: Candidate[];
}) {
  const states = useMemo(
    () =>
      [
        ...new Set(reports.candidates.map((candidate) => candidate.state)),
      ].sort(),
    [reports.candidates],
  );
  const districts = useMemo(
    () => districtOptions(reports.candidates, filters.state),
    [reports.candidates, filters.state],
  );
  const paged = paginate(matches, page, pageSize);
  const activeFilters = [
    filters.query && { key: "query", label: `Search: ${filters.query}` },
    filters.state && { key: "state", label: filters.state },
    filters.district && { key: "district", label: filters.district },
    filters.confidence && {
      key: "confidence",
      label: `${confidenceLabels[filters.confidence]} confidence`,
    },
  ].filter(Boolean) as { key: keyof CandidateFilters; label: string }[];
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">EXPLORE & REVIEW</span>
          <h1>
            Candidates
            <span className="heading-count">
              {formatNumber(reports.candidates.length)}
            </span>
          </h1>
          <p>Find likely Shiva temples and inspect their discovery evidence.</p>
        </div>
        <button
          className="button secondary"
          disabled={!matches.length}
          onClick={() => download("filtered_candidate_review.csv", matches)}
        >
          <ArrowDownToLine size={17} />
          Export results
        </button>
      </div>
      <section className="panel candidate-workspace">
        <div className="filter-toolbar">
          <label className="search-field">
            <Search size={19} />
            <input
              type="search"
              aria-label="Search candidates"
              placeholder="Search by temple name or location…"
              value={filters.query}
              onChange={(event) => onFilters({ query: event.target.value })}
            />
            <kbd>/</kbd>
          </label>
          <div className="filter-selects">
            <label>
              State / union territory
              <select
                value={filters.state}
                onChange={(event) =>
                  onFilters({ state: event.target.value, district: "" })
                }
              >
                <option value="">All states & territories</option>
                {states.map((state) => (
                  <option key={state}>{state}</option>
                ))}
              </select>
            </label>
            <label>
              District
              <select
                value={filters.district}
                onChange={(event) =>
                  onFilters({ district: event.target.value })
                }
              >
                <option value="">All districts</option>
                {districts.map((district) => (
                  <option key={district}>{district}</option>
                ))}
              </select>
            </label>
            <label>
              Shiva confidence
              <select
                value={filters.confidence}
                onChange={(event) =>
                  onFilters({ confidence: event.target.value })
                }
              >
                <option value="">All confidence levels</option>
                <option value="high">High confidence</option>
                <option value="medium">Medium confidence</option>
                <option value="low">Low confidence</option>
              </select>
            </label>
            <label>
              Sort by
              <select
                value={filters.sort}
                onChange={(event) =>
                  onFilters({
                    sort: event.target.value as CandidateFilters["sort"],
                  })
                }
              >
                <option value="confidence">Highest confidence</option>
                <option value="name">Name A–Z</option>
                <option value="recent">Last observed</option>
              </select>
            </label>
          </div>
          {activeFilters.length > 0 && (
            <div className="filter-chips">
              {activeFilters.map((filter) => (
                <button
                  key={filter.key}
                  onClick={() =>
                    onFilters(
                      filter.key === "state"
                        ? { state: "", district: "" }
                        : { [filter.key]: "" },
                    )
                  }
                >
                  {filter.label}
                  <X size={13} />
                </button>
              ))}
              <button
                className="clear-filters"
                onClick={() => onFilters(defaultFilters)}
              >
                Clear filters
              </button>
            </div>
          )}
        </div>
        <div className="results-heading">
          <span role="status" aria-live="polite">
            <strong>{formatNumber(matches.length)}</strong> matching candidates
          </span>
          <label>
            Show
            <select
              aria-label="Rows per page"
              value={pageSize}
              onChange={(event) => {
                onPageSize(Number(event.target.value));
                onPage(1);
              }}
            >
              <option value={25}>25</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
            </select>
            per page
          </label>
        </div>
        {paged.rows.length ? (
          <CandidateRows candidates={paged.rows} onSelect={onSelect} />
        ) : (
          <EmptyState
            title={
              reports.candidates.length
                ? "No candidates match these filters"
                : "No candidate records loaded"
            }
          >
            {reports.candidates.length ? (
              <>
                Try a broader name or location, or{" "}
                <button
                  className="text-button"
                  onClick={() => onFilters(defaultFilters)}
                >
                  clear your filters
                </button>
                .
              </>
            ) : (
              "Open Reports to load candidate records."
            )}
          </EmptyState>
        )}
        <Pagination {...paged} total={matches.length} onChange={onPage} />
      </section>
      <p className="workspace-footnote">
        <Info size={14} />
        These are discovery candidates from Google Places, pending independent
        verification.
      </p>
    </>
  );
}

function Geography({
  reports,
  onBrowse,
}: {
  reports: ReportData;
  onBrowse: (filters?: Partial<CandidateFilters>) => void;
}) {
  const [state, setState] = useState("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const states = useMemo(
    () =>
      [
        ...new Set([
          ...reports.states.map((item) => item.state),
          ...reports.districts.map((item) => item.state),
        ]),
      ].sort(),
    [reports],
  );
  const districts = useMemo(
    () =>
      reports.districts
        .filter(
          (district) =>
            (!state || district.state === state) &&
            district.district
              .toLocaleLowerCase()
              .includes(query.trim().toLocaleLowerCase()),
        )
        .sort((a, b) => b.unique_google_place_ids - a.unique_google_place_ids),
    [reports.districts, state, query],
  );
  const paged = paginate(districts, page, 15);
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">FOLLOW THE GEOGRAPHY</span>
          <h1>Geographic discovery</h1>
          <p>Explore where candidates appear in the loaded reports.</p>
        </div>
        <span className="quiet-label">
          <MapPin size={16} />
          {formatNumber(reports.districts.length)} district records
        </span>
      </div>
      <div className="geography-grid">
        <section className="panel">
          <div className="panel-heading">
            <div>
              <h2>States & union territories</h2>
              <p>Select a state to explore its candidates</p>
            </div>
          </div>
          <StateRanking
            states={reports.states}
            limit={reports.states.length}
            onSelect={(selected) => onBrowse({ state: selected })}
          />
        </section>
        <section className="panel districts-panel">
          <div className="panel-heading">
            <div>
              <h2>District breakdown</h2>
              <p>Ranked by unique discovery candidates</p>
            </div>
          </div>
          <div className="district-filters">
            <label className="search-field">
              <Search size={17} />
              <input
                aria-label="Search districts"
                type="search"
                placeholder="Find a district…"
                value={query}
                onChange={(event) => {
                  setQuery(event.target.value);
                  setPage(1);
                }}
              />
            </label>
            <select
              aria-label="Filter districts by state"
              value={state}
              onChange={(event) => {
                setState(event.target.value);
                setPage(1);
              }}
            >
              <option value="">All states & territories</option>
              {states.map((name) => (
                <option key={name}>{name}</option>
              ))}
            </select>
          </div>
          <div className="district-results" role="status">
            {formatNumber(districts.length)} matching districts
          </div>
          <div className="district-list">
            <div className="district-columns">
              <span>District</span>
              <span>Unique</span>
              <span>High confidence</span>
              <span />
            </div>
            {paged.rows.map((district) => (
              <button
                className="district-row"
                key={JSON.stringify([district.state, district.district])}
                onClick={() =>
                  onBrowse({
                    state: district.state,
                    district: district.district,
                  })
                }
                aria-label={`Browse ${district.district}, ${district.state}`}
              >
                <span>
                  <strong>{district.district}</strong>
                  <small>{district.state}</small>
                </span>
                <strong>
                  {formatNumber(district.unique_google_place_ids)}
                </strong>
                <span>{formatNumber(district.high_confidence_shiva)}</span>
                <ChevronRight size={16} />
              </button>
            ))}
          </div>
          {!paged.rows.length && (
            <EmptyState title="No matching districts">
              Try another state or district name.
            </EmptyState>
          )}
          <Pagination {...paged} total={districts.length} onChange={setPage} />
        </section>
      </div>
      <p className="workspace-footnote">
        <Info size={14} />
        Discovery volume reflects the search coverage in this report, not the
        total number of temples in a region.
      </p>
    </>
  );
}

function Reports({
  reports,
  source,
  busy,
  onUpload,
  onLoad,
}: {
  reports: ReportData;
  source: string;
  busy: boolean;
  onUpload: () => void;
  onLoad: (sample: boolean) => void;
}) {
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">YOUR DATA, IN CONTEXT</span>
          <h1>Reports & data</h1>
          <p>Manage the discovery reports behind this workspace.</p>
        </div>
        <button className="button primary" disabled={busy} onClick={onUpload}>
          <Upload size={17} />
          Import CSV reports
        </button>
      </div>
      <section className="dataset-banner">
        <span className="dataset-icon">
          <Database size={25} strokeWidth={1.5} />
        </span>
        <div>
          <span className="eyebrow">CURRENT DATASET</span>
          <h2>{source}</h2>
          <p>
            {formatNumber(reports.candidates.length)} candidate records
            available for browsing
          </p>
        </div>
        <span className="local-badge">Local workspace</span>
      </section>
      <section className="panel report-files">
        <div className="panel-heading">
          <div>
            <h2>Loaded reports</h2>
            <p>Download a snapshot of the current data</p>
          </div>
        </div>
        {(Object.keys(reportNames) as (keyof ReportData)[]).map((key) => {
          const rows =
            key === "national"
              ? reports.national
                ? [reports.national]
                : []
              : reports[key];
          return (
            <div className="report-file" key={key}>
              <span className="file-icon">
                <FileSpreadsheet size={21} />
              </span>
              <div>
                <strong>{reportNames[key]}</strong>
                <span>
                  {rows.length
                    ? `${formatNumber(rows.length)} ${key === "national" ? "summary" : "rows"}`
                    : "Not loaded"}
                </span>
              </div>
              <button
                className="button secondary"
                disabled={!rows.length}
                onClick={() => download(`${key}_report.csv`, rows)}
                aria-label={`Download ${reportNames[key]}`}
              >
                <ArrowDownToLine size={16} />
                <span>Download CSV</span>
              </button>
            </div>
          );
        })}
      </section>
      <div className="report-help-grid">
        <section className="panel">
          <FolderOpen size={23} className="accent-icon" />
          <h2>Bring your own reports</h2>
          <p>
            Import a candidate CSV, or a set of national, state, district and
            candidate reports. Candidate-only imports also generate summary
            counts.
          </p>
          <p>
            Each import replaces the current dataset for this session. Files
            stay in your browser; refreshing reloads the baseline.
          </p>
          <button
            className="button secondary"
            disabled={busy}
            onClick={onUpload}
          >
            <Upload size={16} />
            Choose CSV files
          </button>
          <small>Up to 4 files · 100 MB per file</small>
        </section>
        <section className="panel">
          <Database size={23} className="accent-icon" />
          <h2>Switch datasets</h2>
          <p>
            Return to the district baseline or explore a small sample. Switching
            datasets clears filters and closes candidate details.
          </p>
          <div className="dataset-actions">
            <button
              className="button secondary"
              disabled={busy}
              onClick={() => onLoad(false)}
            >
              Load baseline reports
            </button>
            <button
              className="text-button"
              disabled={busy}
              onClick={() => onLoad(true)}
            >
              Load sample data
              <ArrowRight size={16} />
            </button>
          </div>
        </section>
      </div>
      <DataScopeNote reports={reports} />
    </>
  );
}

let initialLoad: Promise<{ reports: ReportData; sample: boolean }> | undefined;
export default function App() {
  const [view, setView] = useState<View>(getView);
  const [reports, setReports] = useState<ReportData>(emptyReports);
  const [source, setSource] = useState("Loading reports");
  const [busy, setBusy] = useState(true);
  const [notice, setNotice] = useState<{
    message: string;
    error?: boolean;
  } | null>(null);
  const [filters, setFilters] = useState<CandidateFilters>(defaultFilters);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [selected, setSelected] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const matches = useMemo(
    () => filterCandidates(reports.candidates, filters),
    [reports.candidates, filters],
  );
  const overviewCandidates = useMemo(
    () => filterCandidates(reports.candidates, defaultFilters),
    [reports.candidates],
  );
  const detailCandidates = view === "overview" ? overviewCandidates : matches;
  const selectedIndex = detailCandidates.findIndex(
    (candidate) => candidate.google_place_id === selected,
  );
  const selectedCandidate =
    selectedIndex >= 0 ? detailCandidates[selectedIndex] : null;
  useEffect(() => {
    let active = true;
    initialLoad ??= loadRealReports()
      .then((data) => ({ reports: data, sample: false }))
      .catch(() =>
        loadSampleReports().then((data) => ({ reports: data, sample: true })),
      );
    initialLoad
      .then((data) => {
        if (!active) return;
        setReports(data.reports);
        setSource(
          data.sample ? "Sample reports" : "Phase 1.1 district baseline",
        );
        if (data.sample)
          setNotice({
            message: "Baseline reports are unavailable. Sample data is loaded.",
          });
      })
      .catch(() => {
        if (active) {
          setSource("No reports loaded");
          setNotice({
            message:
              "Reports could not be loaded. Open Reports to import CSV files or retry the baseline.",
            error: true,
          });
        }
      })
      .finally(() => {
        if (active) setBusy(false);
      });
    return () => {
      active = false;
    };
  }, []);
  useEffect(() => {
    const update = () => {
      setView(getView());
      setSelected(null);
      window.scrollTo(0, 0);
    };
    window.addEventListener("hashchange", update);
    return () => window.removeEventListener("hashchange", update);
  }, []);
  useEffect(() => {
    const search = (event: KeyboardEvent) => {
      const element = event.target as HTMLElement;
      if (
        event.key === "/" &&
        !event.metaKey &&
        !event.ctrlKey &&
        !event.altKey &&
        !selected &&
        !element.matches("input, select, textarea, [contenteditable=true]")
      ) {
        const input = document.querySelector<HTMLInputElement>(
          'input[aria-label="Search candidates"]',
        );
        if (input) {
          event.preventDefault();
          input.focus();
        }
      }
    };
    window.addEventListener("keydown", search);
    return () => window.removeEventListener("keydown", search);
  }, [selected]);
  function go(next: View) {
    setView(next);
    location.hash = next;
    window.scrollTo(0, 0);
  }
  function browse(next: Partial<CandidateFilters> = {}) {
    setFilters({ ...defaultFilters, ...next });
    setPage(1);
    setSelected(null);
    go("candidates");
  }
  function moveSelection(index: number) {
    setSelected(detailCandidates[index].google_place_id);
    if (view === "candidates") setPage(Math.floor(index / pageSize) + 1);
  }
  function changeFilters(next: Partial<CandidateFilters>) {
    setFilters((current) => ({ ...current, ...next }));
    setPage(1);
    setSelected(null);
  }
  function install(data: ReportData, label: string) {
    setReports(data);
    setSource(label);
    setFilters(defaultFilters);
    setPage(1);
    setSelected(null);
  }
  async function load(sample: boolean) {
    setBusy(true);
    setNotice(null);
    try {
      install(
        await (sample ? loadSampleReports() : loadRealReports()),
        sample ? "Sample reports" : "Phase 1.1 district baseline",
      );
      setNotice({
        message: `${sample ? "Sample data" : "Baseline reports"} loaded.`,
      });
    } catch (error) {
      setNotice({
        message: `Could not load ${sample ? "sample" : "baseline"} reports. The current dataset was kept. ${error instanceof Error ? error.message : "Please try again."}`,
        error: true,
      });
    } finally {
      setBusy(false);
    }
  }
  async function importFiles(files: FileList | null) {
    if (!files?.length) return;
    setBusy(true);
    setNotice(null);
    try {
      const imported = await importReportFiles(Array.from(files));
      install(imported.reports, "Imported reports");
      setNotice({
        message: `Imported ${imported.imported.map((key) => reportNames[key].toLowerCase()).join(", ")}. This dataset is available for the current session.`,
      });
    } catch (error) {
      setNotice({
        message: `Import failed. ${error instanceof Error ? error.message : "Please check the CSV files."} The current dataset was kept.`,
        error: true,
      });
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }
  return (
    <div className="app-layout">
      <a
        className="skip-link"
        href="#main-content"
        onClick={(event) => {
          event.preventDefault();
          document.getElementById("main-content")?.focus();
        }}
      >
        Skip to content
      </a>
      <aside className="sidebar">
        <a
          className="brand"
          href="#overview"
          aria-label="Shiva Temple Discovery — Overview"
        >
          <span className="brand-mark">
            <ShivaMark size={30} />
          </span>
          <span className="brand-copy">
            <strong>Shiva</strong>
            <small>TEMPLE DISCOVERY</small>
          </span>
        </a>
        <span className="sidebar-label">WORKSPACE</span>
        <nav aria-label="Main navigation">
          {navigation.map(({ id, label, icon: Icon }) => (
            <a
              href={`#${id}`}
              key={id}
              className={view === id ? "active" : ""}
              aria-current={view === id ? "page" : undefined}
            >
              <Icon size={18} strokeWidth={1.6} />
              <span>{label}</span>
              {id === "candidates" && (
                <span className="nav-count">
                  {reports.candidates.length >= 1000
                    ? `${(reports.candidates.length / 1000).toFixed(1)}k`
                    : formatNumber(reports.candidates.length)}
                </span>
              )}
            </a>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <span className="phase-label">PHASE 1</span>
          <p>A foundation for discovery.</p>
          <small>
            Candidate data for exploration and independent verification.
          </small>
          <div className="sidebar-source">
            <Database size={15} />
            <span>Google Places source</span>
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            Workspace
            <ChevronRight size={13} />
            <strong>
              {navigation.find((item) => item.id === view)?.label}
            </strong>
          </div>
          <div className="topbar-actions">
            <span
              className={`dataset-status ${source === "Sample reports" ? "sample-status" : ""}`}
            >
              <span />
              {busy ? "Loading reports…" : source}
            </span>
            <button
              className="button secondary import-button"
              disabled={busy}
              onClick={() => inputRef.current?.click()}
            >
              <Upload size={15} />
              <span>Import reports</span>
            </button>
          </div>
        </header>
        <main id="main-content" tabIndex={-1}>
          <input
            type="file"
            ref={inputRef}
            className="file-input"
            aria-label="Import CSV reports"
            accept=".csv,text/csv"
            multiple
            onChange={(event) => importFiles(event.target.files)}
          />
          {notice && (
            <div
              className={`notice ${notice.error ? "notice-error" : ""}`}
              role={notice.error ? "alert" : "status"}
            >
              <Info size={17} />
              <span>{notice.message}</span>
              <button
                className="icon-button"
                aria-label="Dismiss notification"
                onClick={() => setNotice(null)}
              >
                <X size={16} />
              </button>
            </div>
          )}
          {busy ? (
            <div className="loading-state" role="status">
              <span className="loading-spinner" />
              <h1>Preparing your workspace</h1>
              <p>Loading discovery reports and candidate records…</p>
            </div>
          ) : (
            <>
              {view === "overview" && (
                <Overview
                  reports={reports}
                  onBrowse={browse}
                  onSelect={(candidate) =>
                    setSelected(candidate.google_place_id)
                  }
                  onGeography={() => go("geography")}
                />
              )}
              {view === "candidates" && (
                <Candidates
                  reports={reports}
                  filters={filters}
                  onFilters={changeFilters}
                  page={page}
                  onPage={setPage}
                  pageSize={pageSize}
                  onPageSize={setPageSize}
                  onSelect={(candidate) =>
                    setSelected(candidate.google_place_id)
                  }
                  matches={matches}
                />
              )}
              {view === "geography" && (
                <Geography reports={reports} onBrowse={browse} />
              )}
              {view === "reports" && (
                <Reports
                  reports={reports}
                  source={source}
                  busy={busy}
                  onUpload={() => inputRef.current?.click()}
                  onLoad={load}
                />
              )}
            </>
          )}
          <footer className="app-footer">
            <span className="footer-identity">
              Shiva Temple Discovery<span className="footer-dot">·</span>Phase 1
              <span className="version-badge" title="Portal software version, separate from the report dataset">
                v{portalVersion} · Preview
              </span>
            </span>
            <span>Discovery data. Not a verified temple census.</span>
          </footer>
        </main>
      </div>
      <VisitCounter />
      {selectedCandidate && (
        <CandidateDetail
          candidate={selectedCandidate}
          onClose={() => setSelected(null)}
          onPrevious={
            selectedIndex > 0
              ? () => moveSelection(selectedIndex - 1)
              : undefined
          }
          onNext={
            selectedIndex < detailCandidates.length - 1
              ? () => moveSelection(selectedIndex + 1)
              : undefined
          }
        />
      )}
    </div>
  );
}

export { Overview, Candidates, Geography, Reports, CandidateDetail };
