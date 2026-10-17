# Separate AI Feature Possibilities

**Project:** SafeIași / Harta pietonului – Iași  
**Date:** 17 October 2026  
**Judging criterion:** AI innovation and relevance — 30%.

This document lists **nine independent feature options** from the conversation and pasted note. Each can be considered separately. Similar descriptions from the two sources appear once.

**Status:** These are proposals. Their innovation/demo ratings and effort estimates are design judgments, not official judging scores or measured results. None of these new features has been implemented or benchmarked.

## Quick comparison

| # | Possibility | Main value | Demo appeal | Relative effort |
|---|---|---|---|---|
| 1 | Proactive location discovery | Proactive discovery | High | Medium |
| 2 | Photo-based inspection | Visual reasoning | Very high | Medium |
| 3 | Intervention / urban redesign assistant | Grounded decision support | Very high | Medium |
| 4 | Video conflict investigation | Behavioral analysis | Very high | High |
| 5 | Next-information planner | Adaptive investigation | High | Medium |
| 6 | Recurring-mechanism exploration | Cross-case understanding | High | Low–medium |
| 7 | Recommendation challenger | Critical reasoning | High | Low–medium |
| 8 | Natural-language map queries | Accessible spatial analysis | High | Low–medium |
| 9 | AI scenario stress tests | Generative design testing | Very high | Medium; high with a simulator |

## 1. Discover locations worth inspecting before they appear in accident reports

Find intersections or crossings that resemble locations with documented safety concerns, including places with no events in the selected dataset.

- **AI approach:** Location-profile embeddings or nearest-neighbor retrieval, with AI explaining the relevant similarities, differences, and missing evidence. Keep a transparent structured-feature baseline for comparison.
- **Standalone demo:** Select a crossing with reported concerns. The system finds another location with a similar multilane, unsignalized configuration and explains why it deserves an inspection.
- **Data needed:** Road/intersection profiles: lanes, signal status, crossing type, school/transit proximity, geometry, and reviewed reference cases.
- **Why it could help the AI criterion:** AI helps discover a new inspection candidate beyond the historical accident map.
- **Relative effort:** Medium.
- **Main limitation:** Present an inspection candidate, not a predicted accident or a proven dangerous location. Similarity is not accident probability. Unknown attributes need an explicit missing-data treatment.
- **How to test it:** Have a reviewer judge the analogies and important differences. Include weak feature overlap and unknown values.

