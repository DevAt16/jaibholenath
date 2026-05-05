export type NationalSummary = {
  country: string;
  source: string;
  total_discovered_candidates: number;
  unique_google_place_ids: number;
  high_confidence_shiva: number;
  medium_confidence_shiva_candidates: number;
  low_confidence_possible_temples: number;
  duplicates_removed: number;
  status: string;
};

export type StateCount = {
  state: string;
  unique_google_place_ids: number;
  high_confidence_shiva: number;
  medium_confidence_shiva_candidates: number;
  low_confidence_possible_temples: number;
};

export type DistrictCount = StateCount & {
  district: string;
};

export type Candidate = {
  google_place_id: string;
  google_maps_uri: string;
  discovered_name: string;
  discovered_address: string;
  latitude: number;
  longitude: number;
  state: string;
  district: string;
  source_query: string;
  confidence: "high" | "medium" | "low" | string;
  confidence_score: number;
  classification_reason: string;
  first_seen_at: string;
  last_seen_at: string;
};

export type ReportData = {
  national: NationalSummary | null;
  states: StateCount[];
  districts: DistrictCount[];
  candidates: Candidate[];
};

type CsvRow = Record<string, string>;

function parseCsvLine(line: string): string[] {
  const values: string[] = [];
  let current = "";
  let inQuotes = false;

  for (let index = 0; index < line.length; index += 1) {
    const char = line[index];
    const next = line[index + 1];

    if (char === '"' && inQuotes && next === '"') {
      current += '"';
      index += 1;
      continue;
    }

    if (char === '"') {
      inQuotes = !inQuotes;
      continue;
    }

    if (char === "," && !inQuotes) {
      values.push(current);
      current = "";
      continue;
    }

    current += char;
  }

  values.push(current);
  return values.map((value) => value.trim());
}

export function parseCsv(text: string): CsvRow[] {
  const lines = text
    .replace(/\r\n/g, "\n")
    .replace(/\r/g, "\n")
    .split("\n")
    .filter((line) => line.trim().length > 0);

  if (lines.length < 2) {
    return [];
  }

  const headers = parseCsvLine(lines[0]);
  return lines.slice(1).map((line) => {
    const values = parseCsvLine(line);
    return headers.reduce<CsvRow>((row, header, index) => {
      row[header] = values[index] ?? "";
      return row;
    }, {});
  });
}

function numberValue(row: CsvRow, key: string): number {
  const raw = row[key];
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function toNationalSummary(row: CsvRow): NationalSummary {
  return {
    country: row.country || "India",
    source: row.source || "Google Places API",
    total_discovered_candidates: numberValue(row, "total_discovered_candidates"),
    unique_google_place_ids: numberValue(row, "unique_google_place_ids"),
    high_confidence_shiva: numberValue(row, "high_confidence_shiva"),
    medium_confidence_shiva_candidates: numberValue(
      row,
      "medium_confidence_shiva_candidates",
    ),
    low_confidence_possible_temples: numberValue(row, "low_confidence_possible_temples"),
    duplicates_removed: numberValue(row, "duplicates_removed"),
    status: row.status || "discovery_count_not_final_cultural_count",
  };
}

export function toStateCount(row: CsvRow): StateCount {
  return {
    state: row.state || "Unknown",
    unique_google_place_ids: numberValue(row, "unique_google_place_ids"),
    high_confidence_shiva: numberValue(row, "high_confidence_shiva"),
    medium_confidence_shiva_candidates: numberValue(
      row,
      "medium_confidence_shiva_candidates",
    ),
    low_confidence_possible_temples: numberValue(row, "low_confidence_possible_temples"),
  };
}

export function toDistrictCount(row: CsvRow): DistrictCount {
  return {
    ...toStateCount(row),
    district: row.district || "Unknown",
  };
}

export function toCandidate(row: CsvRow): Candidate {
  return {
    google_place_id: row.google_place_id || "",
    google_maps_uri: row.google_maps_uri || "",
    discovered_name: row.discovered_name || "",
    discovered_address: row.discovered_address || "",
    latitude: numberValue(row, "latitude"),
    longitude: numberValue(row, "longitude"),
    state: row.state || "Unknown",
    district: row.district || "Unknown",
    source_query: row.source_query || "",
    confidence: row.confidence || "low",
    confidence_score: numberValue(row, "confidence_score"),
    classification_reason: row.classification_reason || "",
    first_seen_at: row.first_seen_at || "",
    last_seen_at: row.last_seen_at || "",
  };
}

export async function loadSampleReports(): Promise<ReportData> {
  const [nationalText, stateText, districtText, candidateText] = await Promise.all([
    fetch("/sample-reports/sample_national_summary.csv").then((response) =>
      response.text(),
    ),
    fetch("/sample-reports/sample_state_counts.csv").then((response) => response.text()),
    fetch("/sample-reports/sample_district_counts.csv").then((response) =>
      response.text(),
    ),
    fetch("/sample-reports/sample_candidate_review.csv").then((response) =>
      response.text(),
    ),
  ]);

  return {
    national: parseCsv(nationalText).map(toNationalSummary)[0] ?? null,
    states: parseCsv(stateText).map(toStateCount),
    districts: parseCsv(districtText).map(toDistrictCount),
    candidates: parseCsv(candidateText).map(toCandidate),
  };
}

export function classifyReportFile(fileName: string, rows: CsvRow[]): keyof ReportData | null {
  const name = fileName.toLowerCase();
  const headers = rows[0] ? Object.keys(rows[0]) : [];

  if (
    name.includes("candidate") ||
    (headers.includes("google_place_id") && headers.includes("discovered_name"))
  ) {
    return "candidates";
  }
  if (name.includes("national") || headers.includes("total_discovered_candidates")) {
    return "national";
  }
  if (name.includes("district") || headers.includes("district")) {
    return "districts";
  }
  if (name.includes("state") || headers.includes("state")) {
    return "states";
  }

  return null;
}
