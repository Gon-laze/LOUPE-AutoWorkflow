# 12 Optimization Backlog

This backlog lists practical optimization candidates beyond the baseline blueprint.

## A. High-Priority (near-term)

1. Contract testing automation
- generate request/response tests from `09_openapi_draft.yaml`
- block release if compatibility breaks

2. Provider-aware cost guardrail
- per-job token and cost budget caps
- hard-stop + graceful partial output on budget overflow

3. Link verification cache TTL policy
- cache pass/fail results with TTL
- lower repeated network calls and speed up batch jobs

4. Golden-set regression harness
- fixed sample papers for extraction/verification/score regression
- release gate based on quality delta thresholds

## B. Medium-Priority

1. Incremental chunk processing
- deduplicate unchanged chunks by content hash
- skip redundant extraction calls

2. Cross-agent disagreement analytics
- classify disagreement causes (entity ambiguity, link instability, score drift)
- feed findings into rule base and prompts

3. Venue prior auto-calibration
- update venue priors from curated reviewer feedback
- enforce versioned rollouts and rollback

4. Multi-tenant quota controls
- per-user API and compute quotas
- abuse prevention and cost isolation

## C. Long-Term

1. Human-in-the-loop console
- UI for manual overrides on low-confidence records
- save reviewer actions to KB update stream

2. Neo4j migration path
- move from JSON graph snapshots to queryable graph DB
- improve relationship analytics and explainability queries

3. Adaptive prompt compiler
- generate provider-specific prompt variants from one canonical contract
- keep behavior consistent and reduce provider drift

## D. Suggested KPI Set

- quality: schema pass rate, extraction F1 on golden set
- reliability: job success rate, retry rate, failover rate
- latency: p50/p95 per stage
- cost: average cost per paper
- trust: evidence coverage ratio, cross-agent agreement ratio
