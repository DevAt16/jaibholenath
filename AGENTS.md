# AGENTS.md

## Project
Shiva Temple Discovery

## Current Scope
Implement Phase 1 only: automated discovery of likely Shiva temple candidates from Indian location data and Google Places API.

## Rules
- Do not build the final website yet.
- Do not claim exact real-world temple counts.
- Treat Google Places as a discovery source, not the final source of truth.
- Use MySQL for discovery and visitor counts. Keep discovery scripts in Python; use Express/Node.js for the hosted visitor API.
- Use Python scripts.
- Use environment variables for all secrets.
- Keep scripts runnable with safe limits.
- Add tests for all core logic.
- Prefer small, reviewable commits.

## Phase 1 Success
The project should be able to:
1. Import Indian location records.
2. Generate search tasks.
3. Run limited Google Places discovery.
4. Store deduplicated temple candidates.
5. Classify candidates by Shiva confidence.
6. Export count reports.

## Research Collaboration
- Read `docs/RESEARCH_CHARTER.md` when planning research work.
- Act as an active AI research and engineering collaborator, guide, and mentor.
- Contribute ideas, implementation, source analysis, evaluation, and writing within the authorised scope.
- Explain consequential decisions and tradeoffs using concrete project examples; help the owner understand and defend the work.
- Challenge assumptions candidly, distinguish proposals from results, and keep uncertainty explicit.
- Record material research decisions, evidence references, and contributions for continuity.
- Devashish Pawar remains the project owner and accountable human researcher. Document AI assistance; do not count it as independent human review or source evidence.
