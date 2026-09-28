const root = document.querySelector('#app');
const escape = value => String(value ?? '').replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));
const labels = { unreviewed: 'Unreviewed', in_review: 'In review', needs_evidence: 'Needs evidence', verified: 'Owner verified', rejected: 'Rejected' };
const badge = status => `<span class="status ${escape(status)}">${escape(labels[status] || status)}</span>`;
const brand = '<div class="brand"><span class="brand-mark" aria-hidden="true">ॐ</span><div><strong>Jai Bholenath</strong><small>RESEARCH WORKSPACE</small></div></div>';
let session, dirty = false, selected, message = '', view = 'dashboard';
let filters = { district: '', status: '', search: '', page: 1 };
async function api(path, body) {
  const response = await fetch(`/api${path}`, { credentials: 'same-origin', ...(body !== undefined ? { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': session?.csrf || '' }, body: JSON.stringify(body) } : {}) });
  const data = await response.json();
  if (!response.ok) { const error = new Error(data.error || 'Request failed.'); error.status = response.status; throw error; }
  return data;
}
function errorAt(target, error) { target.innerHTML = `<div class="error" role="alert">${escape(error.message)}</div>`; }
function shell(content) {
  root.innerHTML = `<div class="shell"><aside class="sidebar">${brand}<button data-nav="dashboard" class="${view === 'dashboard' ? 'active' : ''}">Overview</button><button data-nav="queue" class="${view !== 'dashboard' ? 'active' : ''}">Review queue</button><div class="side-bottom"><div class="owner">Owner account<br>${escape(session.email)}</div><button id="logout">Sign out</button><div>v0.2.0 Preview</div></div></aside><main class="workspace"><div class="topbar"><span>Private research · Madhya Pradesh pilot</span><span class="pill">Local review preview</span></div>${message ? `<div class="success" role="status">${escape(message)}</div>` : ''}<div id="content">${content}</div><footer class="footer">Discovery → evidence → review. Google Places is a discovery source, not a temple census.<br>Reviews remain private. Release publishing and discovery jobs are planned for the next increment.</footer></main></div>`;
  message = '';
  document.querySelectorAll('[data-nav]').forEach(button => button.onclick = () => navigate(button.dataset.nav));
  document.querySelector('#logout').onclick = async () => {
    if (dirty && !confirm('Discard your unsaved changes and sign out?')) return;
    try { await api('/logout', {}); session = null; dirty = false; login(); } catch (error) { alert(error.message); }
  };
}
function login(errorMessage = '') {
  root.innerHTML = `<main class="login"><section class="login-story">${brand}<div><div class="eyebrow">A careful beginning</div><h1>From a discovered place<br>to a trusted record.</h1><p>A private space to examine temple candidates, connect the evidence, and document what we know—and what still needs checking.</p><p>Ujjain · Khandwa · Gwalior</p></div><small>Jai Bholenath · Research workspace · v0.2.0 Preview</small></section><section class="login-panel"><form id="login"><div class="eyebrow">Owner access</div><h2>Welcome back.</h2><p class="muted">Sign in to continue your district pilot.</p><div id="login-error" role="status">${errorMessage ? `<div class="error">${escape(errorMessage)}</div>` : ''}</div><label>Email address<input name="email" type="email" autocomplete="username" required></label><label>Password<input name="password" type="password" autocomplete="current-password" required></label><button class="primary">Sign in to workspace</button><p class="muted section"><small>Access is limited to the owner. Set up or reset your password with the local owner setup command.</small></p></form></section></main>`;
  document.querySelector('#login').onsubmit = async event => {
    event.preventDefault(); const form = event.currentTarget; const button = form.querySelector('button'); button.disabled = true;
    try { session = await api('/login', Object.fromEntries(new FormData(form))); dirty = false; await navigate('dashboard'); }
    catch (error) { errorAt(document.querySelector('#login-error'), error); } finally { button.disabled = false; }
  };
}
async function navigate(next, id) {
  if (dirty && !confirm('Discard unsaved changes? Your last saved revision will be retained.')) return;
  dirty = false; view = next;
  shell('<div class="loading">Loading…</div>');
  try {
    if (next === 'dashboard') await dashboard();
    else if (next === 'queue') await queue();
    else await editor(id);
    window.scrollTo(0, 0);
  } catch (error) {
    if (error.status === 401) { session = null; login('Your session has expired. Please sign in again.'); }
    else errorAt(document.querySelector('#content'), error);
  }
}
async function dashboard() {
  const rows = await api('/dashboard');
  const count = status => rows.filter(row => !status || row.status === status).reduce((sum, row) => sum + Number(row.total), 0);
  document.querySelector('#content').innerHTML = `<div class="page-head"><div><div class="eyebrow">The district pilot</div><h1>Build trust, one record at a time.</h1><p class="muted">Start with the evidence. These are discovery candidates awaiting careful review, not confirmed temple counts.</p></div><button class="primary" id="continue">Open review queue →</button></div><div class="grid"><section class="card"><small>CANDIDATES IN PILOT SNAPSHOT</small><div class="metric">${count().toLocaleString()}</div><small>Attributed to three source districts</small></section><section class="card"><small>REVIEWS WITH A FINAL OUTCOME</small><div class="metric">${count('verified') + count('rejected')} <small>/ 30 first milestone</small></div><small>Verified and rejected outcomes combined</small></section><section class="card"><small>OWNER-VERIFIED IDENTITY & LOCATION</small><div class="metric">${count('verified')}</div><small>Under proposed pilot standard v1</small></section></div><div class="guide section"><span class="step">1</span><div><h2>A small, traceable first chapter</h2><p>Confirm the identity and actual location. Record independently originated sources, explain your decision, and preserve unresolved questions. A high discovery score alone cannot verify a temple.</p></div></div><section class="card section"><h2>Where the pilot stands</h2>${['Ujjain', 'Khandwa', 'Gwalior'].map(district => {
    const group = rows.filter(row => row.district === district); const total = group.reduce((sum, row) => sum + Number(row.total), 0); const pending = group.filter(row => ['unreviewed', 'in_review', 'needs_evidence'].includes(row.status)).reduce((sum, row) => sum + Number(row.total), 0);
    return `<div class="district"><div><strong>${district}</strong><p class="muted"><small>${total} candidates · ${pending} awaiting a final outcome</small></p></div><button data-district="${district}">Review district</button></div>`;
  }).join('')}</section>`;
  document.querySelector('#continue').onclick = () => navigate('queue');
  document.querySelectorAll('[data-district]').forEach(button => button.onclick = () => { filters = { ...filters, district: button.dataset.district, page: 1 }; navigate('queue'); });
}
async function queue() {
  const data = await api(`/candidates?${new URLSearchParams(filters)}`);
  document.querySelector('#content').innerHTML = `<div class="page-head"><div><div class="eyebrow">Research desk</div><h1>Review queue</h1><p class="muted">Discovery confidence is a name signal. Review status records your evidence-based decision.</p></div></div><form id="filters" class="filters"><input name="search" aria-label="Search candidate names" placeholder="Search candidate names…" value="${escape(filters.search)}"><select name="district" aria-label="Source district"><option value="">All pilot districts</option>${['Ujjain', 'Khandwa', 'Gwalior'].map(value => `<option ${filters.district === value ? 'selected' : ''}>${value}</option>`).join('')}</select><select name="status" aria-label="Review status"><option value="">All review states</option>${Object.entries(labels).map(([value, label]) => `<option value="${value}" ${filters.status === value ? 'selected' : ''}>${label}</option>`).join('')}</select><button>Apply filters</button></form><div class="table-wrap"><table><thead><tr><th>Candidate</th><th>Source district</th><th>Discovery confidence</th><th>Human review</th><th><span class="muted">Action</span></th></tr></thead><tbody>${data.rows.map(row => `<tr><td><strong>${escape(row.name)}</strong><br><small>Record ${escape(row.id)} · revision ${row.revision}</small></td><td>${escape(row.source_district)}</td><td>${escape(row.confidence)}</td><td>${badge(row.status)}</td><td><button data-review="${escape(row.id)}" aria-label="Review ${escape(row.name)}">Review →</button></td></tr>`).join('')}</tbody></table>${!data.rows.length ? '<div class="empty">No candidates match these filters. Try another district or review state.</div>' : ''}</div><div class="pagination"><span>${data.total} matching candidates · page ${data.page} of ${Math.max(1, Math.ceil(data.total / 20))}</span><div><button id="previous" ${data.page === 1 ? 'disabled' : ''}>Previous</button> <button id="next" ${data.page * 20 >= data.total ? 'disabled' : ''}>Next</button></div></div>`;
  document.querySelector('#filters').onsubmit = event => { event.preventDefault(); filters = { ...Object.fromEntries(new FormData(event.currentTarget)), page: 1 }; navigate('queue'); };
  document.querySelector('#previous').onclick = () => { filters.page--; navigate('queue'); };
  document.querySelector('#next').onclick = () => { filters.page++; navigate('queue'); };
  document.querySelectorAll('[data-review]').forEach(button => button.onclick = () => navigate('editor', button.dataset.review));
}
const field = (name, label, value = '', area = false, full = false) => `<label class="${full ? 'full' : ''}">${label}${area ? `<textarea name="${name}" maxlength="4000">${escape(value)}</textarea>` : `<input name="${name}" value="${escape(value)}" maxlength="4000">`}</label>`;
function sourceMarkup(source = {}) {
  return `<div class="source"><div class="source-head"><h3>Evidence reference</h3><button type="button" data-remove>Remove source</button></div><div class="form-grid">${field('title', 'Source title', source.title)}${field('origin', 'Originating organisation / observer', source.origin)}${field('reference', 'URL or private reference', source.reference, false, true)}<label>Source type<select name="type">${['other', 'official', 'institutional', 'firsthand'].map(type => `<option value="${type}" ${source.type === type ? 'selected' : ''}>${type}</option>`).join('')}</select></label><label>Access / observation date<input name="accessed" type="date" value="${escape(source.accessed || '')}" max="${new Date().toISOString().slice(0, 10)}"></label>${field('supports', 'What identity / location claims does this support?', source.supports, true, true)}${field('independence', 'Why is this independently originated?', source.independence, true, true)}${field('rights', 'Attribution / permission / reuse restrictions', source.rights || 'Unknown')}<label>Intended visibility<select name="visibility"><option value="private">Private reference</option><option value="public" ${source.visibility === 'public' ? 'selected' : ''}>Public citation (rights still need review)</option></select></label></div></div>`;
}
async function editor(id) {
  selected = await api(`/candidates/${id}`);
  const raw = selected.snapshot;
  const doc = selected.revisions[0]?.document || { name: raw.discovered_name };
  // Search attribution deliberately does not prefill reviewed geography.
  document.querySelector('#content').innerHTML = `<div class="page-head"><div><div class="eyebrow">Record ${escape(id)} · Revision ${selected.revision}</div><h1>${escape(doc.name)}</h1>${badge(selected.status)}</div><button data-back>← Review queue</button></div><div class="editor"><form id="review-form"><section class="card"><h2>Identity & actual location</h2><div class="notice">Confirm geography from evidence. The source district on the right describes the discovery query and may differ from the temple’s actual location.</div><div class="form-grid">${field('name', 'Preferred temple name', doc.name, false, true)}${field('alternateNames', 'Alternate / local names', doc.alternateNames)}${field('shivaAssociation', 'Supported Shiva association', doc.shivaAssociation)}${field('state', 'Actual state', doc.state)}${field('district', 'Actual district', doc.district)}${field('settlement', 'Village / town / locality', doc.settlement)}${field('address', 'Reviewed address', doc.address)}${field('latitude', 'Checked latitude', doc.latitude)}${field('longitude', 'Checked longitude', doc.longitude)}<label class="full">Coordinate precision<select name="precision"><option value="unknown">Not checked</option><option value="approximate" ${doc.precision === 'approximate' ? 'selected' : ''}>Approximate settlement location</option><option value="temple_pin" ${doc.precision === 'temple_pin' ? 'selected' : ''}>Temple pin checked against evidence</option></select></label>${field('locationEvidence', 'How was the actual location checked? Cite your sources.', doc.locationEvidence, true, true)}</div></section><section class="card section"><h2>Evidence, with provenance</h2><p class="muted">For verification, record at least two independent origins, including an official, institutional or documented firsthand source. References remain private in this preview.</p><div id="sources">${(doc.sources || []).map(sourceMarkup).join('')}</div><button type="button" id="add-source">+ Add evidence reference</button></section><section class="card section"><h2>Your review decision</h2><div class="notice">Owner review under <strong>proposed pilot standard v1</strong>. This verifies identity and location only; it does not certify history or imply independent peer review. Possible duplicates should stay “Needs evidence” with the matching record reference for now.</div><div class="form-grid"><label class="checkbox full"><input name="duplicateChecked" type="checkbox" ${doc.duplicateChecked ? 'checked' : ''}>I checked for duplicate records and documented any possible matches in the rationale.</label>${field('limitations', 'Unresolved questions / limitations', doc.limitations, true, true)}${field('rationale', 'Decision rationale and supporting evidence', doc.rationale, true, true)}${field('reopenReason', 'If revising a completed review, explain why', '', true, true)}<label class="full">Outcome<select name="status">${['in_review', 'needs_evidence', 'verified', 'rejected'].map(status => `<option value="${status}" ${doc.status === status ? 'selected' : ''}>${labels[status]}</option>`).join('')}</select></label></div><div id="save-error"></div><div class="actions"><small id="save-state">All changes saved</small><button type="submit" class="primary">Save review revision</button></div></section></form><aside class="card original"><h2>Discovery source</h2><small>Preserved original snapshot</small><dl><dt>Name</dt><dd>${escape(raw.discovered_name)}</dd><dt>Source district / state</dt><dd>${escape(raw.district)}, ${escape(raw.state)}</dd><dt>Address returned</dt><dd>${escape(raw.discovered_address)}</dd><dt>Coordinates returned</dt><dd>${escape(raw.latitude)}, ${escape(raw.longitude)}</dd><dt>Name confidence</dt><dd>${escape(raw.confidence)} · ${escape(raw.confidence_score)}</dd><dt>Classification</dt><dd>${escape(raw.classification_reason)}</dd><dt>Place ID</dt><dd>${escape(raw.google_place_id)}</dd></dl><p><small>Google Places supplied this candidate. Its presence here is not verification.</small></p></aside></div><section class="card section history"><h2>Revision history</h2><p class="muted">Each save preserves the full review, its evidence, author and reason.</p>${selected.revisions.length ? selected.revisions.map(revision => `<details><summary><strong>Revision ${revision.revision}</strong> · ${escape(labels[revision.status])} · ${escape(new Date(revision.created_at).toLocaleString())}<br>${escape(revision.author)} · ${escape(revision.reason)}</summary><pre>${escape(JSON.stringify(revision.document, null, 2))}</pre></details>`).join('') : '<p class="muted">No reviews yet. Your first save begins this record’s audit history.</p>'}</section>`;
  document.querySelector('[data-back]').onclick = () => navigate('queue');
  const form = document.querySelector('#review-form');
  function changed() { dirty = true; document.querySelector('#save-state').textContent = 'Unsaved changes'; }
  form.oninput = changed;
  form.onchange = changed;
  function wireRemove() { document.querySelectorAll('[data-remove]').forEach(button => button.onclick = () => { button.closest('.source').remove(); changed(); }); }
  wireRemove();
  document.querySelector('#add-source').onclick = () => {
    if (document.querySelectorAll('.source').length >= 20) return;
    document.querySelector('#sources').insertAdjacentHTML('beforeend', sourceMarkup()); wireRemove(); changed();
    document.querySelector('#sources .source:last-child input').focus();
  };
  form.onsubmit = async event => {
    event.preventDefault();
    const documentData = {};
    form.querySelectorAll('[name]').forEach(element => { if (!element.closest('.source')) documentData[element.name] = element.type === 'checkbox' ? element.checked : element.value; });
    documentData.sources = [...form.querySelectorAll('.source')].map(source => Object.fromEntries([...source.querySelectorAll('[name]')].map(element => [element.name, element.value])));
    documentData.version = selected.revision;
    if (['verified', 'rejected'].includes(documentData.status) && !confirm(`Save a new revision as “${labels[documentData.status]}”?\n\nRationale: ${documentData.rationale || '(missing)'}\n\nThis records your owner review; it does not publish the record.`)) return;
    const button = form.querySelector('[type="submit"]'); button.disabled = true;
    try { const result = await api(`/candidates/${id}/reviews`, documentData); dirty = false; message = `Revision ${result.revision} saved with evidence and audit history.`; await navigate('editor', id); }
    catch (error) { errorAt(document.querySelector('#save-error'), error); document.querySelector('#save-error').scrollIntoView({ block: 'center' }); }
    finally { button.disabled = false; }
  };
}
window.addEventListener('beforeunload', event => { if (dirty) { event.preventDefault(); event.returnValue = ''; } });
try { session = await api('/session'); await navigate('dashboard'); } catch (error) { login(error.status === 401 ? '' : error.message); }