Background: [FHWA systemic safety screening](https://highways.dot.gov/safety/data-analysis-tools/systemic/systemic-approach-safety-using-risk-drive-action) considers roadway characteristics alongside crash history. It does not validate the proposed AI model.

## 2. Analyze street photographs for pedestrian-safety concerns

Upload a photograph and receive an annotated inspection checklist that distinguishes visible observations, plausible concerns, and questions requiring another observation.

- **AI approach:** A vision-language model relates visible scene elements to a specific safety question, identifies supporting image regions, and explains uncertainty.
- **Standalone demo:** The model highlights a vehicle potentially obstructing a crossing approach, explains the visibility concern, and asks for a view from the driver’s approach.
- **Data needed:** A suitable street image with known location/capture context. Uploaded photos are sufficient; Mapillary is a possible source whose access, coverage, and permitted use need checking.
- **Why it could help the AI criterion:** A photograph becomes a concrete, visually inspectable analysis rather than a generic text answer.
- **Relative effort:** Medium.
- **Main limitation:** A daytime photo does not establish nighttime lighting adequacy. Limited perspective cannot establish every dimension, missing object, or infrastructure condition.
- **How to test it:** Annotate what is visible versus unobservable. Measure unsupported findings and incorrect image-region references.

Background: [FHWA crosswalk visibility guidance](https://highways.dot.gov/safety/proven-safety-countermeasures/crosswalk-visibility-enhancements) discusses lighting and obstructions such as parked vehicles. The supplied photograph must support any site-specific finding.

## 3. Generate and compare location-specific interventions

Ask for two or three possible actions at a selected location and compare their prerequisites, evidence, limitations, and available cost information.

- **AI approach:** An LLM retrieves relevant safety guidance and reasons about applicability to the location. Deterministic code checks declared budget arithmetic and hard constraints.
- **Standalone demo:** Ask: ‘What options could we consider here under a scenario budget of 100,000 lei?’ Receive conditional alternatives, missing measurements, and reasons for deferring other actions. Optional schematic overlays illustrate concepts.
- **Data needed:** A location dossier, a small curated action catalog, safety references, and a declared cost basis where available.
- **Why it could help the AI criterion:** The proposals respond to the actual case and constraints, with an inspectable explanation of the alternatives.
- **Relative effort:** Medium.
- **Main limitation:** The repository’s costs and reduction fractions are synthetic. Unknown costs cannot establish budget feasibility. Concept layouts and suggested actions require professional/local-applicability review; do not claim a numerical crash reduction from the project score.
- **How to test it:** Check citations, prerequisites, unknown-cost behavior, and whether the proposal changes appropriately after a relevant fact changes.

Evidence starting point: [FHWA’s countermeasure catalog](https://highways.dot.gov/safety/proven-safety-countermeasures). Review its applicability to the local context.

## 4. Detect and explain potential conflicts in traffic video

Analyze a short traffic clip to flag pedestrian–vehicle interactions that deserve human review, including interactions that did not result in a collision.

- **AI approach:** Object detection, multi-object tracking, and interaction analysis, with explanations linked to the relevant video segment.
- **Standalone demo:** Click a flagged interaction to replay the segment with trajectories and an explanation of why the sequence was selected.
- **Data needed:** Usable traffic footage, reliable timestamps/tracking, and appropriate calibration if quantitative motion or conflict metrics are claimed.
- **Why it could help the AI criterion:** AI identifies a potentially important behavior directly from a sequence of events.
- **Relative effort:** High.
- **Main limitation:** A flagged conflict is not an accident. Reliable speed, time-to-collision, or post-encroachment measures require appropriate validation and calibration. This option has a substantial footage and implementation dependency.
- **How to test it:** Review flagged segments and misses, tracking continuity, timestamp accuracy, and any claimed quantitative measures separately.

Methodological background: [FHWA’s archived SSAM brief](https://www.fhwa.dot.gov/publications/research/safety/08049/). Its simulation-based vehicle-interaction results do not validate a pedestrian-camera implementation.

## 5. Decide what information an investigator should collect next

Prioritize the missing observation that could most change a proposed action, then revise the assessment when the observation arrives.

- **AI approach:** Structured hypothesis generation and decision-sensitive question selection. Use a declared ranking heuristic when calibrated probabilities and observation costs are unavailable.
- **Standalone demo:** Nighttime reports exist, but lighting adequacy is unknown. The system requests a nighttime visibility check. After adequate lighting and pedestrian visibility are reported, it withdraws the unsupported lighting-upgrade proposal.
- **Data needed:** A case, its known/unknown facts, possible action prerequisites, and optional practical constraints on collecting observations.
- **Why it could help the AI criterion:** The AI asks a useful question and visibly changes its position after receiving evidence.
- **Relative effort:** Medium.
- **Main limitation:** Installed lighting is not the same as adequate lighting. Call this information gathering; ‘active learning’ is appropriate only if an actual model-training/label-acquisition loop is implemented.
- **How to test it:** Use cases where a new observation should change the decision and cases where it should not. Check whether the requested information affects an action’s applicability.

## 6. Identify recurring patterns across accident reports

Explore recurring types of reported concern across locations, such as visibility concerns, yielding conflicts, or crossings near transit stops.

- **AI approach:** Semantic embeddings, clustering or retrieval, and interpretable summaries with representative cases, source passages, and exceptions.
- **Standalone demo:** Choose a ‘reported visibility concerns’ group and highlight its supporting cases, their evidence, and the conditions they do not share.
- **Data needed:** Enough reviewed, deduplicated narratives and correctly linked location context. A tiny collection supports a demonstration rather than a reliable discovery claim.
- **Why it could help the AI criterion:** AI reveals relationships across cases that a geographic count alone does not express.
- **Relative effort:** Low–medium.
- **Main limitation:** A cluster is a reported pattern or candidate mechanism, not a proven cause. The four available source articles describe only three unique events, which is insufficient for meaningful mechanism discovery.
- **How to test it:** Compare groups with human annotations; inspect exceptions, duplicate leakage, and unsupported causal language.

## 7. Challenge proposed interventions with an adversarial reviewer

Submit a human- or AI-written proposal and receive specific objections about unsupported assumptions, missing prerequisites, contradictory observations, or overstated benefits.

- **AI approach:** A separate structured review pass evaluates the proposal against evidence and action requirements. An optional bounded revision pass responds to its objections.
- **Standalone demo:** ‘This raised-crossing proposal has not checked bus/emergency-route compatibility or drainage. These prerequisites remain unresolved.’
- **Data needed:** Any proposed action, its supporting evidence, and a catalog or checklist of relevant requirements. It can review manually prepared proposals independently.
- **Why it could help the AI criterion:** The AI challenges a confident-looking proposal and produces a more defensible review.
- **Relative effort:** Low–medium.
- **Main limitation:** Two AI personas or agreeing models do not provide independent validation. The reviewer can also make mistakes; retain human review and deterministic checks.
- **How to test it:** Seed unsupported assumptions and omitted prerequisites. Measure detected and corrected errors, as well as false objections to supported claims.

## 8. Ask complex spatial questions in natural language

Ask an investigation question and see the corresponding map results, validated filters, and editable query conditions.

- **AI approach:** Natural-language-to-query translation over an allowlisted schema. Ordinary code validates and executes the structured query.
- **Standalone demo:** ‘Show crossings near schools with four or more lanes, no confirmed pedestrian signal, and reported nighttime events.’ Display the exact filters and matching locations.
- **Data needed:** Structured location/event data and a defined query schema. No photograph, video, or intervention-generation feature is required.
- **Why it could help the AI criterion:** A complex question changes the map immediately, with the interpreted conditions visible.
- **Relative effort:** Low–medium.
- **Main limitation:** ‘No confirmed signal’ can include unknown status; ‘confirmed absent’ has different semantics. Keep these distinctions explicit. Do not execute arbitrary model-generated SQL/code or silently relax zero-result queries.
- **How to test it:** Compare paraphrases with expected query structures. Include negation, unknown fields, ambiguous requests, and empty results.

## 9. Generate challenging scenarios for a proposed intervention

Ask AI to generate plausible edge cases that an intervention should be checked against, then inspect the remaining concerns.

- **AI approach:** Constrained scenario generation grounded in the location and proposed action. Optional deterministic checks or a simple simulator execute the declared scenario assumptions.
- **Standalone demo:** For a proposed crossing change, generate a bus-obscured view, a slower pedestrian crossing, and simultaneous arrivals. Show how each scenario challenges the proposal.
- **Data needed:** A location description, a proposed action, bounded scenario parameters, and optional geometry/behavior assumptions for simulation.
- **Why it could help the AI criterion:** AI introduces a relevant situation the operator did not explicitly request and exposes an unexamined weakness.
- **Relative effort:** Medium; high with a simulator.
- **Main limitation:** Start with a scenario review table if there is no working simulator. A toy simulation does not establish real-world crash reduction, a validated digital twin, or lives saved.
- **How to test it:** Check relevance, diversity, valid parameters, repeatability, and whether the explanation faithfully reflects any simulation output.

## Shared data notes

The [repository snapshot used in the earlier experiments](https://github.com/andrei-vladjitaru/Ctrl-Alt-Dev-2026/tree/77b0a0908ecf2b6a919a13ef003056f1c815705e/false_data) contains four article texts describing three source-annotated events, seven crossing/intersection features, and a larger 17-event synthetic fixture. Fourteen referenced source articles are absent. These quantities describe that pinned snapshot, not a verified citywide dataset.

Keep synthetic examples labeled synthetic. Unknown values remain unknown. The existing action catalog’s costs and reduction fractions are placeholders. Illustrative web-image links in the pasted note do not establish an Iași location or image provenance.

The [existing extraction report](person2_pipeline_lab/REPORT.md) describes the work already tested. Its 22 safety/HTTP checks do not validate the nine possibilities listed here.
