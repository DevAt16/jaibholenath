import type {
  Candidate,
  DistrictCount,
  ReportData,
  StateCount,
} from "./reportData";
import {
  classifyReportFile,
  parseCsv,
  toCandidate,
  toDistrictCount,
  toNationalSummary,
  toStateCount,
  validateReportRows,
} from "./reportData";

export type CandidateFilters = {
  query: string;
  state: string;
  district: string;
  confidence: string;
  sort: "confidence" | "name" | "recent";
};

export const defaultFilters: CandidateFilters = {
  query: "",
  state: "",
  district: "",
  confidence: "",
  sort: "confidence",
};

export const formatNumber = (value: number) =>
  new Intl.NumberFormat("en-IN").format(value);
export const percent = (value: number, total: number) =>
  total ? Math.round((value / total) * 100) : 0;

export function observedWindow(
  candidates: readonly Pick<Candidate, "first_seen_at" | "last_seen_at">[],
): string {
  let earliest = Infinity;
  let latest = -Infinity;
  // Scan incrementally: spreading large report arrays exceeds JS argument limits.
  for (const candidate of candidates) {
    for (const value of [candidate.first_seen_at, candidate.last_seen_at]) {
      const timestamp = Date.parse(value);
      if (!Number.isFinite(timestamp)) continue;
      earliest = Math.min(earliest, timestamp);
      latest = Math.max(latest, timestamp);
    }
  }
  if (!Number.isFinite(earliest)) return "Not recorded";
  const formatter = new Intl.DateTimeFormat("en-IN", {
    dateStyle: "medium",
    timeZone: "Asia/Kolkata",
  });
  const first = formatter.format(earliest);
  const last = formatter.format(latest);
  return first === last ? first : `${first} – ${last}`;
}

export const districtKey = (record: { state: string; district: string }) =>
  JSON.stringify([record.state, record.district]);

export function discoveryStory(reports: ReportData) {
  // Supplied summaries may describe more records than the loaded candidate extract.
  const derived = !reports.national || !reports.districts.length
    ? summarizeCandidates(reports.candidates)
    : null;
  const districts = [...(reports.districts.length
    ? reports.districts
    : derived!.districts)].sort(
    (a, b) => b.unique_google_place_ids - a.unique_google_place_ids ||
      a.state.localeCompare(b.state) || a.district.localeCompare(b.district),
  );
  const loadedByDistrict = new Map<string, number>();
  for (const candidate of reports.candidates) {
    const key = districtKey(candidate);
    loadedByDistrict.set(key, (loadedByDistrict.get(key) ?? 0) + 1);
  }
  return {
    districts,
    loadedByDistrict,
    summary: reports.national ?? (reports.candidates.length ? derived!.national : null),
  };
}

export function filterCandidates(
  candidates: Candidate[],
  filters: CandidateFilters,
): Candidate[] {
  const words = filters.query
    .trim()
    .toLocaleLowerCase()
    .split(/\s+/)
    .filter(Boolean);
  const ranks: Record<string, number> = { high: 0, medium: 1, low: 2 };
  return candidates
    .filter((candidate) => {
      if (filters.state && candidate.state !== filters.state) return false;
      if (filters.district && candidate.district !== filters.district)
        return false;
      if (filters.confidence && candidate.confidence !== filters.confidence)
        return false;
      const searchable = [
        candidate.discovered_name,
        candidate.discovered_address,
        candidate.state,
        candidate.district,
      ]
        .join(" ")
        .toLocaleLowerCase();
      return words.every((word) => searchable.includes(word));
    })
    .sort((a, b) => {
      if (filters.sort === "name")
        return a.discovered_name.localeCompare(b.discovered_name);
      if (filters.sort === "recent") {
        const timeA = Date.parse(a.last_seen_at) || 0;
        const timeB = Date.parse(b.last_seen_at) || 0;
        if (timeA !== timeB) return timeB - timeA;
      }
      return (
        (ranks[a.confidence] ?? 3) - (ranks[b.confidence] ?? 3) ||
        b.confidence_score - a.confidence_score ||
        a.discovered_name.localeCompare(b.discovered_name) ||
        a.google_place_id.localeCompare(b.google_place_id)
      );
    });
}

export function paginate<T>(rows: T[], requestedPage: number, pageSize = 25) {
  const size = Math.max(1, Math.floor(pageSize) || 25);
  const pages = Math.max(1, Math.ceil(rows.length / size));
  const page = Math.max(1, Math.min(pages, Math.floor(requestedPage) || 1));
  const start = (page - 1) * size;
  return {
    rows: rows.slice(start, start + size),
    page,
    pages,
    start: rows.length ? start + 1 : 0,
    end: Math.min(start + size, rows.length),
  };
}

