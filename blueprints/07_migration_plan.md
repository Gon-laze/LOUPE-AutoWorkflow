# 07 Migration Plan

## 0. Strategy

Use phased migration to reduce risk:
- phase 1: wrap existing logic as tools
- phase 2: add API and workflow runtime
- phase 3: strengthen scoring and explainability
- phase 4: harden KB governance and iterative quality loop

## 1. Phase Details

### Phase 1: Toolization
- wrap scripts/notebooks as callable modules
- baseline output freeze using golden samples
- schema adapters around existing outputs

Exit:
- outputs are reproducible through wrappers
- no major regression

### Phase 2: Service + Runtime
- implement upload/status/download endpoints
- implement async queue and DAG checkpoints
- persistent job state machine

Exit:
- end-to-end API run succeeds for representative papers

### Phase 3: Scoring + Preference Layer
- implement score policy versioning
- implement user-profile-based weight adaptation
- expose factor-level explanations

Exit:
- score changes are deterministic and interpretable

### Phase 4: KB Governance
- implement versioned KB updates
- quality gates and rollback support
- regular offline evaluation loop

Exit:
- traceable idempotent KB updates
- measurable quality improvement on sample benchmark

## 2. Complexity Summary

| Workstream | Complexity |
|---|---|
| tool wrappers | medium |
| API + queue + state machine | high |
| schema hardening | medium-high |
| scoring policy | medium |
| KB governance | high |

## 3. Suggested Timeline

- week 1-2: phase 1
- week 3-4: phase 2
- week 5: phase 3
- week 6+: phase 4 and calibration
