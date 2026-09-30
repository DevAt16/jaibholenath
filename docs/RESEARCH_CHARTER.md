# JaiBholeNath research charter

Date: 30 September 2026. Version: 0.1.

Project owner and independent developer: Devashish Pawar.

This charter records the project's research direction and a proposed first study.
It is not a completed study, a claim of novelty, or a commitment to a publication
deadline. Implementation remains within [Phase 1](../AGENTS.md).

## Purpose

Develop a reproducible method for discovering, evaluating and documenting likely
Shiva temple candidates in India, while retaining the evidence and uncertainty
behind each decision. The longer-term research theme is computational mapping
of India's Shaiva sacred heritage.

The personal motivation is sustained engagement with Shaiva heritage. The
professional contribution should be demonstrated through working software,
measured results, source criticism and research reports. Personal or devotional
significance can motivate the questions; it does not determine their answers.

## Working collaboration and mentorship

Devashish has asked Codex to participate actively as an AI research and engineering
collaborator, guide and mentor. Both should contribute ideas and substantive work.
Devashish remains the project owner and accountable human researcher. Record
Codex's contribution as AI assistance; it does not constitute an independent
human reviewer or source of evidence.

| Work | Devashish's contribution | Codex's contribution |
| --- | --- | --- |
| Research direction | Bring motivation, domain knowledge and judgement about worthwhile questions | Formulate testable questions, examine assumptions and propose bounded studies |
| Evidence | Review source interpretations and contribute local or firsthand knowledge when available | Find and compare sources, trace their origins and identify unsupported claims |
| Engineering | Discuss design choices, develop understanding and contribute implementation | Implement authorised increments, test core logic, review code and document decisions |
| Analysis and writing | Examine findings and take responsibility for final research claims | Build reproducible analyses, explain results, draft reports and critique conclusions |

Use this working rhythm:

1. Start an increment with one concrete question and a reviewable output. Read
   the latest recorded checkpoint rather than assuming earlier plans are done.
2. Codex should propose a reasoned next step and carry out authorised work within
   Phase 1. Routine reversible work should not depend on repeated confirmation.
3. Explain consequential choices as they arise: the problem, alternatives,
   selected approach and evidence that could change the decision. Pair explanations
   with actual project examples so Devashish can assess and defend the method.
4. Challenge weak assumptions candidly. Invite Devashish's judgement on research
   priorities and ambiguous interpretations; neither participant's assertion is
   a substitute for evidence. Distinguish suggestions from completed results.
5. Close each substantive increment with what was learned, what remains uncertain,
   validation performed and the next bounded step. Record material decisions,
   source references and contributions in project files for continuity.

Mentorship should develop Devashish's ability to design studies, evaluate sources,
understand the software and explain the findings. Offer small paired exercises
when useful, while continuing the implementation and research work already
authorised. The project should advance through both contributions, without making
every task a lesson or assuming Devashish must personally perform all routine work.

## Current foundation and limits

The repository contains Python discovery and audit scripts, MySQL storage,
name-based classification, discovery-event provenance, reports, tests and a
research review workspace. These provide a foundation for applied research.
They do not establish that the discovery pipeline is accurate or complete.

Existing checkpoints record:

- An Uttar Pradesh pilot with 294 result occurrences and 206 distinct Google
  Place IDs. Its [quality audit](pilot-research/PILOT_QUALITY_2026_09_29.md)
  documents nine classification changes after inspecting saved names.
- A [geography audit](pilot-research/GEOGRAPHY_AUDIT_2026_09_29.md) identifying
  eight addresses naming another state and 27 records more than 50 km from
  inferred query-town anchors. These are review signals, not boundary decisions.
- A separate Madhya Pradesh review pilot. The
  [28 September checkpoint](pilot-research/CHECKPOINT_2026_09_28.md) records six
  needs-evidence revisions among 52 workspace candidates, with no verified or
  rejected decisions. The existing target is 30 documented reviews.

