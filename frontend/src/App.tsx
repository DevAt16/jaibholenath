import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties, ReactNode } from "react";
import {
  ChevronDown,
  CircleCheck,
  Copy,
  ExternalLink,
  Map as MapIcon,
  MapPin,
  RotateCcw,
  Search,
  Sparkles,
  Upload,
  X,
} from "lucide-react";
import {
  Candidate,
  DistrictCount,
  NationalSummary,
  ReportData,
  classifyReportFile,
  loadSampleReports,
  parseCsv,
  toCandidate,
  toDistrictCount,
  toNationalSummary,
  toStateCount,
} from "./reportData";

const emptyReports: ReportData = {
  national: null,
  states: [],
  districts: [],
  candidates: [],
};

type ViewMode = "search" | "insights";
type DataSourceStatus = {
  label: string;
  detail: string;
  tone: "sample" | "uploaded" | "empty";
};

const loadingDataSource: DataSourceStatus = {
  label: "Loading reports",
  detail: "Preparing discovery data",
  tone: "empty",
};

const sampleDataSource: DataSourceStatus = {
  label: "Sample reports",
  detail: "CSV demo data loaded",
  tone: "sample",
};

type TempleIconProps = {
  size?: number;
  strokeWidth?: number;
  className?: string;
};

function TempleIcon({
  size = 24,
  strokeWidth = 1.8,
  className,
}: TempleIconProps) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={strokeWidth}
      aria-hidden="true"
    >
      <path d="M4 21h16" />
      <path d="M6.5 21V11.5L12 3l5.5 8.5V21" />
      <path d="M8.5 11.5h7" />
      <path d="M9.5 8.5h5" />
      <path d="M11 5.5h2" />
      <path d="M12 3V1.8" />
      <path d="M9.5 21v-5.2a2.5 2.5 0 0 1 5 0V21" />
      <path d="M7.8 15h1.4" />
      <path d="M14.8 15h1.4" />
    </svg>
  );
}

function TempleMetricIcon({ badge }: { badge?: ReactNode }) {
  return (
    <span className="temple-metric-symbol">
      <TempleIcon size={27} strokeWidth={1.7} />
      {badge ? <span className="temple-metric-badge">{badge}</span> : null}
    </span>
  );
}

function formatNumber(value: number | undefined): string {
  return new Intl.NumberFormat("en-IN").format(value ?? 0);
}

function percent(part: number, total: number): number {
  if (!total) {
    return 0;
  }
  return Math.round((part / total) * 100);
}

function MetricCard({
  label,
  value,
  tone,
  icon,
}: {
  label: string;
  value: number;
  tone: "blue" | "green" | "amber" | "red" | "slate";
  icon: ReactNode;
}) {
  return (
    <section className={`metric metric-${tone}`}>
      <div className="metric-icon">{icon}</div>
      <div>
        <p>{label}</p>
        <strong>{formatNumber(value)}</strong>
      </div>
    </section>
  );
}

