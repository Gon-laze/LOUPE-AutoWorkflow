# 04 Scoring Policy

## 1. Objective

Create interpretable and configurable scoring for artifacts and papers, with deterministic output under fixed input/profile.

## 2. Core Dimensions

For each artifact:
- `A`: Availability (0-100)
- `F`: Freshness (0-100)
- `R`: Reproducibility (0-100)
- `V`: Venue prior (0-100)
- `U`: User profile fit (0-100)

Availability is stage-based (paper-method aligned):
- `PointerStage` in {0,1}
- `LivenessStage` in {0,1}
- `OpenStage` in {0,1}

Suggested availability assembly:

`A = 100 * (0.30*PointerStage + 0.40*LivenessStage + 0.30*OpenStage)`

Default artifact score:

`ArtifactScore = 0.35*A + 0.20*F + 0.25*R + 0.10*V + 0.10*U`

Default paper score:

`PaperScore = 0.70*mean(TopKArtifactScores) + 0.30*PaperMethodQuality`

## 2A. Mandatory Methodology Alignment Submodules

1. Magic Byte penalty (mandatory, post-verification)
- if artifact link is reachable but magic-byte check mismatches expected type, mark as functionally dead.
- apply penalty to availability/reproducibility.

2. Passive Mention module (mandatory, post-base-scoring)
- classify artifact mentions into active usage vs passive mention.
- apply penalty when evidence is dominated by passive mentions (e.g., related work only).

Adjusted artifact score:

`ArtifactScoreAdjusted = ArtifactScore * ActiveUsageFactor - MagicBytePenalty`

where:
- `ActiveUsageFactor` in [0,1]
- `MagicBytePenalty` in [0,100] normalized to score scale

## 2B. Evidence-First and Ontology Gate Prerequisites

Before scoring, artifact candidates must pass:
1. Evidence grounding gate
- candidate must have verbatim snippet supporting usage.
- implicit mention can be retained for analysis but excluded from availability numerator.

2. Ontology schema gate
- candidate JSON must satisfy ontology-derived schema.
- invalid entities are repaired once; remaining invalid entities are excluded and logged.

## 3. Suggested Sub-Factor Weights

### Availability
- pointer existence: 30%
- link liveness: 40%
- open/restrict/close status: 30%

### Freshness
- age penalty: 40%
- recent usage ratio: 40%
- trend label: 20%
- external signal fusion (OpenAlex etc.) can backfill missing internal timeline and should be confidence-weighted.

### Reproducibility
- evidence sufficiency: 35%
- metadata completeness: 25%
- method consistency: 20%
- source diversity: 20%

### Venue Prior
Configurable starter prior:
- SIGCOMM: 85
- NSDI: 83
- IMC: 80
- MOBICOM: 79
- default: 70

## 4. User Preference Controls

Expected profile fields:
- `research_vs_production` in [0,1]
- `risk_tolerance` in [0,1]
- `prefer_open_data` in [0,1]
- `prefer_recent_data` in [0,1]

Adjustment behavior:
- production-leaning profile increases availability/reproducibility importance.
- research-leaning profile increases freshness/novelty importance.

## 5. Explainability Rules

Every final score must include:
- score formula version
- effective weights
- top positive factors
- top negative factors
- linked evidence snippets
- evidence-gate acceptance result (explicit/implicit/filtered)
- ontology schema validation result
- passive mention decision and confidence
- magic byte expected vs observed signature when checked
- external-signal usage and confidence when backfilled

## 6. Governance

- Keep a `score_policy_version` in all reports.
- Version bump is mandatory for formula/weight changes.
- Calibrate periodically against sampled human labels.

## 7. DDI Output Binding

- Every job should produce `ddi_report_json`.
- DDI must expose:
  - availability debt
  - freshness debt
  - reproducibility debt
  - passive mention penalty
  - magic byte failure penalty
  - evidence insufficiency penalty
  - ontology mismatch penalty
