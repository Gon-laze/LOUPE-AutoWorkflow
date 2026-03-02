# 08 Agent Playbook

## 1. Purpose

Provide a strict runbook for future coding/ops agents to implement this blueprint consistently.

## 2. Rules

1. Preserve baseline behavior first.
2. Validate all stage outputs by schema.
3. Keep every update traceable by job ID and version.
4. Do not hardcode secrets.

## 3. Mandatory Read Sequence

1. `blueprint_manifest.yaml`
2. `02_workflow_dag.yaml`
3. `09_openapi_draft.yaml`
4. `11_provider_matrix.yaml`
5. `schemas/*.json`
6. `04_scoring_policy.md`
7. `05_knowledge_base_design.md`

## 4. Implementation Units

### Unit A: Tool adapters
- input: existing script/notebook outputs
- output: normalized callable tool interface

### Unit B: Runtime
- input: normalized tools
- output: executable DAG + retries + checkpoints

### Unit C: Report generation
- input: verified and scored artifacts
- output: report JSON and markdown

### Unit D: KB update
- input: normalized verified facts + evidence
- output: persisted updates + `kb_update_record`

### Unit J: Evidence-grounding gate
- input: artifact candidates + verbatim evidence snippets + section context
- output: grounded artifacts + implicit mentions + hallucination flags
- constraint: only grounded artifacts can enter normalization and scoring

### Unit K: Ontology schema gate
- input: grounded artifacts + ontology-derived JSON schema
- output: schema-validated artifacts + violation metrics
- constraint: invalid entities must not silently pass downstream

### Unit M: Ontology-aware prompt engineering
- input: chunks + ontology guidance + prompt template version
- output: extraction prompt package + provider attempt diagnostics
- constraint: extraction should first try prompt-engineered JSON output, then fallback to heuristic extraction

### Unit G: Magic Byte enforcement
- input: reachable links + expected artifact type signatures
- output: functional liveness results + mismatch ratio
- constraint: this unit is mandatory before scoring starts

### Unit L: External signal enrichment + staged availability
- input: verification outputs + normalized artifacts
- output: external value signals + availability stage matrix
- constraint: freshness and availability scoring must consume these outputs

### Unit H: Passive mention scoring
- input: evidence snippets + section context + base scores
- output: passive mention flags + adjusted scores
- constraint: this unit is mandatory before cross-agent review

### Unit I: DDI and dashboard contract emission
- input: final scores and verification traces
- output: `ddi_report_json` + `dashboard_payload_json`

### Unit N: Ops observability snapshot
- input: trace log + prompt diagnostics + alignment metrics + provider usage
- output: `ops_pipeline_snapshot_json` + `prompt_debug_json`
- constraint: must support maintainer UI module board and fast fault localization

### Unit E: Provider adapters
- input: provider matrix and routing rules
- output: unified adapter interface for OpenAI/Zhipu/Claude

### Unit F: OpenAPI contract tests
- input: `09_openapi_draft.yaml`
- output: request/response validation tests + backward compatibility checks

## 5. Validation Checklist

- schema pass rate >= 99% on golden samples
- no missing required output field
- every final score has formula version and factors
- key claims map to evidence snippets
- evidence-grounding and ontology-schema gates are both enforced
- prompt-engineering diagnostics are persisted even when heuristic fallback is used
- ops module board payload is available for each job
- all failures are machine-readable
- provider failover events are logged and traceable
- API responses match OpenAPI schemas

## 6. Failure Triage

1. invalid extraction payload -> schema repair + one retry
2. network instability -> cache fallback + degraded flag
3. KB conflict -> quarantine and manual/agent review
4. repeated job failure -> dead-letter queue + alert