function ConfidenceBars({ national }: { national: NationalSummary | null }) {
  const unique = national?.unique_google_place_ids ?? 0;
  const bars = [
    {
      label: "High",
      value: national?.high_confidence_shiva ?? 0,
      color: "var(--green)",
    },
    {
      label: "Medium",
      value: national?.medium_confidence_shiva_candidates ?? 0,
      color: "var(--amber)",
    },
    {
      label: "Low",
      value: national?.low_confidence_possible_temples ?? 0,
      color: "var(--red)",
    },
  ];

  return (
    <section className="panel confidence-panel">
      <div className="panel-heading">
        <div>
          <h2>Confidence Levels</h2>
        </div>
      </div>
      <div className="stacked-bars">
        {bars.map((bar) => (
          <div className="bar-row" key={bar.label}>
            <div className="bar-label">
              <span>{bar.label}</span>
              <span>{percent(bar.value, unique)}%</span>
            </div>
            <div className="bar-track">
              <div
                className="bar-fill"
                style={{
                  width: `${Math.max(percent(bar.value, unique), bar.value ? 4 : 0)}%`,
                  backgroundColor: bar.color,
                }}
              >
                <span>{formatNumber(bar.value)}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function StateBars({ states }: { states: ReportData["states"] }) {
  const sorted = [...states]
    .sort((a, b) => b.unique_google_place_ids - a.unique_google_place_ids)
    .slice(0, 10);
  const max = sorted[0]?.unique_google_place_ids ?? 0;

  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>States</h2>
          <p>Top {sorted.length || 0} by unique candidates</p>
        </div>
        <MapIcon size={20} />
      </div>
      <div className="state-bars">
        {sorted.length ? (
          sorted.map((state) => (
            <div className="state-row" key={state.state}>
              <span>{state.state}</span>
              <div className="state-track">
                <div
                  className="state-fill"
                  style={{
                    width: `${Math.max(percent(state.unique_google_place_ids, max), 3)}%`,
                  }}
                />
              </div>
              <strong>{formatNumber(state.unique_google_place_ids)}</strong>
            </div>
          ))
        ) : (
          <p className="empty-panel">No state report loaded yet.</p>
        )}
      </div>
    </section>
  );
}

function DistrictTable({
  districts,
  selectedState,
  onStateChange,
}: {
  districts: DistrictCount[];
  selectedState: string;
  onStateChange: (state: string) => void;
}) {
  const states = useMemo(
    () => Array.from(new Set(districts.map((district) => district.state))).sort(),
    [districts],
  );
  const visible = districts
    .filter((district) => selectedState === "All" || district.state === selectedState)
    .sort((a, b) => b.unique_google_place_ids - a.unique_google_place_ids)
    .slice(0, 25);

  return (
    <section className="panel district-panel">
      <div className="panel-heading">
        <div>
          <h2>Districts</h2>
          <p>{formatNumber(visible.length)} rows shown</p>
        </div>
        <select value={selectedState} onChange={(event) => onStateChange(event.target.value)}>
          <option value="All">All states</option>
          {states.map((state) => (
            <option key={state} value={state}>
              {state}
            </option>
          ))}
        </select>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>State</th>
              <th>District</th>
              <th>Unique</th>
              <th>High</th>
              <th>Medium</th>
              <th>Low</th>
            </tr>
          </thead>
          <tbody>
            {visible.length ? (
              visible.map((district) => (
                <tr key={`${district.state}-${district.district}`}>
                  <td>{district.state}</td>
                  <td>{district.district}</td>
                  <td>{formatNumber(district.unique_google_place_ids)}</td>
                  <td>{formatNumber(district.high_confidence_shiva)}</td>
                  <td>{formatNumber(district.medium_confidence_shiva_candidates)}</td>
                  <td>{formatNumber(district.low_confidence_possible_temples)}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={6} className="empty-table-cell">
                  No district report rows match this filter.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function SourcePill({ source }: { source: DataSourceStatus }) {
  return (
    <span className={`source-pill source-pill-${source.tone}`}>
      <strong>{source.label}</strong>
      <span>{source.detail}</span>
    </span>
  );
}

function confidenceRank(confidence: string): number {
  if (confidence === "high") {
    return 1;
  }
  if (confidence === "medium") {
    return 2;
  }
  return 3;
}

function searchCandidates(candidates: Candidate[], query: string): Candidate[] {
  const normalizedQuery = query.trim().toLowerCase();
  if (!normalizedQuery) {
    return [];
  }

  return candidates
    .filter((candidate) =>
      [
        candidate.discovered_name,
        candidate.discovered_address,
        candidate.district,
        candidate.state,
        candidate.source_query,
        candidate.classification_reason,
      ]
        .join(" ")
        .toLowerCase()
        .includes(normalizedQuery),
    )
    .sort((a, b) => {
      const rankDelta = confidenceRank(a.confidence) - confidenceRank(b.confidence);
      if (rankDelta !== 0) {
        return rankDelta;
      }
      return b.confidence_score - a.confidence_score;
    })
    .slice(0, 8);
}

function trendingTerms(candidates: Candidate[]): string[] {
  const counts = new Map<string, number>();
  const add = (value: string) => {
    const clean = value.trim();
    if (!clean || clean === "Unknown") {
      return;
    }
    counts.set(clean, (counts.get(clean) ?? 0) + 1);
  };

  candidates.forEach((candidate) => {
    add(candidate.state);
    add(candidate.district);
  });

  const terms = Array.from(counts.entries())
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .map(([term]) => term)
    .slice(0, 3);

  return terms.length ? terms : ["Tamil Nadu", "Uttarakhand", "Varanasi"];
}

function SearchHome({
  candidates,
  dataSource,
  onShowInsights,
  onLoadFiles,
  onReset,
}: {
  candidates: Candidate[];
  dataSource: DataSourceStatus;
  onShowInsights: () => void;
  onLoadFiles: (files: FileList | null) => void;
  onReset: () => void;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Candidate[]>([]);
  const [searched, setSearched] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const trending = useMemo(() => trendingTerms(candidates), [candidates]);

  function runSearch(nextQuery = query) {
    setQuery(nextQuery);
    setResults(searchCandidates(candidates, nextQuery));
    setSearched(Boolean(nextQuery.trim()));
  }

  function spiritualSearch() {
    const bestCandidate = [...candidates].sort((a, b) => {
      const rankDelta = confidenceRank(a.confidence) - confidenceRank(b.confidence);
      if (rankDelta !== 0) {
        return rankDelta;
      }
      return b.confidence_score - a.confidence_score;
    })[0];

    if (bestCandidate) {
      runSearch(bestCandidate.district || bestCandidate.state || bestCandidate.discovered_name);
    }
  }

  function resetSearch() {
    setQuery("");
    setResults([]);
    setSearched(false);
    onReset();
  }

  return (
    <main className="search-page">
      <nav className="search-nav">
        <div className="portal-brand">
          <TempleIcon size={25} />
          <span>Shiva Temple Discovery</span>
        </div>
        <div className="search-nav-actions">
          <SourcePill source={dataSource} />
          <span className="candidate-data-pill">{formatNumber(candidates.length)} candidates</span>
          <input
            ref={fileInputRef}
            className="file-input"
            type="file"
            accept=".csv,text/csv"
            multiple
            onChange={(event) => onLoadFiles(event.target.files)}
          />
          <button
            type="button"
            className="search-nav-link"
            onClick={() => fileInputRef.current?.click()}
          >
            Load CSV
          </button>
          <button type="button" className="search-nav-link" onClick={onShowInsights}>
            Insights
          </button>
          <button type="button" className="profile-button" aria-label="Reset" onClick={resetSearch}>
            <RotateCcw size={20} />
          </button>
        </div>
      </nav>

      <section className="search-hero">
        <div className="temple-mark" aria-hidden="true">
          <TempleIcon size={168} strokeWidth={0.85} />
        </div>
        <form
          className="temple-search-form"
          onSubmit={(event) => {
            event.preventDefault();
            runSearch();
          }}
        >
          <label className="temple-search-box">
            <Search size={28} />
            <input
              type="search"
              placeholder="Search Shiva Temples"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
          <div className="search-actions">
            <button type="submit" className="search-soft-button">
              Temple Search
            </button>
            <button type="button" className="search-soft-button" onClick={spiritualSearch}>
              <Sparkles size={18} />
              I'm Feeling Spiritual
            </button>
          </div>
        </form>

        <div className="trending-discoveries">
          <strong>Trending Discoveries</strong>
          <div>
            {trending.map((item) => (
              <button
                key={item}
                type="button"
                className="trend-chip"
                onClick={() => runSearch(item)}
              >
                {item}
              </button>
            ))}
          </div>
        </div>

        {!candidates.length && !searched ? (
          <section className="search-empty-state">
            <strong>No candidate data loaded yet</strong>
            <p>Load candidate reports to search discovered temple candidates.</p>
          </section>
        ) : null}

        {searched ? (
          <section className="search-results">
            <div className="search-results-heading">
              <h2>Discovery Results</h2>
              <button type="button" className="search-nav-link" onClick={onShowInsights}>
                Open Insights
              </button>
            </div>
            {results.length ? (
              <div className="result-list">
                {results.map((candidate) => (
                  <article className="result-item" key={candidate.google_place_id}>
                    <div>
                      <h3>{candidate.discovered_name}</h3>
                      <p>
                        {[candidate.district, candidate.state]
                          .filter(Boolean)
                          .join(", ")}
                      </p>
                      <p className="result-meta">
                        Score {candidate.confidence_score.toFixed(2)}
                        {candidate.source_query ? ` · ${candidate.source_query}` : ""}
                      </p>
                    </div>
                    <span className={`confidence-badge confidence-${candidate.confidence}`}>
                      {candidate.confidence}
                    </span>
                    {candidate.google_maps_uri ? (
                      <a
                        className="map-link"
                        href={candidate.google_maps_uri}
                        target="_blank"
                        rel="noreferrer"
                      >
                        <ExternalLink size={14} />
                        Open
                      </a>
                    ) : null}
                  </article>
                ))}
              </div>
            ) : (
              <p className="empty-results">
                No matching candidates found. Try a district, state, temple name, or source query.
              </p>
            )}
          </section>
        ) : null}
      </section>
    </main>
  );
}

function CandidateTable({ candidates }: { candidates: Candidate[] }) {
  const [query, setQuery] = useState("");
  const [confidence, setConfidence] = useState("All");
  const [state, setState] = useState("All");
  const [district, setDistrict] = useState("All");
  const [rowLimit, setRowLimit] = useState("100");
  const [expandedPlaceId, setExpandedPlaceId] = useState<string | null>(null);

  const states = useMemo(
    () => Array.from(new Set(candidates.map((candidate) => candidate.state))).sort(),
    [candidates],
  );
  const districts = useMemo(
    () =>
      Array.from(
        new Set(
          candidates
            .filter((candidate) => state === "All" || candidate.state === state)
            .map((candidate) => candidate.district)
            .filter(Boolean),
        ),
      ).sort(),
    [candidates, state],
  );

  useEffect(() => {
    if (district !== "All" && !districts.includes(district)) {
      setDistrict("All");
    }
  }, [district, districts]);

  const filteredCandidates = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return candidates
      .filter((candidate) => confidence === "All" || candidate.confidence === confidence)
      .filter((candidate) => state === "All" || candidate.state === state)
      .filter((candidate) => district === "All" || candidate.district === district)
      .filter((candidate) => {
        if (!normalizedQuery) {
          return true;
        }
        return [
          candidate.discovered_name,
          candidate.discovered_address,
          candidate.district,
          candidate.state,
          candidate.google_place_id,
          candidate.source_query,
          candidate.classification_reason,
        ]
          .join(" ")
          .toLowerCase()
          .includes(normalizedQuery);
      })
      .sort((a, b) => {
        const rankDelta = confidenceRank(a.confidence) - confidenceRank(b.confidence);
        if (rankDelta !== 0) {
          return rankDelta;
        }
        return b.confidence_score - a.confidence_score;
      });
  }, [candidates, confidence, district, query, state]);
  const visible = useMemo(() => {
    if (rowLimit === "All") {
      return filteredCandidates;
    }
    return filteredCandidates.slice(0, Number(rowLimit));
  }, [filteredCandidates, rowLimit]);
  const activeFilters = [
    query.trim() ? { label: `Search: ${query.trim()}`, clear: () => setQuery("") } : null,
    confidence !== "All" ? { label: `Confidence: ${confidence}`, clear: () => setConfidence("All") } : null,
    state !== "All" ? { label: `State: ${state}`, clear: () => setState("All") } : null,
    district !== "All" ? { label: `District: ${district}`, clear: () => setDistrict("All") } : null,
  ].filter(Boolean) as Array<{ label: string; clear: () => void }>;

  function clearFilters() {
    setQuery("");
    setConfidence("All");
    setState("All");
    setDistrict("All");
  }

  return (
    <section className="panel candidate-panel">
      <div className="candidate-heading">
        <div>
          <h2>Candidates</h2>
        </div>
      </div>
      <div className="candidate-toolbar">
        <label className="search-control">
          <Search size={18} />
          <input
            type="search"
            placeholder="Search candidates"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
        <div className="candidate-controls">
          <select value={confidence} onChange={(event) => setConfidence(event.target.value)}>
            <option value="All">All confidence</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
          <select value={state} onChange={(event) => setState(event.target.value)}>
            <option value="All">All states</option>
            {states.map((stateName) => (
              <option key={stateName} value={stateName}>
                {stateName}
              </option>
            ))}
          </select>
          <select value={district} onChange={(event) => setDistrict(event.target.value)}>
            <option value="All">All districts</option>
            {districts.map((districtName) => (
              <option key={districtName} value={districtName}>
                {districtName}
              </option>
            ))}
          </select>
          <select value={rowLimit} onChange={(event) => setRowLimit(event.target.value)}>
            <option value="50">50 rows</option>
            <option value="100">100 rows</option>
            <option value="250">250 rows</option>
            <option value="500">500 rows</option>
            <option value="All">All rows</option>
          </select>
        </div>
        <span className="candidate-count">
          {formatNumber(visible.length)} of {formatNumber(filteredCandidates.length)} matching rows
        </span>
      </div>
      {activeFilters.length ? (
        <div className="filter-chip-row">
          {activeFilters.map((filter) => (
            <button key={filter.label} type="button" className="filter-chip" onClick={filter.clear}>
              {filter.label}
              <X size={14} />
            </button>
          ))}
          <button type="button" className="clear-filter-button" onClick={clearFilters}>
            Clear all
          </button>
        </div>
      ) : null}
      <div className="table-wrap">
        <table className="candidate-table">
          <thead>
            <tr>
              <th>Details</th>
              <th>Confidence</th>
              <th>Score</th>
              <th>Name</th>
              <th>State</th>
              <th>District</th>
              <th>Maps</th>
              <th>Place ID</th>
            </tr>
          </thead>
          <tbody>
            {visible.length ? (
              visible.map((candidate) => {
                const expanded = expandedPlaceId === candidate.google_place_id;
                return (
                  <Fragment key={candidate.google_place_id}>
                    <tr key={candidate.google_place_id}>
                      <td>
                        <button
                          type="button"
                          className="row-detail-button"
                          aria-label={`Toggle details for ${candidate.discovered_name}`}
                          aria-expanded={expanded}
                          onClick={() =>
                            setExpandedPlaceId(expanded ? null : candidate.google_place_id)
                          }
                        >
                          <ChevronDown size={16} />
                        </button>
                      </td>
                      <td>
                        <span className={`confidence-badge confidence-${candidate.confidence}`}>
                          {candidate.confidence}
                        </span>
                      </td>
                      <td>{candidate.confidence_score.toFixed(2)}</td>
                      <td className="strong-cell">{candidate.discovered_name}</td>
                      <td>{candidate.state}</td>
                      <td>{candidate.district}</td>
                      <td>
                        {candidate.google_maps_uri ? (
                          <a
                            className="map-link"
                            href={candidate.google_maps_uri}
                            target="_blank"
                            rel="noreferrer"
                          >
                            <ExternalLink size={14} />
                            Open
                          </a>
                        ) : (
                          <span className="muted-cell">Missing</span>
                        )}
                      </td>
                      <td className="mono-cell">{candidate.google_place_id}</td>
                    </tr>
                    {expanded ? (
                      <tr className="candidate-detail-row">
                        <td colSpan={8}>
                          <div className="candidate-detail-grid">
                            <div>
                              <span>Address</span>
                              <strong>{candidate.discovered_address || "Unknown"}</strong>
                            </div>
                            <div>
                              <span>Source Query</span>
                              <strong>{candidate.source_query || "Unknown"}</strong>
                            </div>
                            <div>
                              <span>Classification Reason</span>
                              <strong>{candidate.classification_reason || "Unknown"}</strong>
                            </div>
                            <div>
                              <span>Coordinates</span>
                              <strong>
                                {candidate.latitude && candidate.longitude
                                  ? `${candidate.latitude.toFixed(5)}, ${candidate.longitude.toFixed(5)}`
                                  : "Unknown"}
                              </strong>
                            </div>
                            <div>
                              <span>First Seen</span>
                              <strong>{candidate.first_seen_at || "Unknown"}</strong>
                            </div>
                            <div>
                              <span>Last Seen</span>
                              <strong>{candidate.last_seen_at || "Unknown"}</strong>
                            </div>
                          </div>
                        </td>
                      </tr>
                    ) : null}
                  </Fragment>
                );
              })
            ) : (
              <tr>
                <td colSpan={8} className="empty-table-cell">
                  No candidates match the current filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default function App() {
  const [reports, setReports] = useState<ReportData>(emptyReports);
  const [view, setView] = useState<ViewMode>("search");
  const [selectedState, setSelectedState] = useState("All");
  const [notice, setNotice] = useState("");
  const [dataSource, setDataSource] = useState<DataSourceStatus>(loadingDataSource);
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    loadSampleReports()
      .then((sampleReports) => {
        setReports(sampleReports);
        setDataSource(sampleDataSource);
      })
      .catch(() => {
        setNotice("Sample report files could not be loaded.");
        setDataSource({
          label: "No reports loaded",
          detail: "Load CSV reports to begin",
          tone: "empty",
        });
      });
  }, []);

  const national = reports.national;
  const qualityRatio = percent(national?.high_confidence_shiva ?? 0, national?.unique_google_place_ids ?? 0);
  const qualityRingStyle = {
    "--quality-deg": `${Math.min(qualityRatio, 100) * 3.6}deg`,
  } as CSSProperties;

  async function handleFiles(files: FileList | null) {
    if (!files?.length) {
      return;
    }

    const nextReports: ReportData = { ...reports };
    const loaded: string[] = [];

    for (const file of Array.from(files)) {
      const rows = parseCsv(await file.text());
      const reportType = classifyReportFile(file.name, rows);

      if (reportType === "national") {
        nextReports.national = rows.map(toNationalSummary)[0] ?? nextReports.national;
        loaded.push("national");
      }
      if (reportType === "states") {
        nextReports.states = rows.map(toStateCount);
        loaded.push("state");
      }
      if (reportType === "districts") {
        nextReports.districts = rows.map(toDistrictCount);
        loaded.push("district");
      }
      if (reportType === "candidates") {
        nextReports.candidates = rows.map(toCandidate);
        loaded.push("candidate");
      }
    }

    setReports(nextReports);
    setNotice(loaded.length ? `Loaded ${Array.from(new Set(loaded)).join(", ")} reports.` : "No report CSVs recognized.");
    if (loaded.length) {
      setDataSource({
        label: "Uploaded CSV",
        detail: `${Array.from(new Set(loaded)).join(", ")} reports loaded`,
        tone: "uploaded",
      });
    }
  }

  async function loadSamples() {
    setReports(await loadSampleReports());
    setSelectedState("All");
    setDataSource(sampleDataSource);
    setNotice("Sample reports restored.");
  }

  async function resetDashboard() {
    setReports(await loadSampleReports());
    setSelectedState("All");
    setDataSource(sampleDataSource);
    setNotice("");
  }

  if (view === "search") {
    return (
      <SearchHome
        candidates={reports.candidates}
        dataSource={dataSource}
        onShowInsights={() => setView("insights")}
        onLoadFiles={handleFiles}
        onReset={resetDashboard}
      />
    );
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="title-row">
          <h1>Shiva Temple Discovery</h1>
          <span className="phase-pill">Phase 1 Analysis</span>
          <SourcePill source={dataSource} />
        </div>
        <div className="actions">
          <button type="button" className="secondary" onClick={() => setView("search")}>
            <Search size={18} />
            Discovery Search
          </button>
          <input
            ref={inputRef}
            className="file-input"
            type="file"
            accept=".csv,text/csv"
            multiple
            onChange={(event) => handleFiles(event.target.files)}
          />
          <button type="button" onClick={() => inputRef.current?.click()}>
            <Upload size={18} />
            Load CSV
          </button>
          <button type="button" className="secondary" onClick={loadSamples}>
            Sample Reports
          </button>
          <button type="button" className="secondary" onClick={resetDashboard}>
            <RotateCcw size={18} />
            Reset
          </button>
        </div>
      </header>

      {notice ? <div className="notice">{notice}</div> : null}

      <section className="metrics-grid">
        <MetricCard
          label="Discovered"
          value={national?.total_discovered_candidates ?? 0}
          tone="blue"
          icon={<TempleMetricIcon badge={<Search size={12} strokeWidth={2.6} />} />}
        />
        <MetricCard
          label="Unique Places"
          value={national?.unique_google_place_ids ?? 0}
          tone="slate"
          icon={<TempleMetricIcon badge={<MapPin size={12} strokeWidth={2.6} />} />}
        />
        <MetricCard
          label="High Confidence"
          value={national?.high_confidence_shiva ?? 0}
          tone="green"
          icon={<TempleMetricIcon badge={<CircleCheck size={12} strokeWidth={2.6} />} />}
        />
        <MetricCard
          label="Duplicates"
          value={national?.duplicates_removed ?? 0}
          tone="amber"
          icon={<TempleMetricIcon badge={<Copy size={12} strokeWidth={2.6} />} />}
        />
      </section>

      <section className="overview-grid">
        <ConfidenceBars national={national} />
        <section className="panel quality-panel">
          <div className="panel-heading">
            <div>
              <h2>High-Confidence Share</h2>
              <p>Share of unique candidates classified as high confidence</p>
            </div>
          </div>
          <div className="quality-score">
            <div className="quality-ring" style={qualityRingStyle}>
              <div>
                <strong>{qualityRatio}%</strong>
                <span>high-confidence share</span>
              </div>
            </div>
          </div>
          <p className="status-text">{national?.status ?? "No national summary loaded"}</p>
        </section>
      </section>

      <h2 className="section-title">Geographic Analysis & Candidate List</h2>

      <section className="analysis-grid">
        <StateBars states={reports.states} />
        <DistrictTable
          districts={reports.districts}
          selectedState={selectedState}
          onStateChange={setSelectedState}
        />
      </section>

      <CandidateTable candidates={reports.candidates} />
    </main>
  );
}
