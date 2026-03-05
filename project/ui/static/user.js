let currentJobId = null;
let pollTimer = null;

const PROVIDERS = ["openai", "zhipu", "claude"];
const QUALITY_MODES = ["fast", "balanced", "high_quality"];

const uploadForm = document.getElementById("upload-form");
const jobMeta = document.getElementById("job-meta");
const jobProgress = document.getElementById("job-progress");
const jobStage = document.getElementById("job-stage");
const reportOutput = document.getElementById("report-output");
const formFeedback = document.getElementById("form-feedback");

const userProfileRaw = document.getElementById("user-profile");
const providerPolicyRaw = document.getElementById("provider-policy");

const researchSlider = document.getElementById("research-slider");
const researchNumber = document.getElementById("research-number");
const openDataSlider = document.getElementById("open-data-slider");
const openDataNumber = document.getElementById("open-data-number");
const recentDataSlider = document.getElementById("recent-data-slider");
const recentDataNumber = document.getElementById("recent-data-number");
const qualityMode = document.getElementById("quality-mode");

const venueInput = document.getElementById("venue-input");
const venueAdd = document.getElementById("venue-add");
const venueList = document.getElementById("venue-list");
const domainInput = document.getElementById("domain-input");
const domainAdd = document.getElementById("domain-add");
const domainList = document.getElementById("domain-list");

const providerPrimary = document.getElementById("provider-primary");
const fallbackProviderSelect = document.getElementById("fallback-provider-select");
const fallbackAdd = document.getElementById("fallback-add");
const fallbackList = document.getElementById("fallback-list");
const forceSingleProvider = document.getElementById("force-single-provider");

const applyUserJsonBtn = document.getElementById("apply-user-json");
const applyPolicyJsonBtn = document.getElementById("apply-policy-json");

const state = {
  preferredVenues: [],
  domainFocus: [],
  fallbackOrder: ["openai", "zhipu", "claude"],
};

function setFeedback(message, level = "ok") {
  formFeedback.textContent = message || "";
  formFeedback.classList.remove("ok", "error");
  if (message) {
    formFeedback.classList.add(level === "error" ? "error" : "ok");
  }
}

function clamp01(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) {
    return 0;
  }
  return Math.max(0, Math.min(1, num));
}

function uniqueClean(list) {
  const seen = new Set();
  const output = [];
  (list || []).forEach((item) => {
    const normalized = String(item || "").trim();
    if (!normalized) return;
    const key = normalized.toLowerCase();
    if (seen.has(key)) return;
    seen.add(key);
    output.push(normalized);
  });
  return output;
}

function renderChips(container, items, onRemove) {
  container.innerHTML = "";
  if (!items.length) {
    const empty = document.createElement("small");
    empty.className = "meta-soft";
    empty.textContent = "Empty";
    container.appendChild(empty);
    return;
  }
  items.forEach((item, index) => {
    const chip = document.createElement("span");
    chip.className = "chip";
    const text = document.createElement("span");
    text.textContent = item;
    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "×";
    remove.setAttribute("aria-label", `Remove ${item}`);
    remove.addEventListener("click", () => onRemove(index));
    chip.appendChild(text);
    chip.appendChild(remove);
    container.appendChild(chip);
  });
}

function syncRangePair(slider, numberInput) {
  slider.addEventListener("input", () => {
    numberInput.value = slider.value;
    updateRawFromStructured();
  });
  numberInput.addEventListener("input", () => {
    const val = clamp01(numberInput.value);
    numberInput.value = val.toFixed(2);
    slider.value = val.toFixed(2);
    updateRawFromStructured();
  });
}

function addTextItem(inputNode, targetList, renderFn) {
  const value = String(inputNode.value || "").trim();
  if (!value) return;
  targetList.push(value);
  const dedup = uniqueClean(targetList);
  targetList.splice(0, targetList.length, ...dedup);
  inputNode.value = "";
  renderFn();
  updateRawFromStructured();
}

function addFallback(provider) {
  const clean = String(provider || "").trim().toLowerCase();
  if (!PROVIDERS.includes(clean)) {
    setFeedback(`Unsupported provider: ${provider}`, "error");
    return;
  }
  state.fallbackOrder.push(clean);
  state.fallbackOrder = uniqueClean(state.fallbackOrder);
  ensurePrimaryInFallback();
  renderFallback();
  updateRawFromStructured();
}

