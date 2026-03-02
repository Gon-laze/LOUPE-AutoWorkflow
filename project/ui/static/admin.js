const totalNode = document.getElementById("m-total");
const doneNode = document.getElementById("m-done");
const failedNode = document.getElementById("m-failed");
const jobsOutput = document.getElementById("jobs-output");
const eventsOutput = document.getElementById("events-output");
const pipelineGrid = document.getElementById("pipeline-grid");
const moduleDetail = document.getElementById("module-detail");
const promptDebugOutput = document.getElementById("prompt-debug-output");
const alignOutput = document.getElementById("align-output");
const jobHint = document.getElementById("job-hint");
const jobIdInput = document.getElementById("job-id-input");
const jobLoadBtn = document.getElementById("job-load-btn");

let selectedJobId = null;

const STATUS_CLASS = {
  done: ["st-done", "b-done"],
  running: ["st-running", "b-running"],
  pending: ["st-pending", "b-pending"],
  error: ["st-error", "b-error"],
};

function renderPipeline(payload) {
  pipelineGrid.innerHTML = "";
  const modules = (((payload || {}).pipeline || {}).modules || []);
  if (!modules.length) {
    pipelineGrid.textContent = "No module trace yet.";
    return;
  }

  modules.forEach((m) => {
    const card = document.createElement("div");
    const st = m.status || "pending";
    const [cardCls, badgeCls] = STATUS_CLASS[st] || STATUS_CLASS.pending;
    card.className = `node-card ${cardCls}`;
    card.innerHTML = `
      <p class="node-title">${m.node_id} · ${m.label}</p>
      <p class="node-sub"><span class="badge ${badgeCls}">${st.toUpperCase()}</span></p>
      <p class="node-sub">${m.message || ""}</p>
      <p class="node-sub">${m.finished_at || m.started_at || ""}</p>
    `;
    card.addEventListener("click", () => {
      moduleDetail.textContent = JSON.stringify(m, null, 2);
    });
    pipelineGrid.appendChild(card);
  });
}

async function loadPipeline(jobId) {
  if (!jobId) return;
  const resp = await fetch(`/v1/admin/jobs/${jobId}/pipeline`);
  if (!resp.ok) {
    jobHint.textContent = `Load failed: ${resp.status}`;
    return;
  }
  const data = await resp.json();
  selectedJobId = jobId;
  jobHint.textContent = `Status=${data.job_status}, Stage=${data.current_stage}, Progress=${data.progress}`;
  renderPipeline(data);
  promptDebugOutput.textContent = JSON.stringify(data.prompt_debug || {}, null, 2);
  alignOutput.textContent = JSON.stringify(
    {
      alignment_metrics: data.alignment_metrics || {},
      provider_usage: data.provider_usage || {},
      error_message: data.error_message || null,
    },
    null,
    2
  );
  eventsOutput.textContent = JSON.stringify(data.recent_events || [], null, 2);
}

jobLoadBtn.addEventListener("click", () => {
  const v = (jobIdInput.value || "").trim();
  if (!v) return;
  loadPipeline(v);
});

async function refresh() {
  const [mResp, jResp, eResp] = await Promise.all([
    fetch("/v1/admin/metrics"),
    fetch("/v1/admin/jobs?limit=20"),
    fetch("/v1/admin/events?limit=50"),
  ]);

  if (mResp.ok) {
    const m = await mResp.json();
    totalNode.textContent = m.total_jobs;
    doneNode.textContent = m.completed_jobs;
    failedNode.textContent = m.failed_jobs;
  }
  if (jResp.ok) {
    const j = await jResp.json();
    jobsOutput.textContent = JSON.stringify(j.jobs, null, 2);
    if (!selectedJobId && Array.isArray(j.jobs) && j.jobs.length > 0) {
      selectedJobId = j.jobs[0].job_id;
      jobIdInput.value = selectedJobId;
      await loadPipeline(selectedJobId);
    }
  }
  if (eResp.ok) {
    const e = await eResp.json();
    if (!selectedJobId) {
      eventsOutput.textContent = JSON.stringify(e.events, null, 2);
    }
  }

  if (selectedJobId) {
    await loadPipeline(selectedJobId);
  }
}

refresh();
setInterval(refresh, 5000);
