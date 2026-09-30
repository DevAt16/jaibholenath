import { toCandidate, validateReportRows } from './reportData';
import type { ReportData } from './reportData';

export type ExpansionManifest = {
  schema_version: number;
  snapshot_id: string;
  generated_at: string;
  baseline_candidates: number;
  database_candidates: number;
  overlapping_place_ids: number;
  added_since_baseline: number;
  combined_candidates: number;
  geography_high_priority: number;
};
export type ExpansionData = { manifest: ExpansionManifest; reports: ReportData };

export async function loadExpandedReports(currentId?: string): Promise<ExpansionData | null> {
  const response = await fetch('/local-expansion/latest.json', { cache: 'no-store' });
  if (response.status === 404) return null;
  if (!response.ok) throw new Error('Expanded dataset status is unavailable.');
  const manifest: ExpansionManifest = await response.json();
  const counts = [manifest.baseline_candidates, manifest.database_candidates,
    manifest.overlapping_place_ids, manifest.added_since_baseline,
    manifest.combined_candidates, manifest.geography_high_priority];
  if (manifest.schema_version !== 1 || !/^[a-f0-9]{64}$/.test(manifest.snapshot_id)
    || !Number.isFinite(Date.parse(manifest.generated_at))
    || counts.some(value => !Number.isSafeInteger(value) || value < 0)
    || manifest.combined_candidates !== manifest.baseline_candidates + manifest.added_since_baseline
    || manifest.database_candidates !== manifest.overlapping_place_ids + manifest.added_since_baseline) {
    throw new Error('Invalid expanded dataset manifest.');
  }
  if (manifest.snapshot_id === currentId) return null;
  const snapshotResponse = await fetch(`/local-expansion/snapshots/${manifest.snapshot_id}.json`);
  if (!snapshotResponse.ok) throw new Error('Expanded dataset snapshot is unavailable.');
  const snapshot = await snapshotResponse.json();
  const reports: ReportData = snapshot.reports;
  if (snapshot.schema_version !== 1 || !reports?.national || !Array.isArray(reports.candidates)
    || !Array.isArray(reports.states) || !Array.isArray(reports.districts)) {
    throw new Error('Invalid expanded dataset snapshot.');
  }
  const reportRows: [keyof ReportData, object[]][] = [
    ['national', [reports.national]], ['states', reports.states],
    ['districts', reports.districts], ['candidates', reports.candidates],
  ];
  for (const [type, values] of reportRows) {
    if (values.length) validateReportRows(type as keyof ReportData, values.map((row: object) =>
      Object.fromEntries(Object.entries(row).map(([key, value]) => [key, String(value ?? '')]))));
  }
  if (reports.candidates.length !== manifest.combined_candidates
    || reports.national.unique_google_place_ids !== manifest.combined_candidates
    || new Set(reports.candidates.map(row => row.google_place_id)).size !== reports.candidates.length
    || reports.states.reduce((sum, row) => sum + row.unique_google_place_ids, 0) !== reports.candidates.length
    || reports.districts.reduce((sum, row) => sum + row.unique_google_place_ids, 0) !== reports.candidates.length) {
    throw new Error('Expanded dataset counts do not match its candidate records.');
  }
  reports.candidates = reports.candidates.map(row => {
    const strings = Object.fromEntries(Object.entries(row).map(([key, value]) => [key, String(value ?? '')]));
    for (const [key, limit] of [['latitude', 90], ['longitude', 180]] as const) {
      if (strings[key] && (!Number.isFinite(Number(strings[key])) || Math.abs(Number(strings[key])) > limit)) {
        throw new Error('Expanded dataset contains invalid coordinates.');
      }
    }
    const candidate = toCandidate(strings);
    // The existing UI uses (0, 0) to display "Not recorded". A partial pin
    // must not become a fabricated point at latitude or longitude zero.
    if (!strings.latitude || !strings.longitude) candidate.latitude = candidate.longitude = 0;
    return candidate;
  });
  return { manifest, reports };
}
