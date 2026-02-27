# 06 Deployment and Operations

## 1. Target Modes

### Mode A: Personal machine
- API + worker + database + vector store on one host.

### Mode B: Lightweight server
- Same architecture with higher uptime and easier remote access.

## 2. Runtime Stack (MVP)

- API: FastAPI + Uvicorn
- Workflow engine: LangGraph worker
- Queue: Redis (or lightweight local queue for early MVP)
- DB: SQLite (MVP), PostgreSQL (scale-up)
- Vector store: Chroma
- File storage: local directory hierarchy

## 3. Process Topology

1. `api-service`: upload/status/download
2. `worker-service`: async DAG execution
3. `scheduler-service`: retries and maintenance
4. `storage-layer`: files + db + vector

## 4. Security Baseline

- token auth for API
- upload constraints (size/type)
- path traversal defense
- secrets via environment variables
- structured audit logs with trace IDs

## 5. Reliability

- job states: queued/running/succeeded/failed/retrying
- checkpoints after parse/extract/verify/score/report stages
- resume from latest checkpoint
- dead-letter queue for repeated failures

## 6. Monitoring

- throughput metrics
- schema error rate
- extraction confidence trend
- verification success ratio
- worker crash/retry counters

## 7. Expected Throughput

Typical MVP estimate on light hardware:
- single paper: ~1-3 minutes
- 10 papers serial: ~10-30 minutes
- parallel throughput depends on worker count and model/API limits

## 8. Backup

- daily backup for DB + vector metadata + reports
- version snapshots for KB and score policy

## 9. Multi-Provider Runtime Operations

- provider adapters: OpenAI / Zhipu / Claude
- each provider should have:
  - isolated API key env vars
  - independent rate-limit tracking
  - independent circuit-breaker state

Suggested env keys:
- `OPENAI_API_KEY`
- `ZHIPU_API_KEY`
- `ANTHROPIC_API_KEY`

Operational rules:
- trigger failover when provider error/rate-limit threshold is exceeded.
- persist provider usage and failover events per job for audit.

## 10. OpenAPI Contract Operations

- Use `09_openapi_draft.yaml` as source-of-truth for API contract.
- Add contract tests:
  - schema validation for all request/response payloads
  - backward compatibility checks before release
  - negative tests for auth, payload size, and invalid enum values
