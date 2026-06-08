"use strict";

const $ = (sel) => document.querySelector(sel);

const state = {
  images: [],
  selected: new Set(),
};

// --- helpers ---------------------------------------------------------------

function formatBytes(bytes) {
  if (!bytes || bytes < 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  let n = bytes;
  while (n >= 1024 && i < units.length - 1) { n /= 1024; i++; }
  return `${n.toFixed(n >= 10 || i === 0 ? 0 : 1)} ${units[i]}`;
}

function formatAge(seconds) {
  if (seconds == null) return "—";
  const d = Math.floor(seconds / 86400);
  if (d >= 1) return `${d} d`;
  const h = Math.floor(seconds / 3600);
  if (h >= 1) return `${h} h`;
  const m = Math.floor(seconds / 60);
  return `${m} min`;
}

function toast(message, kind = "ok") {
  const el = $("#toast");
  el.textContent = message;
  el.className = `toast ${kind}`;
  setTimeout(() => { el.className = "toast hidden"; }, 3500);
}

async function api(method, url, body) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(url, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || `Błąd ${res.status}`);
  }
  return data;
}

// --- images table ----------------------------------------------------------

function renderImages() {
  const body = $("#images-body");
  body.innerHTML = "";
  if (state.images.length === 0) {
    body.innerHTML = '<tr><td colspan="5" class="empty">Brak nieużywanych obrazów 🎉</td></tr>';
    updateSelectionInfo();
    return;
  }
  for (const img of state.images) {
    const tr = document.createElement("tr");

    const tagsHtml = (img.tags && img.tags.length)
      ? img.tags.map((t) => `<span class="tag">${escapeHtml(t)}</span>`).join("")
      : '<span class="tag none">&lt;none&gt;</span>';

    tr.innerHTML = `
      <td class="col-check"><input type="checkbox" data-id="${img.id}" ${state.selected.has(img.id) ? "checked" : ""}></td>
      <td>${tagsHtml}</td>
      <td class="mono">${escapeHtml(img.short_id || "")}</td>
      <td class="num">${formatBytes(img.size)}</td>
      <td class="num">${formatAge(img.age_seconds)}</td>
    `;
    body.appendChild(tr);
  }

  body.querySelectorAll('input[type="checkbox"]').forEach((cb) => {
    cb.addEventListener("change", () => {
      if (cb.checked) state.selected.add(cb.dataset.id);
      else state.selected.delete(cb.dataset.id);
      updateSelectionInfo();
    });
  });
  updateSelectionInfo();
}

function updateSelectionInfo() {
  const present = new Set(state.images.map((i) => i.id));
  state.selected = new Set([...state.selected].filter((id) => present.has(id)));
  const count = state.selected.size;
  $("#selection-info").textContent = `Zaznaczono: ${count}`;
  $("#delete-selected").disabled = count === 0;
  const all = $("#select-all");
  all.checked = count > 0 && count === state.images.length;
  all.indeterminate = count > 0 && count < state.images.length;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

async function loadImages() {
  const scope = $("#scope").value;
  $("#images-body").innerHTML = '<tr><td colspan="5" class="empty">Ładowanie…</td></tr>';
  try {
    const data = await api("GET", `/api/images?scope=${scope}`);
    state.images = data.images || [];
    renderImages();
  } catch (e) {
    $("#images-body").innerHTML = `<tr><td colspan="5" class="empty">Błąd: ${escapeHtml(e.message)}</td></tr>`;
  }
}

async function deleteSelected() {
  const ids = [...state.selected];
  if (ids.length === 0) return;
  if (!confirm(`Usunąć ${ids.length} obraz(ów)? Tej operacji nie można cofnąć.`)) return;
  try {
    const data = await api("POST", "/api/images/delete", { ids });
    const removed = (data.removed || []).length;
    const errors = (data.errors || []).length;
    if (errors > 0) {
      toast(`Usunięto ${removed}, błędów: ${errors}. Niektóre obrazy mogą być używane.`, "err");
    } else {
      toast(`Usunięto ${removed} obraz(ów).`, "ok");
    }
    state.selected.clear();
    await loadImages();
    await loadStatus();
  } catch (e) {
    toast(`Błąd usuwania: ${e.message}`, "err");
  }
}

// --- settings --------------------------------------------------------------

function toggleScheduleFields() {
  const type = $("#schedule-type").value;
  $("#interval-field").classList.toggle("hidden", type !== "interval");
  $("#cron-field").classList.toggle("hidden", type !== "cron");
}

async function loadSettings() {
  try {
    const s = await api("GET", "/api/settings");
    $("#auto_clean").checked = !!s.auto_clean;
    $("#set-scope").value = s.clean_scope;
    $("#clean_build_cache").checked = !!s.clean_build_cache;
    $("#min_age").value = s.min_age || "";
    $("#clean_interval").value = s.clean_interval || "";
    $("#clean_cron").value = s.clean_cron || "";
    $("#schedule-type").value = s.clean_cron ? "cron" : "interval";
    toggleScheduleFields();
  } catch (e) {
    toast(`Nie udało się wczytać ustawień: ${e.message}`, "err");
  }
}

async function saveSettings(ev) {
  ev.preventDefault();
  const type = $("#schedule-type").value;
  const payload = {
    auto_clean: $("#auto_clean").checked,
    clean_scope: $("#set-scope").value,
    clean_build_cache: $("#clean_build_cache").checked,
    min_age: $("#min_age").value.trim() || "0h",
    clean_interval: $("#clean_interval").value.trim() || "24h",
    clean_cron: type === "cron" ? ($("#clean_cron").value.trim() || null) : null,
  };
  try {
    const data = await api("PUT", "/api/settings", payload);
    $("#settings-msg").textContent = data.next_run
      ? `Zapisano. Następne czyszczenie: ${new Date(data.next_run).toLocaleString()}`
      : "Zapisano. Automatyczne czyszczenie wyłączone.";
    toast("Ustawienia zapisane.", "ok");
    await loadStatus();
  } catch (e) {
    toast(`Błąd zapisu: ${e.message}`, "err");
  }
}

// --- status ----------------------------------------------------------------

async function loadStatus() {
  try {
    const s = await api("GET", "/api/status");
    const parts = [];
    if (s.disk && s.disk.images_reclaimable_bytes != null) {
      parts.push(`Do odzyskania: <strong>${formatBytes(s.disk.images_reclaimable_bytes)}</strong>`);
    }
    if (s.auto_clean && s.next_run) {
      parts.push(`Następne czyszczenie: <strong>${new Date(s.next_run).toLocaleString()}</strong>`);
    } else {
      parts.push("Auto-czyszczenie: <strong>wyłączone</strong>");
    }
    $("#status").innerHTML = parts.join(" &nbsp;•&nbsp; ");
  } catch (e) {
    $("#status").textContent = "";
  }
}

// --- init ------------------------------------------------------------------

function init() {
  $("#refresh").addEventListener("click", loadImages);
  $("#scope").addEventListener("change", loadImages);
  $("#delete-selected").addEventListener("click", deleteSelected);
  $("#select-all").addEventListener("change", (e) => {
    if (e.target.checked) state.images.forEach((i) => state.selected.add(i.id));
    else state.selected.clear();
    renderImages();
  });
  $("#schedule-type").addEventListener("change", toggleScheduleFields);
  $("#settings-form").addEventListener("submit", saveSettings);

  loadImages();
  loadSettings();
  loadStatus();
}

document.addEventListener("DOMContentLoaded", init);
