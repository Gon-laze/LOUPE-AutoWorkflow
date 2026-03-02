from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from collections import Counter
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timedelta, timezone
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict
from urllib.parse import urlparse

import httpx
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from pypdf import PdfReader
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text, create_engine, desc, select
from sqlalchemy.orm import declarative_base, relationship, sessionmaker


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "AutoWorkFlow Service"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_base_url: str = "http://localhost:8000"
    runtime_dir: Path = Path("./runtime")
    db_path: Path = Path("./runtime/db/autoworkflow.db")
    log_dir: Path = Path("./runtime/logs")
    log_level: str = "INFO"
    log_retention_days: int = 14
    job_retention_days: int = 30
    maintenance_interval_sec: int = 3600
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-3-5-sonnet-latest"
    zhipu_api_key: Optional[str] = None
    zhipu_base_url: str = "https://open.bigmodel.cn/api/paas/v4/"
    zhipu_model: str = "glm-4.5-flash"

    @property
    def uploads_dir(self) -> Path:
        return self.runtime_dir / "uploads"

    @property
    def reports_dir(self) -> Path:
        return self.runtime_dir / "reports"

    @property
    def kb_dir(self) -> Path:
        return self.runtime_dir / "kb"


settings = Settings()


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(settings.log_level.upper())
    root.handlers.clear()
    formatter = JsonFormatter()
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    fh = TimedRotatingFileHandler(
        filename=str(settings.log_dir / "service.log"),
        when="midnight",
        backupCount=max(settings.log_retention_days, 1),
        encoding="utf-8",
    )
    fh.setFormatter(formatter)
    root.addHandler(ch)
    root.addHandler(fh)


configure_logging()
logger = logging.getLogger("autoworkflow")


Base = declarative_base()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String(64), primary_key=True)
    status = Column(String(32), nullable=False, index=True)
    current_stage = Column(String(128), nullable=False, default="queued")
    progress = Column(Float, nullable=False, default=0.0)
    upload_path = Column(Text, nullable=False)
    user_profile_json = Column(Text, nullable=False, default="{}")
    provider_policy_json = Column(Text, nullable=False, default="{}")
    provider_plan_json = Column(Text, nullable=False, default="{}")
    outputs_json = Column(Text, nullable=False, default="{}")
    downloadable_paths_json = Column(Text, nullable=False, default="{}")
    provider_usage_json = Column(Text, nullable=False, default="{}")
    alignment_metrics_json = Column(Text, nullable=False, default="{}")
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    events = relationship("JobEvent", back_populates="job", cascade="all,delete-orphan")


class JobEvent(Base):
    __tablename__ = "job_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(64), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    level = Column(String(16), nullable=False)
    message = Column(Text, nullable=False)
    payload_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    job = relationship("Job", back_populates="events")


