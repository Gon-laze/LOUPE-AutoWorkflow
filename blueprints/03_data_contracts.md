# 03 Data Contracts

## 1. Contract Principles

1. Every stage has explicit schema.
2. No silent field dropping.
3. Key claims must be evidence-backed.
4. Stable IDs are required across outputs and stores.
5. Artifact acceptance requires both evidence-grounding and ontology-schema conformance.

## 2. Primary Output Contracts

### Artifact Report
- Schema: `schemas/artifact_report.schema.json`
- Goal: artifact-level extraction, access status, verification, scoring.

### Paper Value Report
- Schema: `schemas/paper_value_report.schema.json`
- Goal: paper-level value with preference adaptation explanation.

### KB Update Record
- Schema: `schemas/kb_update_record.schema.json`
- Goal: track every incremental KB write with versioning and rollback refs.

### DDI Report
- Schema: `schemas/ddi_report.schema.json`
- Goal: standardized Data Debt Index output for paper-level and corpus-level comparison.

### Dashboard Payload
- Schema: `schemas/dashboard_payload.schema.json`
- Goal: front-end ready dashboard cards/charts payload for explainable result delivery.

### Alignment Metrics Snapshot
- Schema: inline object in `09_openapi_draft.yaml` (`JobStatus.alignment_metrics`)
- Goal: expose methodology-alignment gate health (evidence/schema/magic-byte/external-signal coverage).

## 3. Stage Contract Matrix

| Stage | Input | Output |
|---|---|---|
| Parse | uploaded file | raw_text, clean_text, sections |
| Extract | text chunks | artifact candidates + evidence |
| Extract (evidence gate) | candidates + snippets + sections | grounded artifacts + implicit mentions + hallucination flags |
| Extract (schema gate) | grounded artifacts + ontology schema | schema-validated artifacts + violation metrics |
| Verify (link) | normalized artifacts | liveness/access/open status |
| Verify (magic byte) | verification results + artifact types | functional liveness and magic-byte mismatch |
| Verify (external signals) | verified artifacts | external timeline/concept signals + freshness coverage |
| Verify (availability stage) | verification + functional liveness | pointer/liveness/openness stage matrix + availability debt components |
| Score (base) | verified artifacts + profile | artifact base scores + paper base score |
| Score (passive mention) | evidence + sections + base scores | adjusted scores + passive mention flags |
| Report | structured outputs | artifact report + paper report + DDI report + markdown |
| Dashboard | DDI + report summary | dashboard payload JSON |
| KB update | verified facts + hallucination/passive/magic-byte/external-signal outputs | versioned update record |

## 4. Validation Policy

- Runtime schema validation before writing stage output.
- Missing required fields: hard fail + retry route.
- Optional field mismatch: warning + degraded-quality flag.
- Unknown field ratio over threshold: quarantine and alert.

## 5. Provenance Minimum

Each artifact record must carry:
- source paper title/id
- chunk IDs
- evidence snippets
- evidence grounding label (explicit/implicit) with acceptance decision
- verification timestamp and checker source
- magic byte inspection result and detected/expected signature
- availability stage tuple (pointer_exists, liveness_ok, open_access)
- external signal provenance (provider/source/time)
- passive mention classification (active or passive with confidence)
- score formula metadata and version
