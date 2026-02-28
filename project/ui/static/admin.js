const totalNode = document.getElementById("m-total");
const doneNode = document.getElementById("m-done");
const failedNode = document.getElementById("m-failed");
const jobsOutput = document.getElementById("jobs-output");
const eventsOutput = document.getElementById("events-output");

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
  }
  if (eResp.ok) {
    const e = await eResp.json();
    eventsOutput.textContent = JSON.stringify(e.events, null, 2);
  }
}

refresh();
setInterval(refresh, 5000);
