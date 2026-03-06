from __future__ import annotations

import json
import re
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import service


class _DummyRepo:
    def __init__(self) -> None:
        self.progress_calls = []

    def update_job_progress(self, job_id: str, stage: str, progress: float) -> None:
        self.progress_calls.append((job_id, stage, progress))


class DailyReportOutputTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="autowf-daily-report-")
        self._orig_runtime_dir = service.settings.runtime_dir
        service.settings.runtime_dir = Path(self._tmp.name)
        self.storage = service.Storage()
        self.storage.ensure_dirs()

    def tearDown(self) -> None:
        service.settings.runtime_dir = self._orig_runtime_dir
        self._tmp.cleanup()

    def test_daily_filename_suffix_uses_utc_day(self) -> None:
        day = datetime(2026, 3, 7, 13, 45, tzinfo=timezone.utc)
        self.assertEqual(service.Storage._daily_filename("artifact_report.json", day), "artifact_report_20260307.json")
        self.assertEqual(service.Storage._daily_filename("paper_value_report.md", day), "paper_value_report_20260307.md")

    def test_n13_writes_canonical_and_daily_reports(self) -> None:
        repo = _DummyRepo()
        nodes = service.Nodes(repo=repo, storage=self.storage, providers=service.ProviderRouter())

        state: service.WorkflowState = {
            "job_id": "job-daily-report-regression",
            "artifact_report_json": {"artifact_count": 1},
            "paper_value_report_json": {"paper_score": 0.9},
            "ddi_report_json": {"availability_debt": {}},
            "dashboard_payload_json": {"cards": {}},
            "artifact_report_md": "# artifact",
            "paper_value_report_md": "# paper",
            "kb_update_record": {"records_upserted": 1},
            "trace_log": [
                {
                    "timestamp": "2026-03-07T00:00:00+00:00",
                    "node": "N11",
                    "level": "INFO",
                    "message": "reports_generated",
                    "payload": {},
                }
            ],
            "extraction_prompt_debug": {"provider_used": "zhipu", "llm_calls": 1},
        }

        out = nodes.n13(state)
        report_dir = service.settings.reports_dir / state["job_id"]

        canonical_files = [
            "artifact_report.json",
            "paper_value_report.json",
            "ddi_report.json",
            "dashboard_payload.json",
            "artifact_report.md",
            "paper_value_report.md",
            "kb_update_record.json",
            "trace_log.json",
            "prompt_debug.json",
            "ops_pipeline_snapshot.json",
        ]
        for name in canonical_files:
            self.assertTrue((report_dir / name).exists(), f"Missing canonical report file: {name}")

        artifact_daily = Path(out["daily_report_paths"]["artifact_json_daily"]).name
        matched = re.search(r"_(\d{8})\.json$", artifact_daily)
        self.assertIsNotNone(matched, "Daily artifact filename should include YYYYMMDD suffix")
        day_tag = matched.group(1)

        daily_files = [
            f"artifact_report_{day_tag}.json",
            f"paper_value_report_{day_tag}.json",
            f"ddi_report_{day_tag}.json",
            f"dashboard_payload_{day_tag}.json",
            f"artifact_report_{day_tag}.md",
            f"paper_value_report_{day_tag}.md",
            f"kb_update_record_{day_tag}.json",
            f"trace_log_{day_tag}.json",
            f"prompt_debug_{day_tag}.json",
            f"ops_pipeline_snapshot_{day_tag}.json",
        ]
        for name in daily_files:
            self.assertTrue((report_dir / name).exists(), f"Missing daily report file: {name}")

        canonical_payload = json.loads(Path(out["downloadable_paths"]["artifact_json"]).read_text(encoding="utf-8"))
        dated_payload = json.loads(Path(out["daily_report_paths"]["artifact_json_daily"]).read_text(encoding="utf-8"))
        self.assertEqual(canonical_payload, dated_payload)
        self.assertIn((state["job_id"], "N13_finalize", 1.0), repo.progress_calls)


if __name__ == "__main__":
    unittest.main()
