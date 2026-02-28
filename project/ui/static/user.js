let currentJobId = null;
let pollTimer = null;

const uploadForm = document.getElementById("upload-form");
const jobMeta = document.getElementById("job-meta");
const jobProgress = document.getElementById("job-progress");
const jobStage = document.getElementById("job-stage");
const reportOutput = document.getElementById("report-output");

uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const fileInput = document.getElementById("paper-file");
  if (!fileInput.files.length) {
    alert("Please choose a PDF file.");
    return;
  }

  const formData = new FormData();
  formData.append("file", fileInput.files[0]);
  formData.append("user_profile", document.getElementById("user-profile").value || "{}");
  formData.append("provider_policy", document.getElementById("provider-policy").value || "{}");

  const resp = await fetch("/v1/jobs", { method: "POST", body: formData });
  if (!resp.ok) {
    const txt = await resp.text();
    alert(`Job submit failed: ${txt}`);
    return;
  }
  const data = await resp.json();
  currentJobId = data.job_id;
  reportOutput.textContent = "No report loaded.";
  jobMeta.textContent = `Job: ${currentJobId} (${data.status})`;
  startPolling();
});

async function pollStatus() {
  if (!currentJobId) return;
  const resp = await fetch(`/v1/jobs/${currentJobId}`);
  if (!resp.ok) {
    jobMeta.textContent = "Failed to load status.";
    return;
  }
  const data = await resp.json();
  jobMeta.textContent = `Job: ${data.job_id} | Status: ${data.status}`;
  jobProgress.value = data.progress || 0;
  jobStage.textContent = `Stage: ${data.current_stage} | Alignment: ${JSON.stringify(data.alignment_metrics || {})}`;
  if (["succeeded", "failed"].includes(data.status)) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

function startPolling() {
  if (pollTimer) clearInterval(pollTimer);
  pollStatus();
  pollTimer = setInterval(pollStatus, 3000);
}

document.querySelectorAll("button[data-report]").forEach((btn) => {
  btn.addEventListener("click", async () => {
    if (!currentJobId) {
      alert("Submit a job first.");
      return;
    }
    const reportType = btn.getAttribute("data-report");
    const resp = await fetch(`/v1/jobs/${currentJobId}/reports/${reportType}`);
    if (!resp.ok) {
      reportOutput.textContent = `Report not ready (${reportType}).`;
      return;
    }
    const data = await resp.json();
    reportOutput.textContent = JSON.stringify(data.payload, null, 2);
  });
});