These are dated repository records, not a fresh database audit. The two pilots
have different geographies and selection methods; their results must be reported
separately. Distinct Place IDs count listings, not necessarily distinct temples.
The classifier's numeric scores are rule-based signals, not calibrated
probabilities of identity, Shiva association or historical truth.

## First research question

**What evidence gaps and systematic errors arise when bounded Google Places
discovery is used to identify likely Shiva temples, and how can a reproducible
review method make those limits explicit?**

Working report title: *Discovery and evidence gaps in a bounded Shiva-temple
mapping pilot in India*.

The first contribution can be a documented method and an empirical error
analysis. A positive improvement or a novel algorithm is not assumed. Compare
the work with existing heritage inventories and relevant research before
claiming a new scholarly contribution.

## Study design

1. **Record related work.** Maintain a small literature matrix covering heritage
   inventories, multilingual place retrieval, entity resolution, geographic
   attribution and provenance. For each source, record its question, method,
   evaluation, limitations and relevance. Read original publications and record
   what this project adds, tests or reuses.
2. **Freeze the exploratory evidence.** Record code revision, classifier rules,
   location-source versions, query settings, observation dates and input hashes.
   Keep the district baseline and each pilot distinct. The nine corrected Uttar
   Pradesh rows are development examples: they cannot establish independent
   classifier accuracy after the rules were changed using them.
3. **Test review feasibility.** Extend the Madhya Pradesh pilot to its existing
   30-review milestone. Retain the original six cases, including unresolved
   ones. Document selection and do not replace difficult records with easier
   famous temples. Use the versioned evidence standard in the
   [workspace specification](ADMIN_WORKSPACE_SPEC.md). Report any departures or
   later revisions explicitly. This selected pilot evaluates the review process;
   it is not a representative accuracy estimate.
4. **Define a separate evaluation before further tuning.** Choose an affordable
   sample from eligible saved candidates not used to design classifier rules.
   Record the sampling frame, exclusions, seed, strata, sample size rationale,
   review budget and stopping rule before looking at labels. Include high,
   medium and low confidence and the scripts/languages actually available.
   If strata are sampled unequally, report per-stratum results and use the
   recorded sampling weights for any estimate across that frame. Generalisation
   remains limited to that frame, not all temples in India.
5. **Review evidence before comparing predictions.** Where practical, hide the
   automated confidence while reviewing. For each candidate, record temple
   identity, Shiva association and actual geography as separate supported,
   contradicted or unresolved claims. A location gap need not erase supported
   deity evidence. Link every judgement to its evidence, date and rationale.
   Same-name sites and repeated publishers require an explicit identity and
   source-origin check.
6. **Compare methods on the same held-out records.** Start with the frozen
   classifier as the baseline. Evaluate one defined change at a time; preserve
   both outputs. Do not tune on the evaluation labels. If labels influence a
   change, that set becomes development data and a fresh evaluation is needed.
   Repeated listings and known records for the same site must not span the
   development and evaluation sets.

As a solo researcher, distinguish personal repeat-review consistency from
independent agreement. An external second reviewer would strengthen the study;
until one participates, report the single-reviewer limitation. AI can assist
source discovery and drafting, but generated text is not evidence. Record the
tool/model, date and human checks when it affects a research judgement.

## Measurements and interpretation

| Measurement | What to report | Interpretation limit |
| --- | --- | --- |
| Discovery yield | Requests, tasks, pages, result occurrences and distinct Place IDs, by run | No estimate of total real-world temples |
| Listing overlap | IDs repeated across queries and already present in the baseline | Does not resolve different IDs for one physical site |
| Classification | Per-confidence counts of supported, contradicted and unresolved temple/Shiva claims | A changed label alone is not a validated correction |
| Geography | Query attribution, evidence-backed geography, conflicts and unresolved rows | Distance thresholds do not define administrative boundaries |
| Review feasibility | Review time, source availability, missing evidence and all outcome counts | Thirty completed reviews need not produce thirty verified records |
| Physical-site duplication | Documented possible matches and supported merge/separation decisions | A targeted pair audit cannot establish a dataset-wide duplicate rate |