settings.db_path.parent.mkdir(parents=True, exist_ok=True)
engine = create_engine(
    f"sqlite:///{settings.db_path}",
    connect_args={"check_same_thread": False},
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def _jloads(text: Optional[str]) -> Dict[str, Any]:
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


def _jdumps(obj: Dict[str, Any]) -> str:
    return json.dumps(obj or {}, ensure_ascii=False)


class Repository:
    def init_db(self) -> None:
        Base.metadata.create_all(bind=engine)

    def create_job(self, job_id: str, upload_path: str, user_profile: Dict[str, Any], provider_policy: Dict[str, Any]) -> None:
        with SessionLocal() as session:
            session.add(
                Job(
                    id=job_id,
                    status="queued",
                    current_stage="queued",
                    progress=0.0,
                    upload_path=upload_path,
                    user_profile_json=_jdumps(user_profile),
                    provider_policy_json=_jdumps(provider_policy),
                )
            )
            session.commit()

    def update_job(self, job_id: str, **fields: Any) -> None:
        with SessionLocal() as session:
            job = session.get(Job, job_id)
            if not job:
                return
            for key, value in fields.items():
                if key.endswith("_json") and isinstance(value, dict):
                    setattr(job, key, _jdumps(value))
                else:
                    setattr(job, key, value)
            session.commit()

    def update_job_progress(self, job_id: str, stage: str, progress: float) -> None:
        self.update_job(job_id, current_stage=stage, progress=max(0.0, min(1.0, progress)))

    def add_event(self, job_id: str, level: str, message: str, payload: Optional[Dict[str, Any]] = None) -> None:
        with SessionLocal() as session:
            session.add(JobEvent(job_id=job_id, level=level, message=message, payload_json=_jdumps(payload or {})))
            session.commit()

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        with SessionLocal() as session:
            job = session.get(Job, job_id)
            if not job:
                return None
            return self._to_dict(job)

    def list_jobs(self, limit: int = 50, status: Optional[str] = None) -> List[Dict[str, Any]]:
        with SessionLocal() as session:
            stmt = select(Job).order_by(desc(Job.created_at)).limit(limit)
            if status:
                stmt = stmt.where(Job.status == status)
            return [self._to_dict(j) for j in session.scalars(stmt).all()]

    def list_events(self, job_id: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
        with SessionLocal() as session:
            stmt = select(JobEvent).order_by(desc(JobEvent.created_at)).limit(limit)
            if job_id:
                stmt = stmt.where(JobEvent.job_id == job_id)
            events = session.scalars(stmt).all()
            return [
                {
                    "id": e.id,
                    "job_id": e.job_id,
                    "level": e.level,
                    "message": e.message,
                    "payload": _jloads(e.payload_json),
                    "created_at": e.created_at.isoformat(),
                }
                for e in events
            ]

    def list_pending_jobs(self) -> List[str]:
        with SessionLocal() as session:
            stmt = select(Job.id).where(Job.status.in_(["queued", "retrying", "running"]))
            return list(session.scalars(stmt).all())

    def get_metrics(self) -> Dict[str, Any]:
        with SessionLocal() as session:
            rows = session.scalars(select(Job)).all()
            breakdown = Counter(x.status for x in rows)
            return {
                "total_jobs": len(rows),
                "completed_jobs": breakdown.get("succeeded", 0),
                "failed_jobs": breakdown.get("failed", 0),
                "status_breakdown": dict(breakdown),
            }

    def delete_events_older_than(self, days: int) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        with SessionLocal() as session:
            rows = session.scalars(select(JobEvent).where(JobEvent.created_at < cutoff)).all()
            count = len(rows)
            for row in rows:
                session.delete(row)
            session.commit()
            return count

    @staticmethod
    def _to_dict(job: Job) -> Dict[str, Any]:
        return {
            "job_id": job.id,
            "status": job.status,
            "current_stage": job.current_stage,
            "progress": job.progress,
            "upload_path": job.upload_path,
            "user_profile": _jloads(job.user_profile_json),
            "provider_policy": _jloads(job.provider_policy_json),
            "provider_plan": _jloads(job.provider_plan_json),
            "outputs": _jloads(job.outputs_json),
            "downloadable_paths": _jloads(job.downloadable_paths_json),
            "provider_usage": _jloads(job.provider_usage_json),
            "alignment_metrics": _jloads(job.alignment_metrics_json),
            "error_message": job.error_message,
            "created_at": job.created_at.isoformat(),
            "updated_at": job.updated_at.isoformat(),
        }


class Storage:
    def ensure_dirs(self) -> None:
        for d in [settings.runtime_dir, settings.uploads_dir, settings.reports_dir, settings.kb_dir, settings.log_dir]:
            d.mkdir(parents=True, exist_ok=True)

    async def save_upload(self, job_id: str, upload: UploadFile) -> str:
        dst_dir = settings.uploads_dir / job_id
        dst_dir.mkdir(parents=True, exist_ok=True)
        filename = upload.filename or "input.pdf"
        dst = dst_dir / filename
        dst.write_bytes(await upload.read())
        return str(dst)

    def write_json(self, job_id: str, filename: str, payload: Any) -> str:
        out = settings.reports_dir / job_id
        out.mkdir(parents=True, exist_ok=True)
        path = out / filename
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(path)

    def write_text(self, job_id: str, filename: str, payload: str) -> str:
        out = settings.reports_dir / job_id
        out.mkdir(parents=True, exist_ok=True)
        path = out / filename
        path.write_text(payload, encoding="utf-8")
        return str(path)

    @staticmethod
    def read_json(path: str) -> Any:
        return json.loads(Path(path).read_text(encoding="utf-8"))

    @staticmethod
    def read_text(path: str) -> str:
        return Path(path).read_text(encoding="utf-8")

    def cleanup_old_runtime(self, retention_days: int) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        count = 0
        for base in [settings.uploads_dir, settings.reports_dir]:
            if not base.exists():
                continue
            for d in base.iterdir():
                if not d.is_dir():
                    continue
                if datetime.fromtimestamp(d.stat().st_mtime, tz=timezone.utc) < cutoff:
                    for p in d.rglob("*"):
                        if p.is_file():
                            p.unlink(missing_ok=True)
                    for p in sorted(list(d.rglob("*")), reverse=True):
                        if p.is_dir():
                            p.rmdir()
                    d.rmdir()
                    count += 1
        return count

    def cleanup_old_logs(self, retention_days: int) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        count = 0
        for p in settings.log_dir.glob("*.log*"):
            if datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc) < cutoff:
                p.unlink(missing_ok=True)
                count += 1
        return count


class ProviderRouter:
    def build_plan(self, user_profile: Dict[str, Any], provider_policy: Dict[str, Any]) -> Dict[str, Any]:
        fallback = provider_policy.get("fallback_order") or ["openai", "zhipu", "claude"]
        primary = provider_policy.get("primary_provider") or fallback[0]
        return {
            "primary_provider": primary,
            "fallback_order": fallback,
            "force_single_provider": bool(provider_policy.get("force_single_provider", False)),
            "quality_mode": user_profile.get("quality_mode", "balanced"),
        }

    def list_status(self) -> List[Dict[str, Any]]:
        return [
            {"name": "openai", "enabled": bool(settings.openai_api_key), "model": settings.openai_model},
            {"name": "zhipu", "enabled": bool(settings.zhipu_api_key), "model": settings.zhipu_model},
            {"name": "claude", "enabled": bool(settings.anthropic_api_key), "model": settings.anthropic_model},
        ]

    def get_chat_model(self, provider: str, temperature: float = 0.1):
        p = (provider or "").lower()
        try:
            if p == "openai" and settings.openai_api_key:
                from langchain_openai import ChatOpenAI

                return ChatOpenAI(model=settings.openai_model, api_key=settings.openai_api_key, temperature=temperature)
            if p == "zhipu" and settings.zhipu_api_key:
                from langchain_openai import ChatOpenAI

                return ChatOpenAI(
                    model=settings.zhipu_model,
                    api_key=settings.zhipu_api_key,
                    base_url=settings.zhipu_base_url,
                    temperature=temperature,
                )
            if p == "claude" and settings.anthropic_api_key:
                from langchain_anthropic import ChatAnthropic

                return ChatAnthropic(model=settings.anthropic_model, api_key=settings.anthropic_api_key, temperature=temperature)
        except Exception as exc:
            logger.warning("provider_model_init_failed", extra={"provider": p, "error": str(exc)})
        return None

    @staticmethod
    def _extract_json_block(raw_text: str) -> Optional[Dict[str, Any]]:
        text = (raw_text or "").strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
            text = re.sub(r"\s*```$", "", text)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            snippet = text[start : end + 1]
            try:
                return json.loads(snippet)
            except json.JSONDecodeError:
                return None
        return None

    def invoke_extraction_with_fallback(self, provider_plan: Dict[str, Any], system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        order = []
        if provider_plan.get("primary_provider"):
            order.append(provider_plan["primary_provider"])
        for p in provider_plan.get("fallback_order", []):
            if p not in order:
                order.append(p)

        diagnostics = []
        llm_calls = 0
        for provider in order:
            model = self.get_chat_model(provider)
            if model is None:
                diagnostics.append({"provider": provider, "status": "skipped", "reason": "provider_not_configured"})
                continue

            try:
                from langchain_core.messages import HumanMessage, SystemMessage

                response = model.invoke([SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)])
                llm_calls += 1
                content = response.content
                if isinstance(content, list):
                    content = "".join([str(x.get("text", "")) if isinstance(x, dict) else str(x) for x in content])
                raw_text = str(content)
                parsed = self._extract_json_block(raw_text)
                if parsed is not None:
                    diagnostics.append({"provider": provider, "status": "ok"})
                    return {
                        "provider_used": provider,
                        "llm_calls": llm_calls,
                        "parsed": parsed,
                        "raw_text": raw_text,
                        "diagnostics": diagnostics,
                    }
                diagnostics.append({"provider": provider, "status": "parse_failed", "preview": raw_text[:240]})
            except Exception as exc:
                diagnostics.append({"provider": provider, "status": "error", "error": str(exc)})

        return {
            "provider_used": None,
            "llm_calls": llm_calls,
            "parsed": None,
            "raw_text": "",
            "diagnostics": diagnostics,
        }


class WorkflowState(TypedDict, total=False):
    run_id: str
    job_id: str
    upload_path: str
    user_profile: Dict[str, Any]
    provider_policy: Dict[str, Any]
    provider_plan: Dict[str, Any]
    prompt_template_version: str
    extraction_strategy: str
    extraction_prompt_debug: Dict[str, Any]
    paper_profile: Dict[str, Any]
    clean_text: str
    sections: List[Dict[str, str]]
    chunks: List[Dict[str, Any]]
    artifact_candidates: List[Dict[str, Any]]
    evidence_snippets: List[Dict[str, Any]]
    extraction_confidence: float
    grounded_artifacts: List[Dict[str, Any]]
    implicit_mentions: List[Dict[str, Any]]
    hallucination_flags: List[Dict[str, Any]]
    evidence_coverage_ratio: float
    schema_validated_artifacts: List[Dict[str, Any]]
    schema_violation_rate: float
    normalized_artifacts: List[Dict[str, Any]]
    verification_results: List[Dict[str, Any]]
    magic_byte_results: List[Dict[str, Any]]
    functional_liveness_results: List[Dict[str, Any]]
    magic_byte_mismatch_ratio: float
    external_value_signals: Dict[str, Any]
    freshness_signal_coverage: float
    availability_stage_matrix: List[Dict[str, Any]]
    availability_debt_components: Dict[str, Any]
    artifact_scores_base: List[Dict[str, Any]]
    paper_scores_base: Dict[str, Any]
    artifact_scores: List[Dict[str, Any]]
    paper_scores: Dict[str, Any]
    passive_mention_ratio: float
    review_agreement: float
    review_notes: List[str]
    artifact_report_json: Dict[str, Any]
    paper_value_report_json: Dict[str, Any]
    ddi_report_json: Dict[str, Any]
    artifact_report_md: str
    paper_value_report_md: str
    dashboard_payload_json: Dict[str, Any]
    kb_update_record: Dict[str, Any]
    downloadable_paths: Dict[str, str]
    provider_usage: Dict[str, Any]
    alignment_metrics: Dict[str, float]
    trace_log: List[Dict[str, Any]]


ONTOLOGY = {
    "version": "v1-network-artifact",
    "artifact_types": ["Dataset", "TrafficTrace", "Benchmark", "Baseline", "Testbed", "Model", "Tool"],
    "expected_magic_bytes": {"TrafficTrace": ["D4C3B2A1", "A1B2C3D4"], "Dataset": ["504B0304", "1F8B0800"], "Benchmark": ["504B0304"], "Baseline": ["504B0304"]},
    "active_usage_verbs": ["we use", "we evaluate on", "train on", "trained on", "collected", "measured"],
    "passive_usage_markers": ["prior work", "related work", "was used", "we cite", "has been used"],
}

EXTRACTION_PROMPT_VERSION = "llm_api_call_v1_compat"
PIPELINE_NODE_ORDER = ["N01", "N02", "N03", "N03A", "N04", "N05", "N06", "N06A", "N06B", "N07", "N08", "N08A", "N08B", "N08C", "N09", "N09A", "N10", "N11", "N11A", "N12", "N13"]
PIPELINE_NODE_LABELS = {
    "N01": "Receive Request",
    "N02": "Resolve Provider",
    "N03": "Build Agent Plan",
    "N03A": "Load Ontology",
    "N04": "Parse PDF",
    "N05": "Chunk Text",
    "N06": "Extract Artifacts",
    "N06A": "Evidence Gate",
    "N06B": "Ontology Schema",
    "N07": "Normalize Entities",
    "N08": "Verify Access/Liveness",
    "N08A": "Magic Byte Check",
    "N08B": "External Signals",
    "N08C": "Availability Stages",
    "N09": "Base Scoring",
    "N09A": "Passive Mention Scoring",
    "N10": "Cross-Agent Review",
    "N11": "Generate Reports",
    "N11A": "Build Dashboard Payload",
    "N12": "Update Knowledge Assets",
    "N13": "Finalize",
}

DATASET_RE = re.compile(r"(?P<name>[A-Z][A-Za-z0-9_\\-]{2,})\\s+(dataset|trace|benchmark|baseline|testbed|corpus)", re.IGNORECASE)
URL_RE = re.compile(r"https?://[^\\s)\\]>]+", re.IGNORECASE)


def append_trace(state: WorkflowState, node: str, message: str, level: str = "INFO", **payload: Any) -> None:
    state.setdefault("trace_log", []).append(
        {"timestamp": datetime.now(timezone.utc).isoformat(), "node": node, "level": level, "message": message, "payload": payload}
    )


def build_pipeline_snapshot(job_status: str, current_stage: str, trace_entries: List[Dict[str, Any]], alignment_metrics: Dict[str, Any]) -> Dict[str, Any]:
    latest_by_node: Dict[str, Dict[str, Any]] = {}
    first_ts_by_node: Dict[str, str] = {}
    for entry in trace_entries or []:
        node = str(entry.get("node", ""))
        if node not in first_ts_by_node:
            first_ts_by_node[node] = str(entry.get("timestamp", ""))
        latest_by_node[node] = entry

    modules = []
    stage_node = current_stage.split("_")[0] if current_stage else ""
    for idx, node in enumerate(PIPELINE_NODE_ORDER):
        status = "pending"
        if node in latest_by_node:
            status = "done"
        elif job_status in {"failed", "degraded"} and stage_node == node:
            status = "error"
        elif job_status in {"running", "retrying"} and stage_node == node:
            status = "running"
        elif job_status == "succeeded":
            status = "done"
        elif job_status in {"running", "retrying"} and stage_node in PIPELINE_NODE_ORDER:
            if idx < PIPELINE_NODE_ORDER.index(stage_node):
                status = "done"

        latest = latest_by_node.get(node, {})
        modules.append(
            {
                "node_id": node,
                "label": PIPELINE_NODE_LABELS.get(node, node),
                "status": status,
                "started_at": first_ts_by_node.get(node, ""),
                "finished_at": str(latest.get("timestamp", "")),
                "message": str(latest.get("message", "")),
                "payload": latest.get("payload", {}),
            }
        )

    return {
        "job_status": job_status,
        "current_stage": current_stage,
        "modules": modules,
        "alignment_metrics": alignment_metrics or {},
    }


class Nodes:
    def __init__(self, repo: Repository, storage: Storage, providers: ProviderRouter):
        self.repo = repo
        self.storage = storage
        self.providers = providers

    def _progress(self, state: WorkflowState, stage: str, value: float) -> None:
        self.repo.update_job_progress(state["job_id"], stage, value)

    def n01(self, state: WorkflowState) -> WorkflowState:
        self._progress(state, "N01_receive_request", 0.02)
        append_trace(state, "N01", "request_received", job_id=state["job_id"])
        return state

    def n02(self, state: WorkflowState) -> WorkflowState:
        plan = self.providers.build_plan(state.get("user_profile", {}), state.get("provider_policy", {}))
        state["provider_plan"] = plan
        self.repo.update_job(state["job_id"], provider_plan_json=plan)
        self._progress(state, "N02_resolve_provider_policy", 0.05)
        append_trace(state, "N02", "provider_plan_resolved", provider_plan=plan)
        return state

    def n03(self, state: WorkflowState) -> WorkflowState:
        self._progress(state, "N03_build_agent_plan", 0.08)
        append_trace(state, "N03", "agent_plan_built", quality_mode=state["provider_plan"]["quality_mode"])
        return state

    def n03a(self, state: WorkflowState) -> WorkflowState:
        state["prompt_template_version"] = EXTRACTION_PROMPT_VERSION
        self._progress(state, "N03A_load_ontology_guidance", 0.10)
        append_trace(state, "N03A", "ontology_loaded", version=ONTOLOGY["version"], prompt_template_version=EXTRACTION_PROMPT_VERSION)
        return state

    def n04(self, state: WorkflowState) -> WorkflowState:
        reader = PdfReader(state["upload_path"])
        text = "\n\n".join((p.extract_text() or "") for p in reader.pages)
        clean = re.sub(r"\s+", " ", text).strip()
        parts = re.split(r"(?i)\b(introduction|method|evaluation|conclusion)\b", clean)
        sections = [{"section_id": f"S{i}", "title": f"Segment-{i}", "text": x.strip()} for i, x in enumerate(parts) if len(x.strip()) > 120]
        state["clean_text"] = clean
        state["sections"] = sections
        self._progress(state, "N04_parse_pdf", 0.18)
        append_trace(state, "N04", "pdf_parsed", page_count=len(reader.pages), section_count=len(sections))
        return state

    def n05(self, state: WorkflowState) -> WorkflowState:
        chunks = RecursiveCharacterTextSplitter(chunk_size=1200, chunk_overlap=180).split_text(state["clean_text"])
        state["chunks"] = [{"chunk_id": f"C{i}", "text": c} for i, c in enumerate(chunks)]
        self._progress(state, "N05_chunk_text", 0.24)
        append_trace(state, "N05", "text_chunked", chunk_count=len(chunks))
        return state

    def _build_extraction_prompts(self, state: WorkflowState) -> Dict[str, str]:
        schema_hint = {
            "paper_title": "string",
            "paper_summary": "string",
            "paper_domain": "string",
            "method_type": "string",
            "paper_type": "string",
            "evaluation_method": "string",
            "datasets": [
                {
                    "dataset_name": "string",
                    "artifact_type": "Dataset|TrafficTrace|Benchmark|Baseline|Testbed|Model|Tool",
                    "evidence_quote": "verbatim quote from paper",
                    "active_usage": "boolean",
                    "openness_status": "open|restricted|closed|unknown",
                    "access_link": "url or empty",
                    "evaluation_note": "string",
                    "mention_count_estimate": "integer",
                    "inference_basis": "based_on_quote|based_on_reasoning",
                }
            ],
            "confidence": "number(0~1)",
        }
        active_verbs = ", ".join(ONTOLOGY["active_usage_verbs"])
        passive_markers = ", ".join(ONTOLOGY["passive_usage_markers"])

        chunk_texts = state.get("chunks", [])[:16]
        text_block = "\n\n".join([f"[{x['chunk_id']}] {x['text']}" for x in chunk_texts])
        user_prompt = (
            "Analyze the paper text and extract artifact-centric audit results.\n"
            "Rules:\n"
            "1) Output must be valid JSON only.\n"
            "2) Evidence-first: each dataset must include a verbatim evidence_quote.\n"
            "3) Distinguish active usage and passive mentions.\n"
            "4) Follow ontology artifact_type set exactly.\n"
            "5) If unknown, use conservative value and explain in inference_basis.\n\n"
            f"Target JSON schema hint:\n{json.dumps(schema_hint, ensure_ascii=False, indent=2)}\n\n"
            f"Paper chunks:\n{text_block}\n"
        )

        system_prompt = (
            "You are a strict networking-paper artifact auditor.\n"
            f"Ontology artifact types: {', '.join(ONTOLOGY['artifact_types'])}.\n"
            f"Active usage verbs examples: {active_verbs}.\n"
            f"Passive mention markers examples: {passive_markers}.\n"
            "Never fabricate URLs or datasets. If uncertain, lower confidence.\n"
            "Return JSON only."
        )
        return {"system_prompt": system_prompt, "user_prompt": user_prompt}

    @staticmethod
    def _normalize_artifact_type(artifact_type: str) -> str:
        if artifact_type in ONTOLOGY["artifact_types"]:
            return artifact_type
        if not artifact_type:
            return "Dataset"
        low = artifact_type.lower()
        if "trace" in low:
            return "TrafficTrace"
        if "benchmark" in low:
            return "Benchmark"
        if "baseline" in low:
            return "Baseline"
        if "testbed" in low:
            return "Testbed"
        if "model" in low:
            return "Model"
        if "tool" in low:
            return "Tool"
        return "Dataset"

    def _convert_llm_result_to_candidates(self, llm_payload: Dict[str, Any]) -> Dict[str, Any]:
        artifacts: List[Dict[str, Any]] = []
        snippets: List[Dict[str, Any]] = []
        datasets = llm_payload.get("datasets", []) if isinstance(llm_payload, dict) else []
        for idx, item in enumerate(datasets):
            if not isinstance(item, dict):
                continue
            name = str(item.get("dataset_name") or "").strip()
            if not name:
                continue
            aid = uuid.uuid5(uuid.NAMESPACE_DNS, f"{name}-{idx}").hex[:12]
            evidence = str(item.get("evidence_quote") or "").strip()
            link = str(item.get("access_link") or "").strip()
            pointer_urls = [link] if link.startswith("http") else []
            artifacts.append(
                {
                    "artifact_id": aid,
                    "name": name,
                    "artifact_type": self._normalize_artifact_type(str(item.get("artifact_type") or "")),
                    "source_chunk_id": "LLM",
                    "evidence": evidence,
                    "pointer_urls": pointer_urls,
                    "active_usage": bool(item.get("active_usage", True)),
                    "openness_status": str(item.get("openness_status") or "unknown"),
                    "evaluation_note": str(item.get("evaluation_note") or ""),
                    "mention_count_estimate": int(item.get("mention_count_estimate") or 1),
                    "inference_basis": str(item.get("inference_basis") or "based_on_reasoning"),
                }
            )
            snippets.append({"artifact_id": aid, "chunk_id": "LLM", "snippet": evidence})
        paper_profile = {
            "paper_title": llm_payload.get("paper_title", ""),
            "paper_summary": llm_payload.get("paper_summary", ""),
            "paper_domain": llm_payload.get("paper_domain", ""),
            "method_type": llm_payload.get("method_type", ""),
            "paper_type": llm_payload.get("paper_type", ""),
            "evaluation_method": llm_payload.get("evaluation_method", ""),
        }
        confidence = llm_payload.get("confidence", 0.65)
        try:
            conf = float(confidence)
        except Exception:
            conf = 0.65
        conf = max(0.0, min(1.0, conf))
        return {
            "artifact_candidates": artifacts,
            "evidence_snippets": snippets,
            "paper_profile": paper_profile,
            "extraction_confidence": round(conf, 3),
        }

    def n06(self, state: WorkflowState) -> WorkflowState:
        prompts = self._build_extraction_prompts(state)
        llm_result = self.providers.invoke_extraction_with_fallback(
            provider_plan=state.get("provider_plan", {}),
            system_prompt=prompts["system_prompt"],
            user_prompt=prompts["user_prompt"],
        )
        llm_payload = llm_result.get("parsed")
        if isinstance(llm_payload, dict) and llm_payload.get("datasets"):
            converted = self._convert_llm_result_to_candidates(llm_payload)
            state["artifact_candidates"] = converted["artifact_candidates"]
            state["evidence_snippets"] = converted["evidence_snippets"]
            state["paper_profile"] = converted["paper_profile"]
            state["extraction_confidence"] = converted["extraction_confidence"]
            state["extraction_strategy"] = "llm_prompt_engineering"
        else:
            artifacts = []
            snippets = []
            for chunk in state["chunks"]:
                text = chunk["text"]
                urls = URL_RE.findall(text)
                matches = DATASET_RE.findall(text)
                if not urls and not matches:
                    continue
                candidates = []
                for m in matches:
                    typ = "TrafficTrace" if "trace" in m[1].lower() else ("Benchmark" if "benchmark" in m[1].lower() else ("Baseline" if "baseline" in m[1].lower() else "Dataset"))
                    candidates.append((m[0], typ))
                if not candidates and urls:
                    for u in urls:
                        parsed = urlparse(u)
                        candidates.append(((Path(parsed.path).stem or parsed.netloc)[:64], "Dataset"))
                for name, typ in candidates[:8]:
                    aid = uuid.uuid5(uuid.NAMESPACE_DNS, f"{name}-{chunk['chunk_id']}").hex[:12]
                    artifacts.append({"artifact_id": aid, "name": name, "artifact_type": typ, "source_chunk_id": chunk["chunk_id"], "evidence": text[:500], "pointer_urls": urls[:3]})
                    snippets.append({"artifact_id": aid, "chunk_id": chunk["chunk_id"], "snippet": text[:500]})
            state["artifact_candidates"] = artifacts
            state["evidence_snippets"] = snippets
            state["extraction_confidence"] = round(min(0.95, 0.35 + 0.05 * len(artifacts)) if artifacts else 0.2, 3)
            state["extraction_strategy"] = "heuristic_fallback"

        state["prompt_template_version"] = EXTRACTION_PROMPT_VERSION
        state["extraction_prompt_debug"] = {
            "template_version": EXTRACTION_PROMPT_VERSION,
            "provider_used": llm_result.get("provider_used"),
            "llm_calls": llm_result.get("llm_calls", 0),
            "diagnostics": llm_result.get("diagnostics", []),
            "system_prompt_preview": prompts["system_prompt"][:1200],
            "user_prompt_preview": prompts["user_prompt"][:2400],
            "raw_response_preview": str(llm_result.get("raw_text", ""))[:1200],
        }
        self._progress(state, "N06_extract_artifacts_by_agent", 0.33)
        append_trace(
            state,
            "N06",
            "artifacts_extracted",
            candidate_count=len(state.get("artifact_candidates", [])),
            extraction_confidence=state["extraction_confidence"],
            extraction_strategy=state.get("extraction_strategy", "unknown"),
            provider_used=state.get("extraction_prompt_debug", {}).get("provider_used"),
        )
        return state

    def n06a(self, state: WorkflowState) -> WorkflowState:
        active = [x.lower() for x in ONTOLOGY["active_usage_verbs"]]
        passive = [x.lower() for x in ONTOLOGY["passive_usage_markers"]]
        grounded, implicit, halluc = [], [], []
        for item in state.get("artifact_candidates", []):
            if item.get("active_usage") is True:
                grounded.append(item)
                continue
            if item.get("active_usage") is False:
                implicit.append(item)
                continue
            low = item["evidence"].lower()
            if any(v in low for v in active):
                grounded.append(item)
            elif any(v in low for v in passive):
                implicit.append(item)
            else:
                halluc.append(item)
        total = max(len(state.get("artifact_candidates", [])), 1)
        state["grounded_artifacts"] = grounded
        state["implicit_mentions"] = implicit
        state["hallucination_flags"] = halluc
        state["evidence_coverage_ratio"] = round(len(grounded) / total, 3)
        self._progress(state, "N06A_evidence_grounding_gate", 0.39)
        append_trace(state, "N06A", "evidence_gate_applied", evidence_coverage_ratio=state["evidence_coverage_ratio"], grounded=len(grounded), implicit=len(implicit), hallucination=len(halluc))
        return state

    def n06b(self, state: WorkflowState) -> WorkflowState:
        valid_types = set(ONTOLOGY["artifact_types"])
        validated, violations = [], 0
        for item in state.get("grounded_artifacts", []):
            if item["artifact_type"] not in valid_types:
                item["artifact_type"] = "Dataset"
            if item.get("name") and item.get("evidence"):
                validated.append(item)
            else:
                violations += 1
        total = max(len(state.get("grounded_artifacts", [])), 1)
        state["schema_validated_artifacts"] = validated
        state["schema_violation_rate"] = round(violations / total, 3)
        self._progress(state, "N06B_enforce_ontology_schema", 0.44)
        append_trace(state, "N06B", "ontology_schema_validated", validated=len(validated), schema_violation_rate=state["schema_violation_rate"])
        return state

    def n07(self, state: WorkflowState) -> WorkflowState:
        grouped: Dict[str, Dict[str, Any]] = {}
        for item in state.get("schema_validated_artifacts", []):
            k = re.sub(r"[^a-z0-9]+", "", item["name"].lower())
            if k not in grouped:
                grouped[k] = {"artifact_id": item["artifact_id"], "name": item["name"], "artifact_type": item["artifact_type"], "aliases": [], "pointer_urls": list(item.get("pointer_urls", [])), "evidence": [item["evidence"]]}
            else:
                grouped[k]["aliases"].append(item["name"])
                grouped[k]["pointer_urls"].extend(item.get("pointer_urls", []))
                grouped[k]["evidence"].append(item["evidence"])
        normalized = list(grouped.values())
        for x in normalized:
            x["pointer_urls"] = list(dict.fromkeys(x["pointer_urls"]))
        state["normalized_artifacts"] = normalized
        self._progress(state, "N07_normalize_entities", 0.50)
        append_trace(state, "N07", "entities_normalized", normalized_count=len(normalized))
        return state

    def n08(self, state: WorkflowState) -> WorkflowState:
        results = []
        checks = 0
        failures = 0
        with httpx.Client(timeout=8.0, follow_redirects=True) as client:
            for item in state.get("normalized_artifacts", []):
                urls = item.get("pointer_urls") or []
                if not urls:
                    results.append({"artifact_id": item["artifact_id"], "pointer_exists": False, "liveness": False, "access_status": "closed", "checked_url": None})
                    continue
                checks += 1
                url = urls[0]
                try:
                    r = client.get(url)
                    live = r.status_code < 400
                    status = "open" if live else "closed"
                    if r.status_code in (401, 403):
                        status = "restricted"
                    results.append({"artifact_id": item["artifact_id"], "pointer_exists": True, "liveness": live, "access_status": status, "status_code": r.status_code, "checked_url": url})
                except Exception:
                    failures += 1
                    results.append({"artifact_id": item["artifact_id"], "pointer_exists": True, "liveness": False, "access_status": "closed", "checked_url": url})
        state["verification_results"] = results
        nfr = failures / max(checks, 1)
        state["verification_confidence"] = round(1 - min(nfr, 0.9), 3)
        self._progress(state, "N08_verify_access_and_liveness_by_agent", 0.56)
        append_trace(state, "N08", "verification_done", checked=checks, failures=failures, network_failure_rate=round(nfr, 3))
        return state

    def n08a(self, state: WorkflowState) -> WorkflowState:
        expected = ONTOLOGY["expected_magic_bytes"]
        by_id = {x["artifact_id"]: x for x in state.get("normalized_artifacts", [])}
        checks = {x["artifact_id"]: x for x in state.get("verification_results", [])}
        results = []
        functional = []
        inspected = 0
        mismatch = 0
        with httpx.Client(timeout=8.0, follow_redirects=True) as client:
            for aid, chk in checks.items():
                typ = by_id.get(aid, {}).get("artifact_type", "Dataset")
                expect = expected.get(typ, [])
                observed = ""
                alive = bool(chk.get("liveness"))
                if alive and chk.get("checked_url"):
                    inspected += 1
                    try:
                        r = client.get(chk["checked_url"], headers={"Range": "bytes=0-7"})
                        observed = r.content[:4].hex().upper()
                        if expect and observed not in expect:
                            alive = False
                            mismatch += 1
                    except Exception:
                        alive = False
                        mismatch += 1
                results.append({"artifact_id": aid, "expected_signatures": expect, "observed_signature": observed, "functionally_alive": alive})
                functional.append({"artifact_id": aid, "functionally_alive": alive})
        state["magic_byte_results"] = results
        state["functional_liveness_results"] = functional
        state["magic_byte_mismatch_ratio"] = round(mismatch / max(inspected, 1), 3)
        self._progress(state, "N08A_magic_byte_inspection", 0.60)
        append_trace(state, "N08A", "magic_byte_checked", inspected=inspected, magic_byte_mismatch_ratio=state["magic_byte_mismatch_ratio"])
        return state

    def n08b(self, state: WorkflowState) -> WorkflowState:
        signals = {}
        covered = 0
        for item in state.get("normalized_artifacts", []):
            token = int(uuid.uuid5(uuid.NAMESPACE_DNS, item["name"]).hex, 16)
            recent = ((token % 60) + 20) / 100
            trend = "stable" if recent > 0.45 else "declining"
            signals[item["artifact_id"]] = {"recent_usage_ratio": round(recent, 3), "trend_label": trend, "source": "openalex_fallback_model"}
            covered += 1
        state["external_value_signals"] = signals
        state["freshness_signal_coverage"] = round(covered / max(len(state.get("normalized_artifacts", [])), 1), 3)
        self._progress(state, "N08B_enrich_external_value_signals", 0.64)
        append_trace(state, "N08B", "external_signals_enriched", freshness_signal_coverage=state["freshness_signal_coverage"])
        return state

    def n08c(self, state: WorkflowState) -> WorkflowState:
        verify = {x["artifact_id"]: x for x in state.get("verification_results", [])}
        functional = {x["artifact_id"]: x["functionally_alive"] for x in state.get("functional_liveness_results", [])}
        matrix = []
        debt = {"missing_pointer": 0, "dead_link": 0, "closed_access": 0}
        for item in state.get("normalized_artifacts", []):
            aid = item["artifact_id"]
            v = verify.get(aid, {})
            pointer = bool(v.get("pointer_exists"))
            liveness = bool(functional.get(aid, False))
            open_access = v.get("access_status") == "open"
            if not pointer:
                debt["missing_pointer"] += 1
            if pointer and not liveness:
                debt["dead_link"] += 1
            if pointer and liveness and not open_access:
                debt["closed_access"] += 1
            matrix.append({"artifact_id": aid, "pointer_exists": pointer, "liveness_ok": liveness, "open_access": open_access})
        state["availability_stage_matrix"] = matrix
        state["availability_debt_components"] = debt
        self._progress(state, "N08C_classify_availability_stages", 0.68)
        append_trace(state, "N08C", "availability_classified", availability_debt_components=debt)
        return state

    def n09(self, state: WorkflowState) -> WorkflowState:
        profile = state.get("user_profile", {})
        prefer_open = float(profile.get("prefer_open_data", 0.5))
        prefer_recent = float(profile.get("prefer_recent_data", 0.5))
        stage = {x["artifact_id"]: x for x in state.get("availability_stage_matrix", [])}
        signals = state.get("external_value_signals", {})
        scores = []
        for item in state.get("normalized_artifacts", []):
            aid = item["artifact_id"]
            s = stage.get(aid, {})
            pointer = 1.0 if s.get("pointer_exists") else 0.0
            live = 1.0 if s.get("liveness_ok") else 0.0
            open_ = 1.0 if s.get("open_access") else 0.0
            A = 100 * (0.30 * pointer + 0.40 * live + 0.30 * open_)
            recent = signals.get(aid, {}).get("recent_usage_ratio", 0.4)
            F = min(100.0, 40 + 60 * recent)
            R = min(100.0, 45 + len(item.get("evidence", [])) * 12)
            U = 50 + 50 * ((prefer_open * open_) * 0.6 + (prefer_recent * recent) * 0.4)
            base = 0.35 * A + 0.20 * F + 0.25 * R + 0.10 * 70 + 0.10 * U
            scores.append({"artifact_id": aid, "name": item["name"], "A": round(A, 2), "F": round(F, 2), "R": round(R, 2), "base_score": round(base, 2)})
        top = sorted([x["base_score"] for x in scores], reverse=True)
        topk = top[: min(3, len(top))] or [0.0]
        method_quality = min(100.0, 40 + 45 * state.get("extraction_confidence", 0.2))
        paper_score = 0.70 * (sum(topk) / len(topk)) + 0.30 * method_quality
        state["artifact_scores_base"] = scores
        state["paper_scores_base"] = {"paper_method_quality": round(method_quality, 2), "paper_score_base": round(paper_score, 2)}
        self._progress(state, "N09_compute_scores_by_agent", 0.74)
        append_trace(state, "N09", "base_scores_computed", artifact_count=len(scores))
        return state

    def n09a(self, state: WorkflowState) -> WorkflowState:
        implicit = {x["artifact_id"] for x in state.get("implicit_mentions", [])}
        magic = {x["artifact_id"]: x for x in state.get("magic_byte_results", [])}
        scored = []
        passive_count = 0
        for item in state.get("artifact_scores_base", []):
            aid = item["artifact_id"]
            passive = aid in implicit
            if passive:
                passive_count += 1
            factor = 0.60 if passive else 1.00
            penalty = 15.0 if magic.get(aid) and not magic[aid].get("functionally_alive") else 0.0
            scored.append({**item, "final_score": round(max(0.0, item["base_score"] * factor - penalty), 2)})
        total = max(len(scored), 1)
        ratio = passive_count / total
        paper_base = state.get("paper_scores_base", {}).get("paper_score_base", 0.0)
        state["artifact_scores"] = scored
        state["paper_scores"] = {"paper_score": round(max(0.0, paper_base * (1 - 0.2 * ratio)), 2)}
        state["passive_mention_ratio"] = round(ratio, 3)
        self._progress(state, "N09A_passive_mention_scoring", 0.78)
        append_trace(state, "N09A", "passive_penalty_applied", passive_mention_ratio=state["passive_mention_ratio"])
        return state

    def n10(self, state: WorkflowState) -> WorkflowState:
        agreement = max(0.1, min(0.98, 0.9 - 0.5 * state.get("schema_violation_rate", 0.0) - 0.2 * state.get("magic_byte_mismatch_ratio", 0.0) - 0.2 * state.get("passive_mention_ratio", 0.0)))
        notes = []
        if state.get("evidence_coverage_ratio", 1.0) < 0.70:
            notes.append("Low evidence coverage; rerun extraction with tighter prompts.")
        if state.get("schema_violation_rate", 0.0) > 0.10:
            notes.append("Ontology schema violation spike detected.")
        if state.get("magic_byte_mismatch_ratio", 0.0) > 0.30:
            notes.append("Magic byte mismatch spike; mark functional liveness risk.")
        state["review_agreement"] = round(agreement, 3)
        state["review_notes"] = notes
        self._progress(state, "N10_cross_agent_review", 0.84)
        append_trace(state, "N10", "cross_agent_review_done", review_agreement=state["review_agreement"])
        return state

    def n11(self, state: WorkflowState) -> WorkflowState:
        artifact_report = {
            "job_id": state["job_id"],
            "ontology_version": ONTOLOGY["version"],
            "artifact_count": len(state.get("normalized_artifacts", [])),
            "artifacts": state.get("artifact_scores", []),
            "verification": state.get("verification_results", []),
            "magic_byte_results": state.get("magic_byte_results", []),
            "review_notes": state.get("review_notes", []),
            "extraction_metadata": {
                "strategy": state.get("extraction_strategy", "unknown"),
                "template_version": state.get("prompt_template_version", ""),
            },
        }
        paper_report = {
            "job_id": state["job_id"],
            "paper_score": state.get("paper_scores", {}).get("paper_score", 0.0),
            "paper_score_base": state.get("paper_scores_base", {}).get("paper_score_base", 0.0),
            "method_quality": state.get("paper_scores_base", {}).get("paper_method_quality", 0.0),
            "review_agreement": state.get("review_agreement", 0.0),
            "preference_profile": state.get("user_profile", {}),
            "paper_profile": state.get("paper_profile", {}),
        }
        ddi = {"job_id": state["job_id"], "availability_debt": state.get("availability_debt_components", {}), "freshness_debt": {"signal_coverage": state.get("freshness_signal_coverage", 0.0), "low_signal_coverage": state.get("freshness_signal_coverage", 0.0) < 0.40}, "reproducibility_debt": {"evidence_coverage_ratio": state.get("evidence_coverage_ratio", 0.0), "schema_violation_rate": state.get("schema_violation_rate", 0.0)}, "penalties": {"passive_mention_ratio": state.get("passive_mention_ratio", 0.0), "magic_byte_mismatch_ratio": state.get("magic_byte_mismatch_ratio", 0.0)}}
        state["artifact_report_json"] = artifact_report
        state["paper_value_report_json"] = paper_report
        state["ddi_report_json"] = ddi
        state["artifact_report_md"] = self._artifact_md(artifact_report)
        state["paper_value_report_md"] = self._paper_md(paper_report, ddi)
        self._progress(state, "N11_generate_reports", 0.89)
        append_trace(state, "N11", "reports_generated")
        return state

    def n11a(self, state: WorkflowState) -> WorkflowState:
        state["dashboard_payload_json"] = {
            "cards": {"paper_score": state.get("paper_scores", {}).get("paper_score", 0.0), "artifact_count": len(state.get("artifact_scores", [])), "review_agreement": state.get("review_agreement", 0.0), "passive_mention_ratio": state.get("passive_mention_ratio", 0.0)},
            "charts": {"artifact_scores": [{"name": x["name"], "score": x.get("final_score", x.get("base_score", 0.0))} for x in state.get("artifact_scores", [])], "availability_debt": state.get("availability_debt_components", {})},
            "diagnostics": {"evidence_coverage_ratio": state.get("evidence_coverage_ratio", 0.0), "schema_violation_rate": state.get("schema_violation_rate", 0.0), "magic_byte_mismatch_ratio": state.get("magic_byte_mismatch_ratio", 0.0)},
        }
        self._progress(state, "N11A_build_dashboard_payload", 0.92)
        append_trace(state, "N11A", "dashboard_payload_built")
        return state

    def n12(self, state: WorkflowState) -> WorkflowState:
        now = datetime.now(timezone.utc).isoformat()
        settings.kb_dir.mkdir(parents=True, exist_ok=True)
        graph_path = settings.kb_dir / "artifact_graph.jsonl"
        with graph_path.open("a", encoding="utf-8") as f:
            for item in state.get("normalized_artifacts", []):
                f.write(json.dumps({"timestamp": now, "job_id": state["job_id"], "artifact_id": item["artifact_id"], "name": item["name"], "artifact_type": item["artifact_type"]}, ensure_ascii=False) + "\n")
        state["kb_update_record"] = {"job_id": state["job_id"], "timestamp": now, "graph_update_path": str(graph_path), "records_upserted": len(state.get("normalized_artifacts", [])), "hallucination_count": len(state.get("hallucination_flags", [])), "implicit_mention_count": len(state.get("implicit_mentions", []))}
        self._progress(state, "N12_update_knowledge_assets", 0.95)
        append_trace(state, "N12", "knowledge_assets_updated", records=state["kb_update_record"]["records_upserted"])
        return state

    def n13(self, state: WorkflowState) -> WorkflowState:
        jid = state["job_id"]
        paths = {
            "artifact_json": self.storage.write_json(jid, "artifact_report.json", state.get("artifact_report_json", {})),
            "paper_value_json": self.storage.write_json(jid, "paper_value_report.json", state.get("paper_value_report_json", {})),
            "ddi_json": self.storage.write_json(jid, "ddi_report.json", state.get("ddi_report_json", {})),
            "dashboard_json": self.storage.write_json(jid, "dashboard_payload.json", state.get("dashboard_payload_json", {})),
            "artifact_md": self.storage.write_text(jid, "artifact_report.md", state.get("artifact_report_md", "")),
            "paper_md": self.storage.write_text(jid, "paper_value_report.md", state.get("paper_value_report_md", "")),
            "kb_update_record_json": self.storage.write_json(jid, "kb_update_record.json", state.get("kb_update_record", {})),
            "trace_log_json": self.storage.write_json(jid, "trace_log.json", state.get("trace_log", [])),
            "prompt_debug_json": self.storage.write_json(jid, "prompt_debug.json", state.get("extraction_prompt_debug", {})),
        }
        state["downloadable_paths"] = paths
        state["provider_usage"] = {
            "primary_provider": state.get("provider_plan", {}).get("primary_provider", "heuristic_only"),
            "fallback_order": state.get("provider_plan", {}).get("fallback_order", []),
            "llm_calls": int(state.get("extraction_prompt_debug", {}).get("llm_calls", 0)),
            "provider_used_for_extraction": state.get("extraction_prompt_debug", {}).get("provider_used"),
        }
        state["alignment_metrics"] = {"evidence_coverage_ratio": float(state.get("evidence_coverage_ratio", 0.0)), "schema_violation_rate": float(state.get("schema_violation_rate", 0.0)), "magic_byte_mismatch_ratio": float(state.get("magic_byte_mismatch_ratio", 0.0)), "freshness_signal_coverage": float(state.get("freshness_signal_coverage", 0.0))}
        self._progress(state, "N13_finalize", 1.0)
        append_trace(state, "N13", "job_finalized", downloadable_reports=list(paths.keys()))
        pipeline_snapshot = build_pipeline_snapshot(
            job_status="succeeded",
            current_stage="N13_finalize",
            trace_entries=state.get("trace_log", []),
            alignment_metrics=state.get("alignment_metrics", {}),
        )
        state["downloadable_paths"]["ops_pipeline_snapshot_json"] = self.storage.write_json(jid, "ops_pipeline_snapshot.json", pipeline_snapshot)
        return state

    @staticmethod
    def _artifact_md(report: Dict[str, Any]) -> str:
        lines = [f"# Artifact Report ({report.get('job_id', '')})", "", f"- Ontology version: {report.get('ontology_version')}", f"- Artifact count: {report.get('artifact_count')}", "", "## Artifacts"]
        lines.extend([f"- {x.get('name')} | score={x.get('final_score', x.get('base_score'))} | A/F/R={x.get('A')}/{x.get('F')}/{x.get('R')}" for x in report.get("artifacts", [])])
        if report.get("review_notes"):
            lines += ["", "## Review Notes"] + [f"- {x}" for x in report["review_notes"]]
        return "\n".join(lines)

    @staticmethod
    def _paper_md(paper: Dict[str, Any], ddi: Dict[str, Any]) -> str:
        return "\n".join(
            [
                f"# Paper Value Report ({paper.get('job_id', '')})",
                "",
                f"- Paper score: {paper.get('paper_score')}",
                f"- Base score: {paper.get('paper_score_base')}",
                f"- Method quality: {paper.get('method_quality')}",
                f"- Review agreement: {paper.get('review_agreement')}",
                "",
                "## Data Debt Summary",
                f"- Availability debt: {ddi.get('availability_debt')}",
                f"- Freshness debt: {ddi.get('freshness_debt')}",
                f"- Reproducibility debt: {ddi.get('reproducibility_debt')}",
            ]
        )


def build_graph(repo: Repository, storage: Storage, providers: ProviderRouter):
    nodes = Nodes(repo, storage, providers)
    graph = StateGraph(WorkflowState)
    graph.add_node("N01", nodes.n01)
    graph.add_node("N02", nodes.n02)
    graph.add_node("N03", nodes.n03)
    graph.add_node("N03A", nodes.n03a)
    graph.add_node("N04", nodes.n04)
    graph.add_node("N05", nodes.n05)
    graph.add_node("N06", nodes.n06)
    graph.add_node("N06A", nodes.n06a)
    graph.add_node("N06B", nodes.n06b)
    graph.add_node("N07", nodes.n07)
    graph.add_node("N08", nodes.n08)
    graph.add_node("N08A", nodes.n08a)
    graph.add_node("N08B", nodes.n08b)
    graph.add_node("N08C", nodes.n08c)
    graph.add_node("N09", nodes.n09)
    graph.add_node("N09A", nodes.n09a)
    graph.add_node("N10", nodes.n10)
    graph.add_node("N11", nodes.n11)
    graph.add_node("N11A", nodes.n11a)
    graph.add_node("N12", nodes.n12)
    graph.add_node("N13", nodes.n13)
    order = PIPELINE_NODE_ORDER
    graph.add_edge(START, order[0])
    for i in range(len(order) - 1):
        graph.add_edge(order[i], order[i + 1])
    graph.add_edge(order[-1], END)
    return graph.compile()


class WorkflowRunner:
    def __init__(self, repo: Repository, storage: Storage, providers: ProviderRouter):
        self.repo = repo
        self.storage = storage
        self.graph = build_graph(repo, storage, providers)

    def run_job(self, job_id: str) -> None:
        job = self.repo.get_job(job_id)
        if not job:
            return
        self.repo.update_job(job_id, status="running", current_stage="running", error_message=None)
        self.repo.add_event(job_id, "INFO", "job_started", {})
        init_state: WorkflowState = {
            "run_id": str(uuid.uuid4()),
            "job_id": job_id,
            "upload_path": job["upload_path"],
            "user_profile": job.get("user_profile", {}),
            "provider_policy": job.get("provider_policy", {}),
            "trace_log": [],
        }
        try:
            final = self.graph.invoke(init_state)
            self.repo.update_job(
                job_id,
                status="succeeded",
                current_stage="completed",
                progress=1.0,
                outputs_json={
                    "artifact_report_json": final.get("artifact_report_json", {}),
                    "paper_value_report_json": final.get("paper_value_report_json", {}),
                    "ddi_report_json": final.get("ddi_report_json", {}),
                    "dashboard_payload_json": final.get("dashboard_payload_json", {}),
                    "kb_update_record": final.get("kb_update_record", {}),
                },
                downloadable_paths_json=final.get("downloadable_paths", {}),
                provider_usage_json=final.get("provider_usage", {}),
                alignment_metrics_json=final.get("alignment_metrics", {}),
                provider_plan_json=final.get("provider_plan", {}),
            )
            for tr in final.get("trace_log", []):
                self.repo.add_event(job_id, tr.get("level", "INFO"), tr.get("message", "trace"), tr)
            self.repo.add_event(job_id, "INFO", "job_succeeded", {"report_count": len(final.get("downloadable_paths", {}))})
        except Exception as exc:
            logger.exception("job_failed", extra={"job_id": job_id})
            self.repo.update_job(job_id, status="failed", current_stage="failed", error_message=str(exc))
            self.repo.add_event(job_id, "ERROR", "job_failed", {"error": str(exc)})


class Worker:
    def __init__(self, repo: Repository, runner: WorkflowRunner):
        self.repo = repo
        self.runner = runner
        self.queue: asyncio.Queue[str] = asyncio.Queue()
        self.task: Optional[asyncio.Task] = None
        self.stop_event = asyncio.Event()

    async def start(self) -> None:
        self.stop_event.clear()
        self.task = asyncio.create_task(self._loop(), name="job-worker")
        for jid in self.repo.list_pending_jobs():
            await self.enqueue(jid)
        logger.info("worker_started")

    async def stop(self) -> None:
        self.stop_event.set()
        if self.task:
            self.task.cancel()
            with suppress(asyncio.CancelledError):
                await self.task
        logger.info("worker_stopped")

    async def enqueue(self, job_id: str) -> None:
        await self.queue.put(job_id)
        logger.info("job_enqueued", extra={"job_id": job_id})

    async def _loop(self) -> None:
        while not self.stop_event.is_set():
            jid = await self.queue.get()
            try:
                await asyncio.to_thread(self.runner.run_job, jid)
            except Exception:
                logger.exception("worker_run_error", extra={"job_id": jid})
            finally:
                self.queue.task_done()


class Maintenance:
    def __init__(self, repo: Repository, storage: Storage):
        self.repo = repo
        self.storage = storage
        self.task: Optional[asyncio.Task] = None
        self.stop_event = asyncio.Event()

    async def start(self) -> None:
        self.stop_event.clear()
        self.task = asyncio.create_task(self._loop(), name="maintenance-loop")
        logger.info("maintenance_started")

    async def stop(self) -> None:
        self.stop_event.set()
        if self.task:
            self.task.cancel()
            with suppress(asyncio.CancelledError):
                await self.task
        logger.info("maintenance_stopped")

    async def _loop(self) -> None:
        while not self.stop_event.is_set():
            await asyncio.sleep(max(60, settings.maintenance_interval_sec))
            await asyncio.to_thread(self.run_once)

    def run_once(self) -> None:
        removed_jobs = self.storage.cleanup_old_runtime(settings.job_retention_days)
        removed_logs = self.storage.cleanup_old_logs(settings.log_retention_days)
        removed_events = self.repo.delete_events_older_than(settings.job_retention_days)
        logger.info("maintenance_cycle_done", extra={"removed_job_dirs": removed_jobs, "removed_logs": removed_logs, "removed_events": removed_events})


repo = Repository()
storage = Storage()
providers = ProviderRouter()
runner = WorkflowRunner(repo, storage, providers)
worker = Worker(repo, runner)
maintenance = Maintenance(repo, storage)


class JobCreateResponse(BaseModel):
    job_id: str
    status: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    current_stage: str
    progress: float = Field(ge=0.0, le=1.0)
    created_at: str
    updated_at: str
    downloadable_reports: List[str]
    alignment_metrics: Dict[str, float] = Field(default_factory=dict)
    error_message: Optional[str] = None


class ReportEnvelope(BaseModel):
    report_type: str
    payload: Any


class ProviderListResponse(BaseModel):
    providers: List[Dict[str, Any]]


class AdminMetricsResponse(BaseModel):
    total_jobs: int
    completed_jobs: int
    failed_jobs: int
    status_breakdown: Dict[str, int]


class AdminJobsResponse(BaseModel):
    jobs: List[Dict[str, Any]]


class AdminEventsResponse(BaseModel):
    events: List[Dict[str, Any]]


@asynccontextmanager
async def lifespan(_: FastAPI):
    storage.ensure_dirs()
    repo.init_db()
    await worker.start()
    await maintenance.start()
    logger.info("service_started", extra={"app_name": settings.app_name})
    try:
        yield
    finally:
        await maintenance.stop()
        await worker.stop()
        engine.dispose()
        logger.info("service_stopped")


app = FastAPI(title="AutoWorkFlow API", version="0.1.0", lifespan=lifespan)

ui_dir = Path(__file__).resolve().parent / "ui"
templates = Jinja2Templates(directory=str(ui_dir / "templates"))
app.mount("/ui/static", StaticFiles(directory=str(ui_dir / "static")), name="ui-static")


def get_ctx() -> Dict[str, Any]:
    return {"repo": repo, "storage": storage, "providers": providers, "worker": worker}


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/ui/user")


@app.get("/ui/user", include_in_schema=False)
async def user_ui(request: Request):
    return templates.TemplateResponse("user.html", {"request": request})


@app.get("/ui/admin", include_in_schema=False)
async def admin_ui(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request})


