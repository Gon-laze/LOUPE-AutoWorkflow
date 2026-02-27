# 05 Knowledge Base Design

## 1. Objective

Build a self-evolving and explainable knowledge layer that improves future extraction and evaluation quality.

## 2. Knowledge Asset Types

1. Structured registry (KV/relational)
- canonical artifact IDs
- aliases
- status history
- aggregate scores

2. Evidence corpus (vector index)
- snippet embeddings
- chunk-level provenance

3. Relationship graph
- paper -> artifact
- artifact -> venue
- artifact -> method/domain
- artifact -> external source

4. Rule base
- normalization rules
- verification heuristics
- conflict handling rules
- ontology schema fragments and class constraints

## 3. Lightweight Storage Plan

- relational: SQLite (upgrade to PostgreSQL)
- vector: Chroma local persistence
- graph: JSON + NetworkX snapshots (upgrade optional)
- rules: versioned YAML files

## 4. Update Pipeline

1. Validate outputs by schema.
2. Apply evidence-grounding outcomes (explicit/implicit/hallucination flags).
3. Normalize and deduplicate entities.
4. Upsert structured records with idempotency keys.
5. Upsert evidence snippets to vector store.
6. Update graph edges and counters.
7. Merge external value signals (e.g., OpenAlex timelines) with source provenance.
8. Emit `kb_update_record` with version + rollback references.

## 5. Quality Gates

Required before committing KB updates:
- schema validation passed
- minimum evidence coverage passed
- conflict checks passed
- complete update trace present

On gate failure:
- quarantine update batch
- keep raw artifacts for review and replay
- if ontology-coverage gap is high, push records to `ontology_curation_queue` for human-in-the-loop curation.

## 6. Explainability

Every downstream answer/report should expose:
- which KB records were used
- when records were updated
- what evidence supports them
- confidence and limitations
- whether value signals came from internal citations or external enrichment