function ensurePrimaryInFallback() {
  const primary = String(providerPrimary.value || "").trim().toLowerCase();
  if (!primary) return;
  state.fallbackOrder = uniqueClean(state.fallbackOrder);
  const current = state.fallbackOrder.filter((item) => item !== primary);
  state.fallbackOrder = [primary, ...current];
}

function renderPreferredVenues() {
  renderChips(venueList, state.preferredVenues, (idx) => {
    state.preferredVenues.splice(idx, 1);
    renderPreferredVenues();
    updateRawFromStructured();
  });
}

function renderDomainFocus() {
  renderChips(domainList, state.domainFocus, (idx) => {
    state.domainFocus.splice(idx, 1);
    renderDomainFocus();
    updateRawFromStructured();
  });
}

function renderFallback() {
  renderChips(fallbackList, state.fallbackOrder, (idx) => {
    state.fallbackOrder.splice(idx, 1);
    ensurePrimaryInFallback();
    renderFallback();
    updateRawFromStructured();
  });
}

function buildUserProfile() {
  return {
    research_vs_production: clamp01(researchNumber.value),
    prefer_open_data: clamp01(openDataNumber.value),
    prefer_recent_data: clamp01(recentDataNumber.value),
    quality_mode: qualityMode.value,
    preferred_venues: uniqueClean(state.preferredVenues),
    domain_focus: uniqueClean(state.domainFocus),
  };
}

function buildProviderPolicy() {
  ensurePrimaryInFallback();
  return {
    primary_provider: providerPrimary.value,
    fallback_order: uniqueClean(state.fallbackOrder),
    force_single_provider: Boolean(forceSingleProvider.checked),
  };
}

function updateRawFromStructured() {
  const userProfile = buildUserProfile();
  const providerPolicy = buildProviderPolicy();
  userProfileRaw.value = JSON.stringify(userProfile, null, 2);
  providerPolicyRaw.value = JSON.stringify(providerPolicy, null, 2);
}

function isValidFloat01(value) {
  const num = Number(value);
  return Number.isFinite(num) && num >= 0 && num <= 1;
}

function validatePayload(profile, policy) {
  const errors = [];

  if (!isValidFloat01(profile.research_vs_production)) {
    errors.push("research_vs_production must be in [0, 1].");
  }
  if (!isValidFloat01(profile.prefer_open_data)) {
    errors.push("prefer_open_data must be in [0, 1].");
  }
  if (!isValidFloat01(profile.prefer_recent_data)) {
    errors.push("prefer_recent_data must be in [0, 1].");
  }
  if (!QUALITY_MODES.includes(String(profile.quality_mode || ""))) {
    errors.push("quality_mode must be one of fast/balanced/high_quality.");
  }
  if (!Array.isArray(profile.preferred_venues) || !Array.isArray(profile.domain_focus)) {
    errors.push("preferred_venues and domain_focus must be arrays.");
  }

  if (!PROVIDERS.includes(String(policy.primary_provider || ""))) {
    errors.push("primary_provider must be one of openai/zhipu/claude.");
  }
  if (!Array.isArray(policy.fallback_order) || policy.fallback_order.length === 0) {
    errors.push("fallback_order must be a non-empty array.");
  } else {
    const normalized = policy.fallback_order.map((item) => String(item || "").toLowerCase());
    const unique = new Set(normalized);
    if (unique.size !== normalized.length) {
      errors.push("fallback_order contains duplicated providers.");
    }
    if (!normalized.every((item) => PROVIDERS.includes(item))) {
      errors.push("fallback_order contains unsupported provider.");
    }
    if (normalized[0] !== String(policy.primary_provider || "").toLowerCase()) {
      errors.push("fallback_order[0] must equal primary_provider.");
    }
  }

  return errors;
}

