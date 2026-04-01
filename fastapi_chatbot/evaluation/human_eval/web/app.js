let dataset = [];
let filtered = [];
let ratings = [];
let idx = 0;

const $ = (id) => document.getElementById(id);

function esc(str) {
  return String(str || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function averageFromForm() {
  const names = [
    "legal_correctness",
    "completeness",
    "clarity",
    "source_citation",
    "safe_fallback",
  ];
  const vals = names.map((name) => Number(document.querySelector(`[name=\"${name}\"]`).value || 0));
  if (vals.some((v) => v < 1 || v > 5)) {
    return null;
  }
  const avg = vals.reduce((a, b) => a + b, 0) / vals.length;
  return avg.toFixed(2);
}

function updateLocalScore() {
  const avg = averageFromForm();
  $("localScore").textContent = avg ? `Overall: ${avg}/5` : "Overall: -";
}

function getCurrentRater() {
  return $("raterId").value.trim();
}

function matchFilters(item) {
  const d = $("domainFilter").value;
  const l = $("langFilter").value;
  if (d !== "all" && item.domain !== d) return false;
  if (l !== "all" && item.query_language !== l) return false;
  return true;
}

function applyFilters() {
  filtered = dataset.filter(matchFilters);
  idx = Math.min(idx, Math.max(0, filtered.length - 1));
  render();
}

function findRating(raterId, itemId) {
  return ratings.find((r) => r.rater_id === raterId && r.item_id === itemId) || null;
}

function preloadForm(item) {
  const raterId = getCurrentRater();
  if (!raterId || !item) {
    document.querySelector("#ratingForm").reset();
    updateLocalScore();
    return;
  }

  const hit = findRating(raterId, item.id);
  document.querySelector("#ratingForm").reset();
  if (hit) {
    ["legal_correctness", "completeness", "clarity", "source_citation", "safe_fallback", "notes"].forEach((k) => {
      const el = document.querySelector(`[name=\"${k}\"]`);
      if (el) el.value = hit[k] ?? "";
    });
  }
  updateLocalScore();
}

function render() {
  $("positionLabel").textContent = `${filtered.length ? idx + 1 : 0} / ${filtered.length}`;

  if (!filtered.length) {
    $("itemCard").innerHTML = "<p>No items for current filters.</p>";
    document.querySelector("#ratingForm").style.display = "none";
    return;
  }

  const item = filtered[idx];
  document.querySelector("#ratingForm").style.display = "block";

  $("itemCard").innerHTML = `
    <div class="item-meta">
      <span class="badge">${esc(item.id)}</span>
      <span class="badge">${esc(item.domain)}</span>
      <span class="badge">${esc(item.query_language)}</span>
      <span class="badge">source=${esc(item.chatbot_source || "unknown")}</span>
    </div>
    <div><strong>Title/Topic:</strong> ${esc(item.source_title || "")}</div>
    <div class="question"><strong>Query</strong><br>${esc(item.query || "")}</div>
    <div class="answer"><strong>Chatbot Answer</strong><br>${esc(item.chatbot_answer || "")}</div>
  `;

  preloadForm(item);
}

async function refreshSummary() {
  const res = await fetch("api/summary");
  const data = await res.json();
  const overall = data.overall_average == null ? "-" : `${data.overall_average}/5`;

  let byDomain = "";
  for (const [domain, info] of Object.entries(data.by_domain || {})) {
    byDomain += `<div><strong>${esc(domain)}</strong>: ${info.overall_average}/5 (${info.count} ratings)</div>`;
  }

  $("summaryBox").innerHTML = `
    <div><strong>Total ratings:</strong> ${data.total_ratings || 0}</div>
    <div><strong>Overall average:</strong> ${overall}</div>
    ${byDomain}
  `;
}

async function loadAll() {
  const [dRes, rRes] = await Promise.all([fetch("api/dataset"), fetch("api/ratings")]);
  dataset = await dRes.json();
  ratings = await rRes.json();
  applyFilters();
  await refreshSummary();
}

async function saveCurrentRating(ev) {
  ev.preventDefault();
  const item = filtered[idx];
  if (!item) return;

  const raterId = getCurrentRater();
  if (!raterId) {
    $("statusLine").textContent = "Please enter Researcher ID before saving.";
    return;
  }

  const formData = new FormData(ev.target);
  const payload = {
    rater_id: raterId,
    item_id: item.id,
    legal_correctness: Number(formData.get("legal_correctness")),
    completeness: Number(formData.get("completeness")),
    clarity: Number(formData.get("clarity")),
    source_citation: Number(formData.get("source_citation")),
    safe_fallback: Number(formData.get("safe_fallback")),
    notes: String(formData.get("notes") || ""),
  };

  const res = await fetch("api/ratings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    $("statusLine").textContent = `Failed to save rating (${res.status})`;
    return;
  }

  const result = await res.json();
  $("statusLine").textContent = `Saved. Overall score=${result.overall_score}/5`;

  ratings = await (await fetch("api/ratings")).json();
  await refreshSummary();
}

function wire() {
  $("domainFilter").addEventListener("change", applyFilters);
  $("langFilter").addEventListener("change", applyFilters);
  $("raterId").addEventListener("input", () => preloadForm(filtered[idx]));
  $("prevBtn").addEventListener("click", () => {
    if (!filtered.length) return;
    idx = Math.max(0, idx - 1);
    render();
  });
  $("nextBtn").addEventListener("click", () => {
    if (!filtered.length) return;
    idx = Math.min(filtered.length - 1, idx + 1);
    render();
  });
  $("refreshSummaryBtn").addEventListener("click", refreshSummary);

  [
    "legal_correctness",
    "completeness",
    "clarity",
    "source_citation",
    "safe_fallback",
  ].forEach((k) => {
    document.querySelector(`[name=\"${k}\"]`).addEventListener("input", updateLocalScore);
  });

  $("ratingForm").addEventListener("submit", saveCurrentRating);
}

wire();
loadAll().catch((err) => {
  $("statusLine").textContent = `Initialization error: ${err}`;
});
