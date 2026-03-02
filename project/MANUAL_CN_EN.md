# AutoWorkFlow 使用与运维手册 (CN/EN)

## 1) 目标 | Goal

中文：  
本项目将 `experiments/code` 的论文审计能力重构为可长期运行的服务，核心是 LangGraph 工作流，遵循论文方法学：证据优先、本体约束、主动验证、Magic Byte、被动提及惩罚、Data Debt 指标。

English:  
This project refactors the paper-auditing capability from `experiments/code` into a continuously running service using a LangGraph workflow, aligned with the paper methodology: evidence-first, ontology constraint, active verification, Magic Byte checks, passive-mention penalty, and Data Debt metrics.

## 2) 系统组成 | Components

中文：
1. API：FastAPI（上传、状态查询、报告获取、重试）。
2. 工作流：LangGraph（N01~N13）。
3. 存储：SQLite + 本地文件系统。
4. 日志：结构化滚动日志 + `job_events` 表 + 定期清理。
5. 可视化：用户界面 `/ui/user`，运维界面 `/ui/admin`。

English:
1. API: FastAPI (upload, status, report retrieval, retry).
2. Workflow: LangGraph (N01~N13).
3. Storage: SQLite + local filesystem.
4. Logging: structured rotating logs + `job_events` + scheduled cleanup.
5. UI: user portal `/ui/user`, maintainer console `/ui/admin`.
6. Ops observability: per-job pipeline board via `/v1/admin/jobs/{job_id}/pipeline`.

## 3) 快速启动 | Quick Start

```bash
cd AutoWorkFlow/project
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python run.py
```

访问 | Open:
- User UI: `http://localhost:8000/ui/user`
- Admin UI: `http://localhost:8000/ui/admin`
- API Docs: `http://localhost:8000/docs`

## 4) 用户流程 | User Flow

中文：
1. 在 `/ui/user` 上传 PDF。
2. 可选填写 `user_profile`、`provider_policy` JSON。
3. 系统返回 `job_id` 并自动轮询进度。
4. 成功后可查看 `artifact_json / paper_value_json / ddi_json / dashboard_json`。

English:
1. Upload PDF at `/ui/user`.
2. Optionally fill `user_profile` and `provider_policy` JSON.
3. System returns `job_id` and polls status.
4. On success, view `artifact_json / paper_value_json / ddi_json / dashboard_json`.

## 5) 运维流程 | Ops Flow

中文：
1. 在 `/ui/admin` 查看任务总览与失败数。
2. 看最近任务与事件，定位失败节点。
3. API 深入排查：`/v1/admin/events?job_id=<id>`。
4. 必要时重试：`POST /v1/jobs/{job_id}/retry`。
5. 查看模块级状态与返回：`GET /v1/admin/jobs/{job_id}/pipeline`。

English:
1. Use `/ui/admin` for job overview and failures.
2. Inspect recent jobs/events to locate failing nodes.
3. Deep diagnosis via `/v1/admin/events?job_id=<id>`.
4. Retry by `POST /v1/jobs/{job_id}/retry`.

## 6) 日志维护 | Logging Maintenance

中文：
1. 日志文件：`runtime/logs/service.log*`（按日轮转）。
2. 节点 trace：落到 `job_events`。
3. 后台维护线程周期执行：
   - 清理过期上传与报告目录；
   - 清理过期日志文件；
   - 清理过期 `job_events`。

English:
1. Log files: `runtime/logs/service.log*` (daily rotation).
2. Node traces: persisted into `job_events`.
3. Background maintenance loop periodically:
   - deletes expired upload/report folders;
   - deletes expired log files;
   - deletes expired DB events.

Debug endpoints:
- `GET /v1/jobs/{job_id}/trace`: stage timeline summary.
- `GET /v1/admin/jobs/{job_id}/pipeline`: module cards + prompt/provider diagnostics + recent events.

## 7) 关键环境变量 | Important Env Vars

- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `ZHIPU_API_KEY`
- `OPENAI_MODEL`, `ANTHROPIC_MODEL`, `ZHIPU_MODEL`
- `RUNTIME_DIR`, `DB_PATH`, `LOG_DIR`
- `LOG_RETENTION_DAYS`, `JOB_RETENTION_DAYS`, `MAINTENANCE_INTERVAL_SEC`

## 8) 远程服务器部署 | Remote Deployment

### A. Ubuntu + systemd

```bash
sudo apt update && sudo apt install -y python3.11 python3.11-venv git
git clone <repo-url>
cd NetDataset_Analysis/AutoWorkFlow/project
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env (keys/models/retention)
```

创建 `/etc/systemd/system/autoworkflow.service`:

```ini
[Unit]
Description=AutoWorkFlow Service
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/NetDataset_Analysis/AutoWorkFlow/project
ExecStart=/opt/NetDataset_Analysis/AutoWorkFlow/project/.venv/bin/python run.py
Restart=always
RestartSec=5
User=ubuntu

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable autoworkflow
sudo systemctl start autoworkflow
sudo systemctl status autoworkflow
```

### B. Docker (可选 | optional)

```bash
cd AutoWorkFlow/project
cp .env.example .env
docker compose up -d --build
docker compose logs -f autoworkflow
```

## 9) 故障排查 | Troubleshooting

中文：
1. 报告未生成：先看 `/v1/jobs/{job_id}` 的 `current_stage` 和 `error_message`。
2. 链接验证失败多：检查服务器出网、DNS、代理策略。
3. LLM 不可用：检查 API Key；系统可退化为启发式抽取流程。

English:
1. Missing report: inspect `current_stage` and `error_message` from `/v1/jobs/{job_id}`.
2. High verification failures: check egress network, DNS, and proxy.
3. LLM unavailable: verify API keys; workflow can degrade to heuristic extraction.