function applyUserProfileRaw() {
  try {
    const data = JSON.parse(userProfileRaw.value || "{}");
    if (typeof data !== "object" || data === null || Array.isArray(data)) {
      throw new Error("User Profile JSON must be an object");
    }
    researchNumber.value = clamp01(data.research_vs_production ?? 0.5).toFixed(2);
    researchSlider.value = researchNumber.value;
    openDataNumber.value = clamp01(data.prefer_open_data ?? 0.8).toFixed(2);
    openDataSlider.value = openDataNumber.value;
    recentDataNumber.value = clamp01(data.prefer_recent_data ?? 0.7).toFixed(2);
    recentDataSlider.value = recentDataNumber.value;

    const mode = String(data.quality_mode || "balanced");
    qualityMode.value = QUALITY_MODES.includes(mode) ? mode : "balanced";

    state.preferredVenues = uniqueClean(Array.isArray(data.preferred_venues) ? data.preferred_venues : []);
    state.domainFocus = uniqueClean(Array.isArray(data.domain_focus) ? data.domain_focus : []);
    renderPreferredVenues();
    renderDomainFocus();
    updateRawFromStructured();
    setFeedback("User Profile JSON applied successfully.", "ok");
  } catch (error) {
    setFeedback(`Invalid User Profile JSON: ${error.message}`, "error");
  }
}

function applyProviderPolicyRaw() {
  try {
    const data = JSON.parse(providerPolicyRaw.value || "{}");
    if (typeof data !== "object" || data === null || Array.isArray(data)) {
      throw new Error("Provider Policy JSON must be an object");
    }

    const primary = String(data.primary_provider || "openai").toLowerCase();
    providerPrimary.value = PROVIDERS.includes(primary) ? primary : "openai";

    const fallback = Array.isArray(data.fallback_order) ? data.fallback_order : [providerPrimary.value];
    state.fallbackOrder = uniqueClean(fallback.map((item) => String(item || "").toLowerCase()));
    ensurePrimaryInFallback();
    renderFallback();

    forceSingleProvider.checked = Boolean(data.force_single_provider);
    updateRawFromStructured();
    setFeedback("Provider Policy JSON applied successfully.", "ok");
  } catch (error) {
    setFeedback(`Invalid Provider Policy JSON: ${error.message}`, "error");
  }
}

uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  setFeedback("");

  const fileInput = document.getElementById("paper-file");
  if (!fileInput.files.length) {
    setFeedback("Please choose a PDF file.", "error");
    return;
  }

  updateRawFromStructured();

  let profile;
  let policy;
  try {
    profile = JSON.parse(userProfileRaw.value || "{}");
    policy = JSON.parse(providerPolicyRaw.value || "{}");
  } catch (error) {
    setFeedback(`JSON parse error: ${error.message}`, "error");
    return;
  }

  const errors = validatePayload(profile, policy);
  if (errors.length) {
    setFeedback(`Validation failed: ${errors.join(" ")}`, "error");
    return;
  }

  const formData = new FormData();
  formData.append("file", fileInput.files[0]);
  formData.append("user_profile", JSON.stringify(profile));
  formData.append("provider_policy", JSON.stringify(policy));

  const submitBtn = uploadForm.querySelector("button[type='submit']");
  submitBtn.setAttribute("aria-busy", "true");

  try {
    const resp = await fetch("/v1/jobs", { method: "POST", body: formData });
    if (!resp.ok) {
      const txt = await resp.text();
      setFeedback(`Job submit failed: ${txt}`, "error");
      return;
    }

    const data = await resp.json();
    currentJobId = data.job_id;
    reportOutput.textContent = "No report loaded.";
    jobMeta.textContent = `Job: ${currentJobId} (${data.status})`;
    setFeedback("Job submitted successfully.", "ok");
    startPolling();
  } catch (error) {
    setFeedback(`Network error: ${error.message}`, "error");
  } finally {
    submitBtn.removeAttribute("aria-busy");
  }
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
      setFeedback("Submit a job first.", "error");
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

venueAdd.addEventListener("click", () => addTextItem(venueInput, state.preferredVenues, renderPreferredVenues));
domainAdd.addEventListener("click", () => addTextItem(domainInput, state.domainFocus, renderDomainFocus));
fallbackAdd.addEventListener("click", () => addFallback(fallbackProviderSelect.value));
providerPrimary.addEventListener("change", () => {
  ensurePrimaryInFallback();
  renderFallback();
  updateRawFromStructured();
});

applyUserJsonBtn.addEventListener("click", applyUserProfileRaw);
applyPolicyJsonBtn.addEventListener("click", applyProviderPolicyRaw);

syncRangePair(researchSlider, researchNumber);
syncRangePair(openDataSlider, openDataNumber);
syncRangePair(recentDataSlider, recentDataNumber);
qualityMode.addEventListener("change", updateRawFromStructured);
forceSingleProvider.addEventListener("change", updateRawFromStructured);

applyUserProfileRaw();
applyProviderPolicyRaw();
updateRawFromStructured();
