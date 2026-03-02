# 10 Multi-Agent and Multi-Provider Design

## 1. Objective

Support a production-pragmatic multi-agent workflow with provider flexibility across:
- OpenAI
- Zhipu
- Claude (Anthropic)

Goals:
1. Keep output quality stable when one provider fails or degrades.
2. Keep behavior explainable and auditable.
3. Keep routing configurable by user preference and budget.

## 2. Agent Topology

### 2.1 Agents and Responsibilities

1. Planner Agent
- reads `user_profile` + `provider_policy`
- chooses quality mode, cost ceiling, fallback order

2. Extraction Agent
- performs schema-constrained artifact extraction
- outputs evidence snippets and extraction confidence

3. Verification Agent
- checks liveness/accessibility/open-status
- enriches with external signals and cache

4. Scoring Agent
- computes dimension scores and preference-adjusted overall scores

5. Reviewer Agent
- cross-checks extraction/verification/score consistency
- emits agreement score and risk notes

6. Report Agent
- synthesizes final artifact and paper reports
- includes explainability fields and score formula version

## 3. Provider Adapter Abstraction

Use a provider-neutral adapter interface:

- `chat(messages, model, **kwargs) -> text`
- `structured(messages, schema, model, **kwargs) -> json`
- `tool_call(messages, tools, model, **kwargs) -> tool_events`
- `health() -> provider_status`

Adapter implementations:
- `OpenAIAdapter`
- `ZhipuAdapter`
- `ClaudeAdapter`

## 4. Capability and Compatibility

Maintain a capability matrix in `11_provider_matrix.yaml`.

Critical compatibility checks:
- structured output mode availability
- tool calling support
- context window size
- rate-limit and timeout behavior

## 5. Routing Strategy

### 5.1 Routing Inputs
- job quality mode
- user cost ceiling
- provider health
- recent error and latency stats

### 5.2 Suggested Default Routing
- extraction: Claude -> OpenAI -> Zhipu
- verification: OpenAI -> Zhipu -> Claude
- report synthesis: Claude -> OpenAI -> Zhipu
- low-cost mode: Zhipu/OpenAI-mini-first

### 5.3 Failover Rules
- trigger failover when:
  - provider error count >= threshold
  - timeout ratio >= threshold
  - rate-limit saturation is persistent
- persist failover events in job trace.

## 6. Consistency and Quality Controls

1. Cross-agent agreement gate:
- if agreement < threshold, queue for human review.

2. Mandatory verification and scoring guards:
- Evidence-grounding gate is mandatory before normalization/scoring.
- Ontology schema gate is mandatory before verification/scoring.
- Ontology-aware prompt package must be used before LLM extraction call.
- Magic Byte inspection is mandatory for functionally-live classification.
- External signal enrichment + staged availability classification are mandatory inputs to scoring.
- Passive mention scoring is mandatory before final score publication.

3. Deterministic output constraints:
- schema validation after each major agent step.
- stable score policy version bound to final report.

4. Prompt and role normalization:
- keep one canonical prompt contract.
- provider-specific prompt adaptation must be isolated to adapters.

## 7. Security and Compliance

- provider keys isolated by env vars.
- no provider secrets in logs.
- redact PII from trace payloads.
- enforce upload and output retention policy.

## 8. Operational Telemetry

Track per provider and per job:
- token in/out
- latency p50/p95
- error rate
- failover count
- estimated cost

Use telemetry for dynamic routing and monthly calibration.

## 9. Rollout Plan

1. Phase A: single-provider baseline (OpenAI or Zhipu or Claude).
2. Phase B: add failover-capable two-provider mode.
3. Phase C: full multi-agent + three-provider routing + agreement gate.
4. Phase D: continuous quality/cost optimization by telemetry.
