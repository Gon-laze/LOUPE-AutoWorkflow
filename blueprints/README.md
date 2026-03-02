# AutoWorkFlow Blueprints

This folder stores a design-only blueprint for turning `./experiments/code/` into a continuously running, remotely accessible workflow based on LangChain/LangGraph.

- Scope: architecture, machine-readable contracts, scoring model, knowledge-base updates, deployment and migration plans.
- Non-scope: direct implementation changes in this round.

## Recommended Read Order

1. `blueprint_manifest.yaml`
2. `01_system_blueprint.md`
3. `02_workflow_dag.yaml`
4. `03_data_contracts.md`
5. `04_scoring_policy.md`
6. `05_knowledge_base_design.md`
7. `06_deployment_ops.md`
8. `07_migration_plan.md`
9. `08_agent_playbook.md`
10. `09_openapi_draft.yaml`
11. `10_multi_agent_provider_design.md`
12. `11_provider_matrix.yaml`
13. `12_optimization_backlog.md`

## Existing Capability Coverage (Current Project)

- Ingestion/download: `experiments/code/Paper_AllDownload_new.ipynb`
- Metadata collection: `experiments/code/Paper_AllMetadata_new.ipynb`
- PDF preprocessing: `experiments/code/pdf2String_local_bestFilter.ipynb`
- LLM extraction: `experiments/code/LLM_API_Call.py`, `experiments/code/pdf_Analysis_new_multiprocessing.py`
- Graph/relation build: `experiments/code/Dataset_KnowledgeGraph.ipynb`
- Value analysis: `experiments/code/DataDebtAnalysis.ipynb`, `experiments/code/finalCalculation.ipynb`
- Ground-truth evaluation: `experiments/code/ground_truth_eval.py`, `experiments/code/plot_gt_eval.py`

## Human + Agent Usability

- Human-readable docs: Markdown files.
- Agent-readable contracts: YAML workflow DAG + OpenAPI draft + provider matrix + JSON Schemas.
- Every major stage has explicit I/O contracts and failure policies.
- Methodology alignment highlights:
  - ontology-aware prompt engineering node for extraction (LLM_API_Call-style)
  - mandatory evidence-grounding gate before normalization
  - mandatory ontology-schema validation gate before downstream scoring
  - mandatory Magic Byte inspection node in DAG
  - external signal enrichment (OpenAlex etc.) + staged availability modeling
  - mandatory Passive Mention scoring submodule
  - DDI report and dashboard payload contracts with API endpoints
  - job-level alignment metrics exposed via OpenAPI status payload
  - ops pipeline snapshot + prompt diagnostics for maintainer debugging UI

## Provider Scope

- Primary provider set in this blueprint:
  - OpenAI
  - Zhipu
  - Claude (Anthropic)
- Routing and failover policy source: `11_provider_matrix.yaml`

## Version

- Blueprint version: `v1.2`
- Updated at: `2026-03-01`