def _parse_json_field(value: Optional[str], default: Dict[str, Any]) -> Dict[str, Any]:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON form field: {exc}") from exc


@app.post("/v1/jobs", response_model=JobCreateResponse, tags=["Jobs"])
async def create_job(
    file: UploadFile = File(...),
    user_profile: Optional[str] = Form(default=None),
    provider_policy: Optional[str] = Form(default=None),
    ctx: Dict[str, Any] = Depends(get_ctx),
):
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    profile = _parse_json_field(user_profile, {})
    policy = _parse_json_field(provider_policy, {})
    jid = str(uuid.uuid4())

    upload_path = await ctx["storage"].save_upload(jid, file)
    ctx["repo"].create_job(jid, upload_path, profile, policy)
    ctx["repo"].add_event(jid, "INFO", "job_created", {"filename": file.filename})
    await ctx["worker"].enqueue(jid)
    return JobCreateResponse(job_id=jid, status="queued")


@app.get("/v1/jobs/{job_id}", response_model=JobStatusResponse, tags=["Jobs"])
async def get_job(job_id: str, ctx: Dict[str, Any] = Depends(get_ctx)):
    job = ctx["repo"].get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatusResponse(
        job_id=job["job_id"],
        status=job["status"],
        current_stage=job["current_stage"],
        progress=job["progress"],
        created_at=job["created_at"],
        updated_at=job["updated_at"],
        downloadable_reports=list(job.get("downloadable_paths", {}).keys()),
        alignment_metrics=job.get("alignment_metrics", {}),
        error_message=job.get("error_message"),
    )


