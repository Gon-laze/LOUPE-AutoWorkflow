# AutoWorkFlow Project

Implementation project under `AutoWorkFlow/project`, aligned with the blueprints and paper methodology.

- Runtime: FastAPI + LangGraph
- Storage: SQLite + local files
- UI: `/ui/user` and `/ui/admin`
- Logging: structured rotating logs + DB job events + retention cleanup
- Runtime behavior: ontology-constrained prompt engineering with LangChain provider fallback, then heuristic fallback.
- Ops debug APIs: `/v1/jobs/{job_id}/trace`, `/v1/admin/jobs/{job_id}/pipeline`.

## Quick start

`run.py` is the primary startup entry.

```bash
cd AutoWorkFlow/project
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# REQUIRED: edit .env before start (API keys/models/runtime paths/proxy policy)
python run.py
```

If `.env` is not configured, LLM provider features will be partially or fully unavailable.

Open:

- User UI: `http://localhost:8000/ui/user`
- Admin UI: `http://localhost:8000/ui/admin`
- API docs: `http://localhost:8000/docs`

## Second startup method (systemd)

```bash
cd AutoWorkFlow/project
./scripts/install_systemd_service.sh
sudo systemctl status autoworkflow
```

`systemd` is the persistent runtime option. `python run.py` remains the primary direct startup method.

## Proxy policy

- `OPENAI_API_KEY` and `ANTHROPIC_API_KEY`: enable proxy before startup on this server.
- `ZHIPU_API_KEY`: disable proxy before startup on this server.

```bash
source ~/.bashrc_ProxyUse       # OpenAI / Anthropic
source ~/.bashrc_ProxyWithdraw  # Zhipu
```

## Compatibility scripts

- `./scripts/start_server.sh` runs `python run.py`
- `./scripts/manage_service.sh run` runs `python run.py`
- `./scripts/manage_service.sh install-systemd` installs systemd service

Manual: `MANUAL_CN_EN.md`.
