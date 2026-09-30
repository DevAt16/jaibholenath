# Admin & Research Workspace — pilot specification

Status: direction and staged implementation specification, 15 September 2026.
Target: v0.2.0 Preview. The first local review slice is implemented in
`admin-workspace/`; its README records delivered scope and local setup.
Release tools, linked duplicate decisions, cultural documentation and discovery
job controls remain planned. Nothing has been deployed to the public site.

## Purpose and first milestone

Give the owner a traceable path from an existing discovery candidate to a
reviewed record and an approved public dataset. Follow the personal direction
anchor's emphasis on trust, provenance, and a small district pilot.

Start with Ujjain, Khandwa, and Gwalior in Madhya Pradesh. Treat these as the
proposed pilot scope; confirm their identifiers against the location table
before filtering. Names alone must not join records from different states.

First acceptance milestone: complete 30 candidate reviews, retain evidence and
reasons for every outcome, and prepare a reproducible pilot release. Report
verified, rejected, duplicate, and unresolved outcomes separately. Thirty
completed reviews must never be described as thirty verified temples.

The longer-term anchor targets 100–200 verified records across three districts.
Do not set a publication deadline that overrides evidence requirements.

## Scope

First delivery includes one owner account, a dashboard, a review queue, a record
editor, an audit history, and release preview/export. Reuse the existing visual
identity and make reviewing comfortable on desktop and tablet. Basic mobile
access must work, but fieldwork/photo collection is a later workflow.

Discovery scripts continue running manually on the owner's computer. Queueing
jobs for a local Python worker is the following delivery, after review and
release controls are usable. No shell command input, automatic nationwide
search, public registration, generic page builder, or outreach automation.

## Verification standard v1 — proposed rules

Publish this methodology before describing pilot records as verified. Store
its version with each decision. These are project review rules, not official
certification or institutional endorsement.

Discovery confidence remains the automated high/medium/low name signal. It must
not change into a verification score or automatically approve a record.

To mark identity/location verified under this standard, require:

1. A supported temple identity and Shiva association, with local/alternate names
   recorded when known.
2. Evidence for its actual state, district, settlement, and location. Search-task
   attribution alone is insufficient. Record how coordinates were checked and
   their precision; an approximate village location is not a verified temple pin.
3. At least two independently originated sources supporting identity and
   location together, including an official/institutional record or documented
   first-hand confirmation. Two sites copying the same listing count as one.
4. A completed duplicate check. Preserve possible matches and the review reason.
5. Reviewer identity, review date, evidence references, decision rationale, and
   any unresolved limitations.

This evidence threshold needs to be tested on the first records. If it proves
unsuitable, revise and version the method; do not silently make exceptions.
Evidence can be in a local language. Absence from an official list is not a
rejection reason by itself.

Verification of identity/location does not verify every cultural claim. History,
age, architecture, conservation condition, and traditions need their own source
links and uncertainty labels. A local oral account can be documented as such;
it must not be rewritten as established historical fact.

### Review states

| State | Meaning and entry requirement |
|---|---|
| Unreviewed | Existing discovery candidate; no human decision yet. |
| In review | Owner has started an editable revision. |
| Needs evidence | Record the missing or conflicting evidence. |
| Verified | All identity/location checks pass under a named methodology version. |
| Rejected | Evidence supports exclusion from this dataset; reason required. |
| Duplicate | Link to the retained record and explain the match. No destructive deletion. |

Disallow self-links and duplicate-link cycles. Reopening a completed review
creates a new revision and requires a reason. Never rewrite an earlier decision.

## Record fields and evidence

Preserve raw discovery candidates and discovery events. A later search must not
overwrite editorial corrections or verification decisions.

| Group | Fields |
|---|---|
| Identity | Stable editorial ID, linked candidate ID/Place ID, preferred name, alternate names and language, Shiva association. |
| Geography | State/district identifiers, settlement, address, coordinates, precision, geographic evidence and discrepancy notes. |
| Review | State, methodology version, reviewer, timestamps, checklist, rationale, duplicate target, limitations. |
| Sources | Title, originating organisation/person category, URL or private evidence reference, source type, access/observation date, independence notes. |
| Cultural documentation | Supported deity/tradition, history, architecture/period, festivals, public managing-body information, accessibility/conservation observations with dates. |
| Rights and visibility | Attribution, licence/permission basis, public/private flag, reuse restrictions, image rights when relevant. |
| History | Revision number, author, changed fields, earlier values, review and publication actions. |

Each evidence association identifies the specific field or claim it supports.
Unknown fields remain unknown. Required verification evidence cannot be replaced
by a high name-confidence score. Sensitive contact details and private reviewer
notes are excluded from exports. Initially store source references and notes;
file/image uploads and their storage pipeline are a separate increment.

Source rights must be reviewed before exporting content. Google Places remains
a discovery source. A linked citation does not itself grant republication rights.
Record permission as unknown when it has not been checked.

## Screens and primary actions

### 1. Dashboard

Show the three pilot districts, review progress, verified identity/location
records, evidence gaps, and latest release status. Use explicit labels such as
“12 verified under standard v1” and “30 reviews completed.”

Primary action: Continue review. Secondary: Open latest release. Show a useful
empty state linking to the candidate queue; do not show fictional activity.

### 2. Review queue

Filter by pilot district, review state, discovery confidence, missing evidence,
and text search. Keep discovery confidence and human review in separate columns.
Show candidate name, source district, reviewed district if different, status,
and last review date. Server-side pagination avoids loading the full dataset.

