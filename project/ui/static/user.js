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
const forceSingleNote = document.getElementById("force-single-note");

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
  if (!message) return;
  formFeedback.classList.add(level === "error" ? "error" : "ok");
}

function clamp01(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) return 0;
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

function renderChips(container, items, onRemove, removeEnabled = true) {
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
    chip.appendChild(text);

    if (removeEnabled) {
      const remove = document.createElement("button");
      remove.type = "button";
      remove.textContent = "×";
      remove.setAttribute("aria-label", `Remove ${item}`);
      remove.addEventListener("click", () => onRemove(index));
      chip.appendChild(remove);
    }

    container.appendChild(chip);
  });
}

function normalizeProvider(value) {
  return String(value || "").trim().toLowerCase();
}

function ensurePrimaryInFallback() {
  const primary = normalizeProvider(providerPrimary.value);
  if (!primary) return;

  state.fallbackOrder = uniqueClean(state.fallbackOrder).map(normalizeProvider).filter((x) => PROVIDERS.includes(x));
  const withoutPrimary = state.fallbackOrder.filter((item) => item !== primary);
  state.fallbackOrder = [primary, ...withoutPrimary];
}

function setForceSingleMode(enabled) {
  if (enabled) {
    const primary = normalizeProvider(providerPrimary.value) || "openai";
    state.fallbackOrder = [primary];
    fallbackProviderSelect.disabled = true;
    fallbackAdd.disabled = true;
    fallbackList.classList.add("is-disabled");
    forceSingleNote.textContent = "Force single provider enabled: only the primary provider will be used.";
  } else {
    fallbackProviderSelect.disabled = false;
    fallbackAdd.disabled = false;
    fallbackList.classList.remove("is-disabled");
    forceSingleNote.textContent = "";
    ensurePrimaryInFallback();
  }
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
  renderChips(
    fallbackList,
    state.fallbackOrder,
    (idx) => {
      if (forceSingleProvider.checked) return;
      state.fallbackOrder.splice(idx, 1);
      if (!state.fallbackOrder.length) {
        state.fallbackOrder = [normalizeProvider(providerPrimary.value) || "openai"];
      }
      ensurePrimaryInFallback();
      renderFallback();
      updateRawFromStructured();
    },
    !forceSingleProvider.checked
  );
}

function addTextItem(inputNode, targetList, renderFn) {
  const value = String(inputNode.value || "").trim();
  if (!value) return;
  targetList.push(value);
  targetList.splice(0, targetList.length, ...uniqueClean(targetList));
  inputNode.value = "";
  renderFn();
  updateRawFromStructured();
}

function addFallbackFromSelection() {
  if (forceSingleProvider.checked) {
    setFeedback("Force single provider is enabled. Disable it before adding fallback providers.", "error");
    return;
  }

  const selected = Array.from(fallbackProviderSelect.selectedOptions).map((opt) => normalizeProvider(opt.value));
  const uniqueSelected = uniqueClean(selected);

  if (!uniqueSelected.length) {
    setFeedback("Select one or more providers to add.", "error");
    return;
  }

  state.fallbackOrder.push(...uniqueSelected);
  state.fallbackOrder = uniqueClean(state.fallbackOrder).map(normalizeProvider).filter((x) => PROVIDERS.includes(x));
  ensurePrimaryInFallback();
  renderFallback();
  updateRawFromStructured();
  setFeedback("Fallback providers updated.", "ok");
}

function syncRangePair(slider, numberInput) {
  slider.addEventListener("input", () => {
    numberInput.value = slider.value;
    updateRawFromStructured();
  });

  numberInput.addEventListener("input", () => {
    if (numberInput.value === "") return;
    const val = clamp01(numberInput.value);
    slider.value = String(val);
    updateRawFromStructured();
  });

  numberInput.addEventListener("blur", () => {
    const val = clamp01(numberInput.value);
    numberInput.value = val.toFixed(2);
    slider.value = numberInput.value;
    updateRawFromStructured();
  });
}

function buildUserProfile() {
  return {
    research_vs_production: Number(clamp01(researchNumber.value).toFixed(2)),
    prefer_open_data: Number(clamp01(openDataNumber.value).toFixed(2)),
    prefer_recent_data: Number(clamp01(recentDataNumber.value).toFixed(2)),
    quality_mode: qualityMode.value,
    preferred_venues: uniqueClean(state.preferredVenues),
    domain_focus: uniqueClean(state.domainFocus),
  };
}