export function districtOptions(candidates: Candidate[], state: string) {
  return [
    ...new Set(
      candidates
        .filter((candidate) => !state || candidate.state === state)
        .map((candidate) => candidate.district),
    ),
  ].sort();
}

export function summarizeCandidates(candidates: Candidate[]): ReportData {
  // One row per Place ID. CSV imports can contain the same place more than once.
  const unique = [
    ...new Map(
      candidates.map((candidate) => [candidate.google_place_id, candidate]),
    ).values(),
  ];
  const states = new Map<string, StateCount>();
  const districts = new Map<string, DistrictCount>();
  const national = {
    country: "India",
    source: "Google Places API",
    total_discovered_candidates: candidates.length,
    unique_google_place_ids: unique.length,
    high_confidence_shiva: 0,
    medium_confidence_shiva_candidates: 0,
    low_confidence_possible_temples: 0,
    duplicates_removed: candidates.length - unique.length,
    status: "discovery_count_not_final_cultural_count",
  };
  for (const candidate of unique) {
    const field =
      candidate.confidence === "high"
        ? "high_confidence_shiva"
        : candidate.confidence === "medium"
          ? "medium_confidence_shiva_candidates"
          : "low_confidence_possible_temples";
    national[field] += 1;
    const districtKey = JSON.stringify([candidate.state, candidate.district]);
    for (const [map, key] of [
      [states, candidate.state],
      [districts, districtKey],
    ] as const) {
      const count = map.get(key) ?? {
        state: candidate.state,
        district: candidate.district,
        unique_google_place_ids: 0,
        high_confidence_shiva: 0,
        medium_confidence_shiva_candidates: 0,
        low_confidence_possible_temples: 0,
      };
      count.unique_google_place_ids += 1;
      count[field] += 1;
      map.set(key, count as DistrictCount);
    }
  }
  return {
    national,
    states: [...states.values()],
    districts: [...districts.values()],
    candidates: unique,
  };
}

export function mapsUrl(candidate: Candidate): string {
  try {
    const url = new URL(candidate.google_maps_uri);
    if (
      url.protocol === "https:" &&
      !url.username &&
      !url.password &&
      (url.hostname === "maps.google.com" ||
        (["www.google.com", "google.com"].includes(url.hostname) &&
          url.pathname.startsWith("/maps")))
    )
      return url.href;
  } catch {
    /* Use the Place ID when the source URL is missing or invalid. */
  }
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(candidate.discovered_name || "Temple")}&query_place_id=${encodeURIComponent(candidate.google_place_id)}`;
}

export function toCsv(rows: object[]): string {
  if (!rows.length) return "";
  const headers = Object.keys(rows[0]);
  const cell = (value: unknown) => {
    let text = String(value ?? "");
    // Keep user-supplied names and queries as text in spreadsheet applications.
    if (typeof value === "string" && /^[\s]*[=+@-]/.test(text))
      text = `'${text}`;
    return `"${text.replace(/"/g, '""')}"`;
  };
  return [
    headers.map(cell).join(","),
    ...rows.map((row) =>
      headers
        .map((key) => cell((row as Record<string, unknown>)[key]))
        .join(","),
    ),
  ].join("\r\n");
}

/** Build a replacement dataset completely before changing the current workspace. */
export async function importReportFiles(
  files: { name: string; size: number; text: () => Promise<string> }[],
) {
  if (!files.length || files.length > 4)
    throw new Error("Choose one to four report files at a time.");
  const parsed: Partial<ReportData> = {};
  for (const file of files) {
    if (file.size > 100 * 1024 * 1024)
      throw new Error(`${file.name} exceeds the 100 MB limit.`);
    const rows = parseCsv(await file.text());
    const type = classifyReportFile(file.name, rows);
    if (!type) throw new Error(`${file.name} is not a recognized report.`);
    if (type in parsed)
      throw new Error(`Choose only one report of each type (${type}).`);
    validateReportRows(type, rows);
    if (type === "candidates") parsed.candidates = rows.map(toCandidate);
    if (type === "national") parsed.national = toNationalSummary(rows[0]);
    if (type === "states") parsed.states = rows.map(toStateCount);
    if (type === "districts") parsed.districts = rows.map(toDistrictCount);
  }
  const derived = parsed.candidates
    ? summarizeCandidates(parsed.candidates)
    : { national: null, states: [], districts: [], candidates: [] };
  return {
    reports: { ...derived, ...parsed, candidates: derived.candidates },
    imported: Object.keys(parsed) as (keyof ReportData)[],
  };
}
