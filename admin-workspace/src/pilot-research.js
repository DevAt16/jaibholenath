import { validateReview } from './review.js';

// The manifest is research evidence, never a review API payload. Conversion
// deliberately leaves unverified geography and duplicate checks unset.
export function preparePilotReviews(manifest, followup) {
  if (manifest.schema !== 'pilot-research-drafts-v1' || !Array.isArray(manifest.records) || manifest.records.length !== 6) throw new Error('Expected the six-record pilot manifest.');
  if (followup.schema !== 'pilot-followup-v1' || followup.records.length !== 6) throw new Error('Expected six follow-up assessments.');
  const seen = new Set();
  return manifest.records.map(record => {
    if (seen.has(record.google_place_id) || record.suggested_review_status !== 'needs_evidence') throw new Error('Duplicate candidate or unsupported research outcome.');
    seen.add(record.google_place_id);
    const extra = followup.records.filter(item => item.dossier_id === record.dossier_id);
    if (extra.length !== 1) throw new Error('Missing or duplicate follow-up assessment.');
    const sources = record.source_ids.map(id => {
      const source = manifest.sources[id];
      if (!source) throw new Error('Unknown evidence reference.');
      return {
        title: source.title, origin: source.origin, reference: source.url,
        type: source.kind === 'institutional inventory' ? 'institutional' : 'other',
        accessed: source.accessed, supports: `${source.finding}\nAccess recorded in the original dossier: ${source.access}`,
        independence: `Not established for final verification. ${source.limits}`,
        rights: source.reuse_rights, visibility: 'private',
      };
    });
    for (const reference of extra[0].references) sources.push({
      title: `${reference.origin}: follow-up reference for ${record.dossier_id}`,
      origin: reference.origin, reference: reference.url, type: reference.origin === 'INTACH' ? 'institutional' : 'other',
      accessed: followup.reviewed_on, supports: `${reference.access}. ${extra[0].assessment}`,
      independence: 'Not established. Repeated origins are not additional independent sources.',
      rights: 'Unknown; citation and original summary only.', visibility: 'private',
    });
    const input = {
      version: 0, status: 'needs_evidence', name: record.discovery_snapshot.discovered_name,
      alternateNames: '', shivaAssociation: '', state: '', district: '', settlement: '', address: '',
      latitude: '', longitude: '', precision: 'unknown', locationEvidence: '', duplicateChecked: false,
      limitations: [record.editorial_note, ...record.next_checks, record.nearby_candidate_screen.limitation, extra[0].assessment].join('\n'),
      rationale: `AI-assisted desk review ${followup.reviewed_on} (${record.dossier_id}), recorded at the owner's request; not an owner verification. ${record.assessment} Exact temple pin, independently supported geography and duplicate review remain unresolved. Follow-up: ${extra[0].assessment}`,
      reopenReason: '', sources,
    };
    return { dossierId: record.dossier_id, placeId: record.google_place_id, snapshot: record.discovery_snapshot, input, document: validateReview(input) };
  });
}