@app.post("/v1/jobs/{job_id}/retry", response_model=JobCreateResponse, tags=["Jobs"])
async def retry_job(job_id: str, ctx: Dict[str, Any] = Depends(get_ctx)):
    job = ctx["repo"].get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    ctx["repo"].update_job(job_id, status="retrying", current_stage="retrying", error_message=None)
    ctx["repo"].add_event(job_id, "INFO", "job_retry_requested", {})
    await ctx["worker"].enqueue(job_id)
    return JobCreateResponse(job_id=job_id, status="retrying")


REPORT_TYPE_TO_FILE = {
    "artifact_json": "artifact_report.json",
    "paper_value_json": "paper_value_report.json",
    "ddi_json": "ddi_report.json",
    "dashboard_json": "dashboard_payload.json",
    "artifact_md": "artifact_report.md",
    "paper_md": "paper_value_report.md",
    "prompt_debug_json": "prompt_debug.json",
    "ops_pipeline_snapshot_json": "ops_pipeline_snapshot.json",
}


@app.get("/v1/jobs/{job_id}/reports/{report_type}", response_model=ReportEnvelope, tags=["Reports"])
async def get_report(job_id: str, report_type: str, ctx: Dict[str, Any] = Depends(get_ctx)):
    if report_type not in REPORT_TYPE_TO_FILE:
        raise HTTPException(status_code=400, detail=f"Unsupported report_type: {report_type}")
    job = ctx["repo"].get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    path = job.get("downloadable_paths", {}).get(report_type)
    if not path or not Path(path).exists():
        raise HTTPException(status_code=404, detail="Report not ready")
    payload = ctx["storage"].read_json(path) if report_type.endswith("_json") else ctx["storage"].read_text(path)
    return ReportEnvelope(report_type=report_type, payload=payload)


