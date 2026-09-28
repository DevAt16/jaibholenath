export const statuses = ['in_review', 'needs_evidence', 'verified', 'rejected'];
export const methodology = 'pilot-v1-proposed';
export class InputError extends Error {
  constructor(message, status = 400) { super(message); this.status = status; }
}
const fields = ['name', 'alternateNames', 'shivaAssociation', 'state', 'district', 'settlement', 'address', 'latitude', 'longitude', 'precision', 'locationEvidence', 'limitations', 'rationale', 'reopenReason'];
export function validateReview(input, previousStatus = 'unreviewed') {
  if (!input || Array.isArray(input) || !Number.isInteger(input.version) || input.version < 0 || !statuses.includes(input.status)) throw new InputError('Invalid review version or outcome.');
  const document = {};
  for (const key of fields) {
    if (typeof input[key] !== 'string' || input[key].length > 4000) throw new InputError(`Invalid ${key}.`);
    document[key] = input[key].trim();
  }
  if (!document.name) throw new InputError('A preferred name is required.');
  if (['verified', 'rejected'].includes(previousStatus) && !document.reopenReason) throw new InputError('Explain why you are revising a completed review.');
  document.duplicateChecked = input.duplicateChecked === true;
  if (!Array.isArray(input.sources) || input.sources.length > 20) throw new InputError('Provide at most 20 evidence references.');
  document.sources = input.sources.map(source => {
    if (!source || typeof source !== 'object') throw new InputError('Invalid evidence reference.');
    const item = {};
    for (const key of ['title', 'origin', 'reference', 'type', 'accessed', 'supports', 'independence', 'rights', 'visibility']) {
      if (typeof source[key] !== 'string' || source[key].length > 2000) throw new InputError(`Invalid source ${key}.`);
      item[key] = source[key].trim();
    }
    if (!item.title || !item.origin || !item.reference || !item.supports) throw new InputError('Each source needs a title, originating organisation, reference and supported claims.');
    if (!['official', 'institutional', 'firsthand', 'other'].includes(item.type) || !['private', 'public'].includes(item.visibility)) throw new InputError('Invalid source type or visibility.');
    const sourceDate = new Date(item.accessed);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(item.accessed) || !Number.isFinite(sourceDate.getTime()) || sourceDate.toISOString().slice(0, 10) !== item.accessed || item.accessed > new Date().toISOString().slice(0, 10)) throw new InputError('Source date must be a valid date up to today.');
    return item;
  });
  for (const [key, limit] of [['latitude', 90], ['longitude', 180]]) {
    if (document[key] && (!Number.isFinite(Number(document[key])) || Math.abs(Number(document[key])) > limit)) throw new InputError(`Invalid ${key}.`);
  }
  if (input.status !== 'in_review' && !document.rationale) throw new InputError('Record the reason for this outcome.');
  if (input.status === 'verified') {
    const missing = ['shivaAssociation', 'state', 'district', 'settlement', 'latitude', 'longitude', 'locationEvidence'].filter(key => !document[key]);
    if (missing.length || document.precision !== 'temple_pin' || !document.duplicateChecked) throw new InputError('Verification requires supported identity, actual geography, a checked temple pin and a completed duplicate check.');
    const origins = new Set(document.sources.map(s => s.origin.toLowerCase()));
    if (origins.size < 2 || document.sources.some(s => !s.independence) || !document.sources.some(s => ['official', 'institutional', 'firsthand'].includes(s.type))) throw new InputError('Verification requires two independently originated sources, including an official, institutional or documented firsthand source, with independence notes.');
  }
  return { ...document, status: input.status, methodology };
}
