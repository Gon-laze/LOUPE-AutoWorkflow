# AutoWorkFlow Project

Implementation project under `AutoWorkFlow/project`, aligned with the blueprints and paper methodology.

- Runtime: FastAPI + LangGraph
- Storage: SQLite + local files
- UI: `/ui/user` and `/ui/admin`
- Logging: structured rotating logs + DB job events + retention cleanup
- Runtime behavior: heuristic extraction by default; provider keys can be configured for model-backed extension.

Quick start:

```bash
cd AutoWorkFlow/project
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python run.py
```

Open:

- User UI: `http://localhost:8000/ui/user`
- Admin UI: `http://localhost:8000/ui/admin`
- API docs: `http://localhost:8000/docs`

Manual: `MANUAL_CN_EN.md`.