For predicted positives, show supported (P), contradicted (N) and unresolved (U)
counts together. If reporting precision on resolved labels, label it explicitly
as P/(P+N), with its denominator and uncertainty; it excludes U. Also show
P/(P+N+U) and (P+U)/(P+N+U) as worst/best-case sensitivity bounds for the sampled
records, not confidence intervals. Empty denominators are undefined, not zero.
Use the sampling design when calculating aggregate estimates and intervals.

Recall within a labelled candidate frame can be studied later, but national
discovery recall requires an independent reference frame. Search results alone
cannot supply the missing population. Google documents that identical Text
Search requests may return different lists, so reproducing an analysis of a
dated permitted snapshot is distinct from repeating live discovery.
[Source: Text Search documentation](https://developers.google.com/maps/documentation/places/web-service/text-search).

## Evidence and reproducibility

For each study, retain a protocol, code revision, configuration without secrets,
input identifiers/hashes where permitted, decision history, analysis commands,
test results, tables, limitations and a change log. New core logic needs tests
under the repository rules. Python and MySQL remain the discovery stack;
Express/Node.js remains the hosted visitor API stack. New discovery retains the
existing request and billing limits.

Link an observation or claim to its source, the processing/review activity and
the responsible researcher. W3C PROV provides an established vocabulary for
these relationships; a graph database is not necessary to record them now.
[Source: PROV overview](https://www.w3.org/TR/prov-overview/).

Design public research outputs separately from private working material.
Document field-level source rights, attribution and retention rules; release
code, methods and permitted evidence/metadata. Do not assume that API content
can become an openly licensed dataset. Google's Places policies identify Place
IDs as an exception to caching restrictions; other retained fields and exports
need assessment against the applicable terms. The existing storage/export design
has not been certified by this charter.
[Source: Places policies](https://developers.google.com/maps/documentation/places/web-service/policies).

Represent historical claims, institutional records, documented observations and
reported traditions with their own evidence and status. An oral or devotional
account may be valuable heritage documentation without establishing a
construction date or an empirically demonstrated event. Record original names,
language and aliases without forcing uncertain equivalence.

## Roadmap by completed outputs

| Stage | Concrete output | Professional evidence |
| --- | --- | --- |
| Current Phase 1: method | Literature matrix, versioned protocol, 30-review feasibility record and error taxonomy | Data engineering, source criticism and traceable system design |
| Current Phase 1: evaluation | Separate held-out evaluation, meaningful tests and reproducible technical report | Evaluation design, multilingual classification and geographic reasoning |
| Future proposal: entity resolution and retrieval | Evidence-backed site/alias model and labelled matching/retrieval benchmark | Search, ranking and entity resolution |
| Future proposal: heritage representation | Claim provenance and a justified ontology mapped to existing standards | Knowledge modelling and evidence-aware AI systems |
| Future proposal: spatial research and public access | Geographic studies with coverage limits, followed by a public product | GIS analysis and usable research infrastructure |

Only the first two rows guide current implementation. The later rows describe
possible research directions; they do not authorise building the final website,
a full knowledge graph, or new nationwide discovery runs.

For an independent developer, a sustainable working cycle is one bounded
question, one reviewable engineering increment and one documented finding at a
time. Use an activity/evidence log for experiments, research decisions and
unresolved questions. Choose the sample and workload to fit available time;
evidence requirements should not bend to a release date.

## First milestone and positioning

The first research milestone is a technical report supported by the review
pilot, a distinct evaluation if completed, reproducible analysis and an explicit
limitations statement. Publish a report before describing it as peer reviewed.
Journal, conference or workshop submission is a later decision based on related
work, results and fit; acceptance is not promised.

Current positioning: **Independent software developer building JaiBholeNath,
with a research focus on computational Shaiva heritage.**

As completed studies accumulate, **software engineer and independent researcher
in information retrieval and computational cultural heritage** becomes a
positioning supported by those outputs. The project can demonstrate skills
relevant to applied AI, search and data systems; it does not guarantee a role,
seniority level or academic outcome. Each public claim should point to something
implemented, evaluated or documented.
