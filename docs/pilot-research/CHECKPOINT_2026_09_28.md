# Pilot checkpoint — 28 September 2026

Completed the durability and first six-record desk-review increment. This is not
a completed temple-verification pilot or a published dataset.

## Recorded outcome

The configured hosted development workspace contains 52 candidates. Six now
have revision 1, status `needs_evidence`, and one audit event each. The other 46
remain unreviewed. No record was marked owner verified or rejected. All original
discovery snapshots and the existing owner account were preserved.

| Dossier | Workspace record | Remaining evidence gap |
| --- | --- | --- |
| U01 — Anarkeshwar | 26 | Resolve name inconsistency; establish the current exact site pin. |
| U02 — Bilkeshwar | 28 | Resolve village aliases; obtain institutional/firsthand evidence and a checked pin. |
| K01 — Mankameshwar | 20 | Obtain candidate-specific identity/location evidence; exclude namesakes. |
| K02 — Dariyanath | 24 | Move beyond directory corroboration; establish exact site and deity. |
| G01 — Goleshwar | 8 | Establish source independence, pin and identity; resolve possible namesakes. |
| G02 — Sarveshwar | 44 | Obtain direct temple evidence beyond a hotel's nearby-attraction listing. |

These saves explicitly identify AI-assisted desk research performed at the
owner's request. The existing owner account is the audit author; the rationale
states that this is not an owner verification. Reviewed geography, coordinates
and duplicate checks remain unset. Evidence stays private.

The original [six dossiers](SIX_RECORD_DOSSIERS.md) and manifest retain their
16 September research state. The [follow-up log](FOLLOWUP_2026_09_28.json) records
the additional bounded searches, links, access limitations and assessments.
Repeated directories were not promoted to independent verification. There were
no paid Places calls, outreach or field observations.

Selected follow-up evidence:

- U01: the [Amar Ujala article](https://www.amarujala.com/madhya-pradesh/ujjain/anarkeshwar-mahadev-ujjain-gives-freedom-from-hell-just-by-seeing-27th-place-in-84-mahadev-2023-08-05)
  still has inconsistent temple naming. The alternate INTACH inventory link is
  recorded as search-index evidence because direct retrieval timed out.
- U02: [Webdunia](https://hindi.webdunia.com/84-mahadev-ujjain/bilweshwar-mahadev-116021100025_1.html)
  supplies an Ambodia locality lead, not a checked pin.
- G01: [Temples of India](https://templesofindia.org/temple-view/goleshwar-mahadev-gwalior-madhya-pradesh-705rdc)
  repeats Karhiya but lacks detailed temple evidence.

## Durability and validation

The actual workspace uses hosted MariaDB 11.8.9; the old temporary localhost
database is absent. Added MySQL/MariaDB JSON normalization for candidate details
and revision documents. MySQL 8.4 remains the tested project target.

Private backups live in the ignored `admin-workspace/private-backups/` directory:

| Backup | Candidates | Revisions | Audit events |
| --- | --- | --- | --- |
| `pilot-before-2026-09-28.json` | 52 | 0 | 0 |
| `pilot-after-2026-09-28.json` | 52 | 6 | 6 |

Both were restored into disposable local MySQL 8.4 databases and passed full
durable-row checksum comparison. The review batch was first rehearsed on a local
restored copy; a second application skipped all six existing reviews. The hosted
post-save preflight confirmed identical saved documents. Restores exclude
sessions and login throttles. Backups include password hashes and private
evidence: do not commit, publish or share them as research exports.

Integration checks exercise authentication, CSRF, concurrent saves, audit
rollback, backup integrity, refusal of nonempty restore targets, recovery
rollback and Unicode JSON. Python, admin and visitor integration suites run
against disposable databases. Existing frontend tests and its production build
also passed: 39 Python, 10 admin, 6 visitor API and 41 frontend tests (96 total),
with no integration skips. Frontend and visitor API builds passed. Existing
frontend design edits were left as they were.

Off-machine backup retention is still an operational follow-up; provider
retention has not been verified. The backup command does not schedule backups or
upload them to another service.

## Reproduce the review batch

From `admin-workspace`, with its development environment configured:

```sh
npm run research:preview
npm run research:apply
```

The script checks the discovery CSV digest, candidate snapshots, six-record
scope and current revisions. It takes a private backup before saving. Each save
uses the editor's validation, transaction and optimistic-concurrency checks.
A partial failure can be retried: identical revision-1 documents are skipped,
while different existing reviews stop preflight rather than being overwritten.
It never creates verified/rejected outcomes.

## Next checkpoint

Resolve the six evidence gaps where possible, then extend to 30 documented
reviews across the pilot districts. Report needs-evidence, verified and rejected
outcomes separately. Any future town/ULB discovery should remain a bounded,
separate release from the frozen district baseline. The final website remains
outside this work.
