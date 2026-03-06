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

`run.py` 是主启动入口。
`run.py` is the primary startup entry.

```bash
cd AutoWorkFlow/project
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# REQUIRED: edit .env before start
python run.py
```

必须先补全 `.env`，否则很多功能将不受支持（尤其是 LLM provider 能力）。
You must configure `.env` before startup, or many features (especially LLM provider capabilities) will be unavailable.

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
1. 默认通过 `python run.py` 前台运行，直接观察终端返回。
2. 在 `/ui/admin` 查看任务总览与失败节点。
3. API 深入排查：`/v1/admin/events?job_id=<id>`。
4. 必要时重试：`POST /v1/jobs/{job_id}/retry`。

English:
1. Default operation is foreground `python run.py` with direct terminal output.
2. Use `/ui/admin` for failures and pipeline inspection.
3. Deep diagnosis via `/v1/admin/events?job_id=<id>`.
4. Retry by `POST /v1/jobs/{job_id}/retry`.

## 6) 日志维护 | Logging Maintenance

中文：
1. 服务日志：`runtime/logs/service.log*`（按日轮转）。
2. 节点 trace：落到 `job_events`。
3. 后台维护线程周期清理过期日志、上传、报告和事件。

English:
1. Service logs: `runtime/logs/service.log*` (daily rotation).
2. Node traces persisted in `job_events`.
3. Maintenance loop cleans expired logs/uploads/reports/events.

## 7) .env 参数说明 | .env Parameter Guide

通用运行参数 | Runtime:
- `APP_NAME`: 服务名称，仅用于显示与日志标识。
- `APP_HOST`: 监听地址，服务器部署一般用 `0.0.0.0`。
- `APP_PORT`: 监听端口。
- `APP_BASE_URL`: 对外访问基地址（用于报告内链接或回调拼接）。

路径参数 | Paths:
- `RUNTIME_DIR`: 运行时根目录（上传、报告、缓存）。
- `DB_PATH`: SQLite 数据库路径。
- `LOG_DIR`: 日志目录。

维护与清理 | Retention:
- `LOG_LEVEL`: 日志级别（`DEBUG/INFO/WARNING/ERROR`）。
- `LOG_RETENTION_DAYS`: 日志保留天数。
- `JOB_RETENTION_DAYS`: 任务相关文件保留天数。
- `MAINTENANCE_INTERVAL_SEC`: 后台维护周期（秒）。

模型与 Provider:
- `OPENAI_API_KEY`, `OPENAI_MODEL`
- `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`
- `ZHIPU_API_KEY`, `ZHIPU_BASE_URL`, `ZHIPU_MODEL`

最低可用建议：
1. 至少配置一个可用 Provider 的 API Key。
2. 修改 `.env` 后重启服务进程（前台重启或 systemd restart）。

## 8) 远程服务器部署 | Remote Deployment

### A. Ubuntu + systemd (第二启动手段 | second startup method)

```bash
sudo apt update && sudo apt install -y python3.11 python3.11-venv git
git clone <repo-url>
cd NetDataset_Analysis/AutoWorkFlow/project
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# REQUIRED: edit .env
./scripts/install_systemd_service.sh
sudo systemctl status autoworkflow
```

模板文件：`project/deploy/autoworkflow.service`

### B. Docker (optional)

```bash
cd AutoWorkFlow/project
cp .env.example .env
# REQUIRED: edit .env
docker compose up -d --build
docker compose logs -f autoworkflow
```

## 9) 故障排查 | Troubleshooting

中文：
1. 页面报 `ECONNREFUSED`：说明当前没有进程监听端口，请先确认 `python run.py` 是否仍在运行，或检查 systemd 服务状态。
2. 任务失败：看 `/v1/jobs/{job_id}` 的 `current_stage` 和 `error_message`。
3. LLM 不可用：检查 API Key、代理设置、模型名和服务出网能力。

English:
1. `ECONNREFUSED` means no process is listening on the target port. Check whether `python run.py` is still running, or inspect systemd service status.
2. Job failures: inspect `current_stage` and `error_message` from `/v1/jobs/{job_id}`.
3. LLM unavailable: check API keys, proxy, model names, and egress network.

## 10) 输入校验规范 | Input Validation Rules

中文：
1. 前端（`/ui/user`）使用结构化输入并实时生成 JSON。
2. `research_vs_production` / `prefer_open_data` / `prefer_recent_data` 必须在 `[0,1]`。
3. `quality_mode` 仅允许 `fast|balanced|high_quality`。
4. `primary_provider` 与 `fallback_order` 仅允许 `openai|zhipu|claude`，且 `fallback_order[0] = primary_provider`。
5. 后端在 `POST /v1/jobs` 再次校验，失败返回 `400`。

English:
1. Frontend uses structured inputs and emits JSON.
2. Ratio fields must be in `[0,1]`.
3. `quality_mode` must be one of `fast|balanced|high_quality`.
4. Provider policy must be valid and ordered by primary provider.
5. Backend enforces the same checks at `POST /v1/jobs`.

## 11) 代理策略 | Proxy Policy

中文：
1. `OPENAI_API_KEY` 与 `ANTHROPIC_API_KEY`：启动前开启代理。
2. `ZHIPU_API_KEY`：启动前关闭代理。
3. 推荐命令：

```bash
source ~/.bashrc_ProxyUse       # OpenAI / Anthropic
source ~/.bashrc_ProxyWithdraw  # Zhipu
```

English:
1. Enable proxy before startup for OpenAI/Anthropic.
2. Disable proxy before startup for Zhipu.

## 12) run.py 与 ECONNREFUSED 说明 | run.py And ECONNREFUSED

中文：
1. 当前 `run.py` 已恢复为直接运行（前台）方式，便于实时监视返回。
2. 若主动终止该进程，端口将不再有监听者，`ECONNREFUSED` 属于网络协议层的必然结果，不可能仅通过修改 `run.py` 在“无进程监听”时消除。
3. 若你需要“终止终端后仍可访问”，应使用 systemd 作为第二启动手段。

English:
1. `run.py` now uses direct foreground execution for immediate runtime visibility.
2. If you intentionally terminate that process, no listener remains on the port; `ECONNREFUSED` is expected behavior and cannot be eliminated purely in `run.py`.
3. If you need continued availability after terminal exit, use the systemd startup method.
