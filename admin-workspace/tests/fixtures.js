export function draft() {
  return { version: 0, status: 'in_review', name: 'Pilot temple', alternateNames: '', shivaAssociation: '', state: '', district: '', settlement: '', address: '', latitude: '', longitude: '', precision: 'unknown', locationEvidence: '', limitations: '', rationale: '', reopenReason: '', duplicateChecked: false, sources: [] };
}
export function verified() {
  return { ...draft(), status: 'verified', shivaAssociation: 'Supported Shiva identity', state: 'Madhya Pradesh', district: 'Ujjain', settlement: 'Ujjain', latitude: '23.18', longitude: '75.76', precision: 'temple_pin', locationEvidence: 'Both sources support the checked temple pin.', duplicateChecked: true, rationale: 'Reviewed both independent references.', sources: ['official', 'firsthand'].map((type, i) => ({ title: `Source ${i}`, origin: `Independent origin ${i}`, reference: `private:reference-${i}`, type, accessed: '2026-01-01', supports: 'Identity and location', independence: 'Independent observation rather than copied listing', rights: 'Unknown', visibility: 'private' })) };
}
