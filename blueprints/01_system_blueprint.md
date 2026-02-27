# 01 System Blueprint

## 1. Goal and Boundaries

### Goal
Build a continuous, remotely accessible workflow that:
1. Accepts uploaded papers (PDF and optional attachments).
2. Produces two reports:
   - Artifact report: what artifacts are used, whether they are open/restricted/closed, and how to access them.
   - Paper value report: artifact value + paper-level value with configurable preference weights.
3. Updates reusable knowledge assets after each finished run.

### Boundaries
- This blueprint is design only.
- Existing extraction/evaluation logic should be wrapped first, not rewritten in phase 1.

## 2. Requirement-to-Design Mapping

| Requirement | Design Mapping |
|---|---|
| Continuous run on personal/light server | API service + async worker + persistent queue + local DB/vector store |
| Remote upload and auto reports | Upload endpoint + job DAG + report generation endpoint |
| Artifact + evaluation outputs | Structured extraction + active verification + scoring policy |
| User preference controls | Profile-driven weight adjustments and venue priors |
| Iterative and explainable knowledge updates | Versioned KB updates with provenance and rollback refs |

## 3. Current Capability Mapping (Reusable as Tools)

| Existing module | Current role | Target workflow role |
|---|---|---|
| `Paper_AllDownload_new.ipynb` | conference crawling/download | optional ingestion tool |
| `Paper_AllMetadata_new.ipynb` | metadata normalization | metadata enrichment tool |
| `pdf2String_local_bestFilter.ipynb` | PDF text extraction/cleaning | parsing tool |
| `LLM_API_Call.py` + `pdf_Analysis_new_multiprocessing.py` | LLM extraction | extraction core tool |
| `Dataset_KnowledgeGraph.ipynb` | relation graph generation | graph update tool |
| `DataDebtAnalysis.ipynb` | availability/freshness/reproducibility analysis | verification + scoring feature tool |
| `ground_truth_eval.py` | benchmark evaluation | offline QA and drift check tool |

## 4. Target Layered Architecture

1. Access Layer
- FastAPI endpoints: upload, status, report download, admin.

2. Orchestration Layer
- LangGraph DAG with checkpoints and resumable execution.

3. Tool Layer
- Existing scripts/notebook logic wrapped as callable tools.

4. Intelligence Layer
- LangChain chains/agents for schema extraction, verification coordination, report synthesis.

5. Data Layer
- Object storage for raw/intermediate/final files.
- Relational store (SQLite first, PostgreSQL later).
- Vector store (Chroma) for evidence retrieval.
- Graph store (JSON/NetworkX first, optional Neo4j later).

6. Observability Layer
- Structured logs, traces, error routes, replay support.

## 5. LangChain/LangGraph Mapping

- Chains:
  - `ExtractionChain` for chunk-to-schema extraction.
  - `ReportChain` for structured results to report text.
- Agent:
  - `VerificationAgent` for tool selection and fallback behavior in link and metadata checks.
- Graph:
  - Branch for low-confidence extraction.
  - Branch for network degradation fallback.

## 6. Complexity and Expected Effects

| Module | Complexity | Main risk | Expected effect |
|---|---|---|---|
| API + queue + state machine | High | state consistency | enables remote continuous service |
| Extraction schema hardening | Medium-High | output drift | stable parsing and maintainability |
| Active verification tools | Medium | external link instability | stronger trust and reproducibility |
| Scoring + preference adaptation | Medium | calibration bias | user-aligned decisions |
| KB iterative updates | High | duplicates/drift | cumulative quality gains |

## 7. Acceptance Criteria

1. Every stage has schema-validated I/O.
2. Reports include evidence trace for key claims.
3. KB updates are versioned and rollback-capable.
4. User profile changes deterministically affect scoring.
5. Job status exposes alignment metrics (evidence coverage, schema violations, magic-byte mismatch, external-signal coverage).

## 8. OpenAPI-First Interface Design

- Public API contract is defined in `09_openapi_draft.yaml` (OpenAPI 3.1).
- Core endpoints:
  - job submission (`POST /v1/jobs`)
  - job status (`GET /v1/jobs/{job_id}`)
  - report retrieval (`GET /v1/jobs/{job_id}/reports/{report_type}`)
  - retry (`POST /v1/jobs/{job_id}/retry`)
  - provider discovery (`GET /v1/providers`)
- Contract-first policy:
  - backend implementation must not break published schema without version bump.
  - request/response validation should be enforced at gateway and service layers.

## 9. Multi-Agent + Multi-Provider Architecture

Detailed design is in `10_multi_agent_provider_design.md` and `11_provider_matrix.yaml`.

### Agent roles
- Planner agent: builds run strategy from user profile and provider policy.
- Extraction agent: schema-constrained artifact extraction with evidence binding.
- Verification agent: active link and access checks.
- Reviewer agent: cross-agent consistency review and risk notes.
- Report agent: report synthesis using structured, verified facts.

### Supported providers
- OpenAI
- Zhipu (BigModel)
- Claude (Anthropic)

### Provider abstraction goal
- unify structured output, tool calling, retry semantics, and fallback routing.

## 10. Additional Optimization Directions

1. Cost-control mode
- token and request budget guardrails per job.
- dynamic provider downgrade for non-critical steps.

2. Latency optimization
- chunk-level parallel extraction with deterministic merge.
- aggressive caching for repeated links and metadata sources.

3. Quality control
- cross-agent agreement score gate before final report publish.
- periodic offline evaluation against labeled set.

4. Reliability and security
- provider circuit breaker + failover.
- stricter secret rotation and per-provider quota monitoring.

## 11. Paper-Method Alignment Enhancements (Implemented in Blueprint)

1. Mandatory Magic Byte inspection
- Added as explicit DAG node (`N08A_magic_byte_inspection`) after verification and before scoring.

2. Passive Mention as independent scoring module
- Added as explicit DAG node (`N09A_passive_mention_scoring`) after base scoring.

3. DDI and dashboard contracts
- Added output contracts and API exposure for DDI report and dashboard payload.

4. Evidence-first hard gate
- Added explicit grounding gate before normalization to filter unsupported/hallucinated candidates.

5. Ontology schema conformance gate
- Added explicit schema validator to enforce ontology-derived JSON constraints before downstream scoring.

6. External signal enrichment + staged availability
- Added OpenAlex-style external value signals and explicit pointer/liveness/openness stage modeling before scoring.