Primary action: Review record. Bulk verification is excluded from the first
release. Batch selection may later assign work but must not approve evidence.

### 3. Record editor

Display original discovery details alongside the editorial draft. Use tabs or
sections for Identity & location, Evidence, Cultural notes, and History.

Primary action: Save draft. Other actions: Needs evidence, Complete verification,
Reject, and Mark duplicate. Explain unmet checks inline before submission.
Warn before leaving unsaved work. Use revision-based concurrency checks: if
another tab changed the record, show the conflict rather than overwrite it.

Every final decision shows its proposed outcome and rationale before saving.
The owner can initially review and approve their own work; identify this as
owner-reviewed, not independent peer review. Invite-only reviewer roles come later.

### 4. Releases

Choose approved revisions, scope, title, methodology version, and release notes.
Preview counts, additions, edits, exclusions, missing rights, and exact export
content. Show separate candidate coverage and verified pilot coverage.

Release states: Draft → Validated → Approved → Exported → Live.
Only verified, explicitly approved revisions enter the verified pilot export.
Rejected/duplicate records stay in the private audit history; unresolved
candidates may remain in the separately labelled discovery baseline.

An export is not “Live.” Initially the owner downloads the release bundle,
updates the public dataset through GitHub, and lets Hostinger deploy it. Live
status requires checking that the public manifest identifies the release that
was deployed. Failed deployment leaves the previous release live.

Exports contain compatible report CSVs, a manifest with release ID, generation
time, methodology version, counts, and file checksums, and separate pilot
verification/provenance metadata. Update the public reader to display pilot
status explicitly before publishing that metadata. Never imply the whole
national discovery baseline has been verified because a small pilot was reviewed.

Approved releases refer to immutable revisions. Edits create a new draft while
the published revision remains intact. Rollback republishes a previous complete
bundle; it must not delete newer reviews. Application version and dataset release
version are separate.

## Hosting and application boundaries

Proposed admin deployment: admin.jaibholenath.com, with React UI served by a
separate Express admin app and same-origin /api routes. Keep the public Vite
portal and the small visitor API as their own deployments. Confirm available
app slots in the actual Hostinger account before provisioning.

The admin service uses a dedicated MySQL account with scoped discovery reads and
editorial writes. The visitor account retains access only to its two counter
tables. Browsers never receive database credentials or a Google Places API key.

Authenticate and authorise every admin API route on the server. Use an
invite-only/bootstrap owner account, a standard password-hashing implementation,
server-side sessions, Secure/HttpOnly cookies, CSRF protection for mutations,
login throttling, logout/session expiry, and no default credentials. Keep login
secrets, recovery tokens, and private source details out of logs and public files.
Record state-changing actions in an append-only application audit trail.

Initial schema additions should be new migrations, not edits to installed
baseline migrations. Suggested entities: admin_users, admin_sessions,
heritage_records, record_revisions, evidence_sources, revision_evidence,
review_events, dataset_releases, and release_records. Define indexes, foreign
keys, retention and access rules in implementation before applying migrations.

### Following increment: discovery jobs

The admin API stores allowlisted job types and validated parameters. A Python
worker on the owner's computer claims queued jobs, reusing bounded discovery
logic. The UI reports Worker offline until a recent authenticated heartbeat is
available; clicking Run never implies immediate execution while the laptop is off.

Job types: location import, task generation, bounded discovery, classification,
and report export. Add explicit pilot district scoping to the current runner
before exposing it; its current global pending-task limit does not enforce pilot
scope. Preview task/page/request ceilings before any paid API job starts.

Jobs need leases/heartbeats, progress, redacted errors, idempotent retry handling,
and cancellation that stops further requests while retaining completed records.
Do not run long jobs inside a web request or accept arbitrary shell arguments.
A paid request whose result is uncertain must not be silently retried indefinitely.
Move the worker to an always-on Python-capable host only when required.

## Build order and acceptance

1. Authentication and additive schema: unauthenticated requests cannot read or
   mutate private data; owner setup has no shipped password.
2. One complete review path: load a candidate, save corrections and sources,
   validate a decision, reopen it, and inspect the full history.
3. Pilot queue/dashboard: district filtering, pagination, and truthful status
   counts derived from actual review states.
4. Release preview/export plus public metadata reader: all required evidence and
   rights checks pass; files are reproducible and contain no private fields.
5. Publishing rehearsal: deploy a small test release, verify its manifest, and
   restore the preceding bundle without altering the editorial database.
6. Operate the first 30 reviews, refine methodology explicitly, then add jobs.

Tests must cover authentication/CSRF, evidence gates, status transitions,
optimistic concurrency, duplicate cycles, audit writes in the same transaction,
release immutability, exclusion of private data, export count reconciliation,
and failure/rollback. Run database tests on a disposable MySQL server and browser
tests for login, editing, blocked approval, preview and export. No real paid
discovery calls are needed for acceptance testing.

## Decisions to retain for implementation

The source document supplies direction, not proof that any records are verified
or that any institution has endorsed the project. Outreach, funding materials,
and broader heritage expansion stay outside this implementation milestone.

Default to one owner, three proposed pilot districts, the evidence standard
above, and manual deployment of approved exports. Confirm the owner login
identity and actual hosting/database configuration only when provisioning is
needed. Do not request passwords in chat. Existing data must be backed up and
schema changes tested before production migration.