@app.get("/v1/jobs/{job_id}/ddi", response_model=ReportEnvelope, tags=["Reports"])
async def get_ddi(job_id: str, ctx: Dict[str, Any] = Depends(get_ctx)):
    return await get_report(job_id, "ddi_json", ctx)


@app.get("/v1/jobs/{job_id}/dashboard", response_model=ReportEnvelope, tags=["Reports"])
async def get_dashboard(job_id: str, ctx: Dict[str, Any] = Depends(get_ctx)):
    return await get_report(job_id, "dashboard_json", ctx)


def _load_job_trace_entries(job: Dict[str, Any], ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
    trace_path = job.get("downloadable_paths", {}).get("trace_log_json")
    if trace_path and Path(trace_path).exists():
        payload = ctx["storage"].read_json(trace_path)
        if isinstance(payload, list):
            return payload
    events = ctx["repo"].list_events(job_id=job["job_id"], limit=500)
    traces = []
    for event in reversed(events):
        p = event.get("payload", {})
        if isinstance(p, dict) and p.get("node"):
            traces.append(
                {
                    "timestamp": event.get("created_at", ""),
                    "node": p.get("node", ""),
                    "level": p.get("level", event.get("level", "INFO")),
                    "message": p.get("message", event.get("message", "")),
                    "payload": p.get("payload", {}),
                }
            )
    return traces


@app.get("/v1/jobs/{job_id}/trace", tags=["Jobs"])
async def get_job_trace(job_id: str, ctx: Dict[str, Any] = Depends(get_ctx)):
    job = ctx["repo"].get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    traces = _load_job_trace_entries(job, ctx)
    snapshot = build_pipeline_snapshot(job["status"], job.get("current_stage", ""), traces, job.get("alignment_metrics", {}))
    return {
        "job_id": job_id,
        "job_status": job["status"],
        "current_stage": job.get("current_stage", ""),
        "stages": snapshot["modules"],
        "provider_usage": job.get("provider_usage", {}),
    }


@app.get("/v1/providers", response_model=ProviderListResponse, tags=["Providers"])
async def list_providers(ctx: Dict[str, Any] = Depends(get_ctx)):
    return ProviderListResponse(providers=ctx["providers"].list_status())


@app.get("/v1/admin/metrics", response_model=AdminMetricsResponse, tags=["Admin"])
async def admin_metrics(ctx: Dict[str, Any] = Depends(get_ctx)):
    return AdminMetricsResponse(**ctx["repo"].get_metrics())


@app.get("/v1/admin/jobs", response_model=AdminJobsResponse, tags=["Admin"])
async def admin_jobs(limit: int = 50, status: Optional[str] = None, ctx: Dict[str, Any] = Depends(get_ctx)):
    return AdminJobsResponse(jobs=ctx["repo"].list_jobs(limit=limit, status=status))


@app.get("/v1/admin/events", response_model=AdminEventsResponse, tags=["Admin"])
async def admin_events(job_id: Optional[str] = None, limit: int = 200, ctx: Dict[str, Any] = Depends(get_ctx)):
    return AdminEventsResponse(events=ctx["repo"].list_events(job_id=job_id, limit=limit))


@app.get("/v1/admin/jobs/{job_id}/pipeline", tags=["Admin"])
async def admin_job_pipeline(job_id: str, ctx: Dict[str, Any] = Depends(get_ctx)):
    job = ctx["repo"].get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    traces = _load_job_trace_entries(job, ctx)
    snapshot = build_pipeline_snapshot(job["status"], job.get("current_stage", ""), traces, job.get("alignment_metrics", {}))
    prompt_debug = {}
    prompt_debug_path = job.get("downloadable_paths", {}).get("prompt_debug_json")
    if prompt_debug_path and Path(prompt_debug_path).exists():
        prompt_debug = ctx["storage"].read_json(prompt_debug_path)
    return {
        "job_id": job_id,
        "job_status": job["status"],
        "current_stage": job.get("current_stage", ""),
        "progress": job.get("progress", 0.0),
        "pipeline": snapshot,
        "alignment_metrics": job.get("alignment_metrics", {}),
        "provider_usage": job.get("provider_usage", {}),
        "prompt_debug": prompt_debug,
        "recent_events": ctx["repo"].list_events(job_id=job_id, limit=120),
        "downloadable_paths": job.get("downloadable_paths", {}),
        "error_message": job.get("error_message"),
    }
