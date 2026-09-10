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

export function parseCsv(text: string): CsvRow[] {
  const records: string[][] = [];
  let record: string[] = [];
  let value = "";
  let quoted = false;
  const input = text.replace(/^\uFEFF/, "");
  for (let index = 0; index < input.length; index += 1) {
    const char = input[index];
    if (char === '"') {
      if (quoted && input[index + 1] === '"') {
        value += '"';
        index += 1;
      } else if (quoted || !value.trim()) quoted = !quoted;
      else value += char;
    } else if (char === "," && !quoted) {
      record.push(value.trim());
      value = "";
    } else if ((char === "\n" || char === "\r") && !quoted) {
      record.push(value.trim());
      if (record.some(Boolean)) records.push(record);
      record = [];
      value = "";
      if (char === "\r" && input[index + 1] === "\n") index += 1;
    } else value += char;
  }
  if (quoted) throw new Error("The CSV contains an unclosed quoted field.");
  record.push(value.trim());
  if (record.some(Boolean)) records.push(record);
  if (records.length < 2) return [];
  const [headers, ...rows] = records;
  if (
    new Set(headers).size !== headers.length ||
    headers.some((header) => !header)
  ) {
    throw new Error("CSV column names must be unique and non-empty.");
  }
  return rows.map((values, index) => {
    if (values.length !== headers.length)
      throw new Error(
        `CSV row ${index + 2} has an unexpected number of columns.`,
      );
    return Object.fromEntries(
      headers.map((header, column) => [header, values[column] ?? ""]),
    );
  });
}

export function validateReportRows(
  type: keyof ReportData,
  rows: CsvRow[],
): void {
  const required: Record<keyof ReportData, string[]> = {
    candidates: [
      "google_place_id",
      "discovered_name",
      "state",
      "district",
      "confidence",
      "confidence_score",
    ],
    national: [
      "total_discovered_candidates",
      "unique_google_place_ids",
      "high_confidence_shiva",
      "medium_confidence_shiva_candidates",
      "low_confidence_possible_temples",
      "duplicates_removed",
    ],
    states: [
      "state",
      "unique_google_place_ids",
      "high_confidence_shiva",
      "medium_confidence_shiva_candidates",
      "low_confidence_possible_temples",
    ],
    districts: [
      "state",
      "district",
      "unique_google_place_ids",
      "high_confidence_shiva",
      "medium_confidence_shiva_candidates",
      "low_confidence_possible_temples",
    ],
  };
  if (!rows.length) throw new Error("The report has no data rows.");
  if (type === "national" && rows.length !== 1)
    throw new Error("A national summary must contain one data row.");
  const missing = required[type].filter((key) => !(key in rows[0]));
  if (missing.length)
    throw new Error(`Missing columns: ${missing.join(", ")}.`);
  rows.forEach((row, index) => {
    if (required[type].some((key) => !row[key]?.trim()))
      throw new Error(`Required values are missing on row ${index + 2}.`);
    if (type === "candidates") {
      if (
        !["high", "medium", "low"].includes(row.confidence) ||
        !Number.isFinite(Number(row.confidence_score)) ||
        Number(row.confidence_score) < 0 ||
        Number(row.confidence_score) > 1
      ) {
        throw new Error(`Invalid confidence or score on row ${index + 2}.`);
      }
    } else {
      const numeric = required[type].filter(
        (key) => !["state", "district"].includes(key),
      );
      if (
        numeric.some(
          (key) =>
            !Number.isSafeInteger(Number(row[key])) || Number(row[key]) < 0,
        )
      )
        throw new Error(`Invalid count on row ${index + 2}.`);
    }
  });
}

async function fetchReport(
  path: string,
  type: keyof ReportData,
): Promise<string> {
  const response = await fetch(path);
  if (!response.ok) throw new Error("A report file is unavailable.");
  const text = await response.text();
  validateReportRows(type, parseCsv(text));
  return text;
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
    total_discovered_candidates: numberValue(
      row,
      "total_discovered_candidates",
    ),
    unique_google_place_ids: numberValue(row, "unique_google_place_ids"),
    high_confidence_shiva: numberValue(row, "high_confidence_shiva"),
    medium_confidence_shiva_candidates: numberValue(
      row,
      "medium_confidence_shiva_candidates",
    ),
    low_confidence_possible_temples: numberValue(
      row,
      "low_confidence_possible_temples",
    ),
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
    low_confidence_possible_temples: numberValue(
      row,
      "low_confidence_possible_temples",
    ),
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

async function loadReportSet(
  directory: string,
  prefix = "",
): Promise<ReportData> {
  const [nationalText, stateText, districtText, candidateText] =
    await Promise.all([
      fetchReport(`${directory}/${prefix}national_summary.csv`, "national"),
      fetchReport(`${directory}/${prefix}state_counts.csv`, "states"),
      fetchReport(`${directory}/${prefix}district_counts.csv`, "districts"),
      fetchReport(`${directory}/${prefix}candidate_review.csv`, "candidates"),
    ]);
  return {
    national: parseCsv(nationalText).map(toNationalSummary)[0] ?? null,
    states: parseCsv(stateText).map(toStateCount),
    districts: parseCsv(districtText).map(toDistrictCount),
    candidates: parseCsv(candidateText).map(toCandidate),
  };
}

export function loadSampleReports(): Promise<ReportData> {
  return loadReportSet("/sample-reports", "sample_");
}

export function loadRealReports(): Promise<ReportData> {
  return loadReportSet("/real-reports");
}

export function classifyReportFile(
  fileName: string,
  rows: CsvRow[],
): keyof ReportData | null {
  const name = fileName.toLowerCase();
  const headers = rows[0] ? Object.keys(rows[0]) : [];

  if (
    name.includes("candidate") ||
    (headers.includes("google_place_id") && headers.includes("discovered_name"))
  ) {
    return "candidates";
  }
  if (
    name.includes("national") ||
    headers.includes("total_discovered_candidates")
  ) {
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