function buildProviderPolicy() {
  const primary = normalizeProvider(providerPrimary.value) || "openai";
  ensurePrimaryInFallback();

  let fallbackOrder = uniqueClean(state.fallbackOrder)
    .map(normalizeProvider)
    .filter((x) => PROVIDERS.includes(x));

  if (forceSingleProvider.checked) {
    fallbackOrder = [primary];
  }

  if (!fallbackOrder.length) {
    fallbackOrder = [primary];
  }

  if (fallbackOrder[0] !== primary) {
    fallbackOrder = [primary, ...fallbackOrder.filter((p) => p !== primary)];
  }

  state.fallbackOrder = fallbackOrder;

  return {
    primary_provider: primary,
    fallback_order: fallbackOrder,
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

  const primaryProvider = normalizeProvider(policy.primary_provider);
  if (!PROVIDERS.includes(primaryProvider)) {
    errors.push("primary_provider must be one of openai/zhipu/claude.");
  }

  if (!Array.isArray(policy.fallback_order) || policy.fallback_order.length === 0) {
    errors.push("fallback_order must be a non-empty array.");
  } else {
    const normalized = policy.fallback_order.map((item) => normalizeProvider(item));
    const unique = new Set(normalized);
    if (unique.size !== normalized.length) {
      errors.push("fallback_order contains duplicated providers.");
    }
    if (!normalized.every((item) => PROVIDERS.includes(item))) {
      errors.push("fallback_order contains unsupported provider.");
    }
    if (normalized[0] !== primaryProvider) {
      errors.push("fallback_order[0] must equal primary_provider.");
    }
    if (policy.force_single_provider && (normalized.length !== 1 || normalized[0] !== primaryProvider)) {
      errors.push("force_single_provider=true requires fallback_order=[primary_provider].");
    }
  }

  return errors;
}

function applyUserProfileRaw(options = {}) {
  const { silent = false } = options;
  try {
    const data = JSON.parse(userProfileRaw.value || "{}");
    if (typeof data !== "object" || data === null || Array.isArray(data)) {
      throw new Error("User Profile JSON must be an object");
    }

    researchNumber.value = Number(clamp01(data.research_vs_production ?? 0.5)).toFixed(2);
    researchSlider.value = researchNumber.value;

    openDataNumber.value = Number(clamp01(data.prefer_open_data ?? 0.8)).toFixed(2);
    openDataSlider.value = openDataNumber.value;

    recentDataNumber.value = Number(clamp01(data.prefer_recent_data ?? 0.7)).toFixed(2);
    recentDataSlider.value = recentDataNumber.value;

    const mode = String(data.quality_mode || "balanced");
    qualityMode.value = QUALITY_MODES.includes(mode) ? mode : "balanced";

    state.preferredVenues = uniqueClean(Array.isArray(data.preferred_venues) ? data.preferred_venues : []);
    state.domainFocus = uniqueClean(Array.isArray(data.domain_focus) ? data.domain_focus : []);

    renderPreferredVenues();
    renderDomainFocus();
    updateRawFromStructured();

    if (!silent) setFeedback("User Profile JSON applied successfully.", "ok");
    return true;
  } catch (error) {
    if (!silent) setFeedback(`Invalid User Profile JSON: ${error.message}`, "error");
    return false;
  }
}

function applyProviderPolicyRaw(options = {}) {
  const { silent = false } = options;
  try {
    const data = JSON.parse(providerPolicyRaw.value || "{}");
    if (typeof data !== "object" || data === null || Array.isArray(data)) {
      throw new Error("Provider Policy JSON must be an object");
    }

    const primary = normalizeProvider(data.primary_provider || "openai");
    providerPrimary.value = PROVIDERS.includes(primary) ? primary : "openai";

    const fallbackRaw = Array.isArray(data.fallback_order) ? data.fallback_order : [providerPrimary.value];
    state.fallbackOrder = uniqueClean(fallbackRaw)
      .map(normalizeProvider)
      .filter((item) => PROVIDERS.includes(item));

    forceSingleProvider.checked = Boolean(data.force_single_provider);
    ensurePrimaryInFallback();
    setForceSingleMode(forceSingleProvider.checked);
    renderFallback();
    updateRawFromStructured();

    if (!silent) setFeedback("Provider Policy JSON applied successfully.", "ok");
    return true;
  } catch (error) {
    if (!silent) setFeedback(`Invalid Provider Policy JSON: ${error.message}`, "error");
    return false;
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

venueInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    addTextItem(venueInput, state.preferredVenues, renderPreferredVenues);
  }
});

domainInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    addTextItem(domainInput, state.domainFocus, renderDomainFocus);
  }
});

fallbackAdd.addEventListener("click", addFallbackFromSelection);

providerPrimary.addEventListener("change", () => {
  if (forceSingleProvider.checked) {
    state.fallbackOrder = [normalizeProvider(providerPrimary.value)];
  } else {
    ensurePrimaryInFallback();
  }
  renderFallback();
  updateRawFromStructured();
});

forceSingleProvider.addEventListener("change", () => {
  setForceSingleMode(forceSingleProvider.checked);
  renderFallback();
  updateRawFromStructured();
});

applyUserJsonBtn.addEventListener("click", () => applyUserProfileRaw());
applyPolicyJsonBtn.addEventListener("click", () => applyProviderPolicyRaw());

userProfileRaw.addEventListener("change", () => applyUserProfileRaw({ silent: true }));
userProfileRaw.addEventListener("blur", () => applyUserProfileRaw({ silent: true }));
providerPolicyRaw.addEventListener("change", () => applyProviderPolicyRaw({ silent: true }));
providerPolicyRaw.addEventListener("blur", () => applyProviderPolicyRaw({ silent: true }));

syncRangePair(researchSlider, researchNumber);
syncRangePair(openDataSlider, openDataNumber);
syncRangePair(recentDataSlider, recentDataNumber);
qualityMode.addEventListener("change", updateRawFromStructured);

applyUserProfileRaw({ silent: true });
applyProviderPolicyRaw({ silent: true });
setForceSingleMode(forceSingleProvider.checked);
renderFallback();
updateRawFromStructured();
