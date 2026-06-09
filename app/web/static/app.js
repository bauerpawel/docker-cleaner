"use strict";

const $ = (sel) => document.querySelector(sel);

const state = {
  images: [],
  selected: new Set(),
};

// --- i18n ------------------------------------------------------------------

const I18N = {
  en: {
    unused_images: "Unused images",
    scope_label: "Scope:",
    opt_dangling: "dangling (untagged)",
    opt_all: "all unused",
    refresh: "Refresh",
    select_all_title: "Select all",
    th_tags: "Tags",
    th_id: "ID",
    th_size: "Size",
    th_age: "Age",
    delete_selected: "Delete selected",
    auto_cleanup_title: "Automatic cleanup",
    enable_auto_clean: "Enable automatic cleanup",
    clean_scope_label: "Cleanup scope",
    schedule_type_label: "Schedule type",
    opt_interval: "interval",
    opt_cron: "cron",
    interval_label: "Interval (e.g. 24h, 30m, 7d)",
    cron_label: "Cron expression (e.g. 0 3 * * *)",
    min_age_label: "Age threshold (only older than)",
    clean_build_cache_label: "Also prune build cache",
    save_settings: "Save settings",
    loading: "Loading…",
    empty_images: "No unused images 🎉",
    selected: "Selected: {n}",
    delete_confirm: "Delete {n} image(s)? This cannot be undone.",
    deleted_ok: "Removed {n} image(s).",
    deleted_partial: "Removed {removed}, errors: {errors}. Some images may be in use.",
    delete_error: "Delete error: {msg}",
    load_error: "Error: {msg}",
    settings_load_error: "Failed to load settings: {msg}",
    settings_saved_next: "Saved. Next cleanup: {time}",
    settings_saved_off: "Saved. Automatic cleanup disabled.",
    settings_saved_toast: "Settings saved.",
    save_error: "Save error: {msg}",
    status_reclaimable: "Reclaimable: {size}",
    status_next: "Next cleanup: {time}",
    status_auto_off: "Auto-cleanup: disabled",
    err_status: "Error {status}",
  },
  pl: {
    unused_images: "Nieużywane obrazy",
    scope_label: "Zakres:",
    opt_dangling: "dangling (nieotagowane)",
    opt_all: "wszystkie nieużywane",
    refresh: "Odśwież",
    select_all_title: "Zaznacz wszystko",
    th_tags: "Tagi",
    th_id: "ID",
    th_size: "Rozmiar",
    th_age: "Wiek",
    delete_selected: "Usuń zaznaczone",
    auto_cleanup_title: "Automatyczne czyszczenie",
    enable_auto_clean: "Włącz automatyczne czyszczenie",
    clean_scope_label: "Zakres czyszczenia",
    schedule_type_label: "Typ harmonogramu",
    opt_interval: "interwał",
    opt_cron: "cron",
    interval_label: "Interwał (np. 24h, 30m, 7d)",
    cron_label: "Wyrażenie cron (np. 0 3 * * *)",
    min_age_label: "Próg wieku (usuwaj starsze niż)",
    clean_build_cache_label: "Czyść też build cache",
    save_settings: "Zapisz ustawienia",
    loading: "Ładowanie…",
    empty_images: "Brak nieużywanych obrazów 🎉",
    selected: "Zaznaczono: {n}",
    delete_confirm: "Usunąć {n} obraz(ów)? Tej operacji nie można cofnąć.",
    deleted_ok: "Usunięto {n} obraz(ów).",
    deleted_partial: "Usunięto {removed}, błędów: {errors}. Niektóre obrazy mogą być używane.",
    delete_error: "Błąd usuwania: {msg}",
    load_error: "Błąd: {msg}",
    settings_load_error: "Nie udało się wczytać ustawień: {msg}",
    settings_saved_next: "Zapisano. Następne czyszczenie: {time}",
    settings_saved_off: "Zapisano. Automatyczne czyszczenie wyłączone.",
    settings_saved_toast: "Ustawienia zapisane.",
    save_error: "Błąd zapisu: {msg}",
    status_reclaimable: "Do odzyskania: {size}",
    status_next: "Następne czyszczenie: {time}",
    status_auto_off: "Auto-czyszczenie: wyłączone",
    err_status: "Błąd {status}",
  },
};

function detectLang() {
  const stored = localStorage.getItem("lang");
  if (stored === "en" || stored === "pl") return stored;
  const nav = (navigator.language || "en").toLowerCase();
  return nav.startsWith("pl") ? "pl" : "en";
}

let lang = detectLang();

function t(key, vars) {
  let s = (I18N[lang] && I18N[lang][key]) || (I18N.en[key] || key);
  if (vars) {
    for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, v);
  }
  return s;
}

function applyI18n() {
  document.documentElement.lang = lang;
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    el.textContent = t(el.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-title]").forEach((el) => {
    el.title = t(el.dataset.i18nTitle);
  });
  document.querySelectorAll(".lang-btn").forEach((b) => {
    b.classList.toggle("active", b.dataset.lang === lang);
  });
}

function setLang(next) {
  if (next === lang) return;
  lang = next;
  localStorage.setItem("lang", lang);
  applyI18n();
  // Odśwież elementy generowane dynamicznie w bieżącym języku.
  renderImages();
  loadStatus();
  $("#settings-msg").textContent = "";
}

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
    throw new Error(data.detail || t("err_status", { status: res.status }));
  }
  return data;
}

// --- images table ----------------------------------------------------------

function renderImages() {
  const body = $("#images-body");
  body.innerHTML = "";
  if (state.images.length === 0) {
    body.innerHTML = `<tr><td colspan="5" class="empty">${escapeHtml(t("empty_images"))}</td></tr>`;
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
  $("#selection-info").textContent = t("selected", { n: count });
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
  $("#images-body").innerHTML = `<tr><td colspan="5" class="empty">${escapeHtml(t("loading"))}</td></tr>`;
  try {
    const data = await api("GET", `/api/images?scope=${scope}`);
    state.images = data.images || [];
    renderImages();
  } catch (e) {
    $("#images-body").innerHTML = `<tr><td colspan="5" class="empty">${escapeHtml(t("load_error", { msg: e.message }))}</td></tr>`;
  }
}

async function deleteSelected() {
  const ids = [...state.selected];
  if (ids.length === 0) return;
  if (!confirm(t("delete_confirm", { n: ids.length }))) return;
  try {
    const data = await api("POST", "/api/images/delete", { ids });
    const removed = (data.removed || []).length;
    const errors = (data.errors || []).length;
    if (errors > 0) {
      toast(t("deleted_partial", { removed, errors }), "err");
    } else {
      toast(t("deleted_ok", { n: removed }), "ok");
    }
    state.selected.clear();
    await loadImages();
    await loadStatus();
  } catch (e) {
    toast(t("delete_error", { msg: e.message }), "err");
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
    toast(t("settings_load_error", { msg: e.message }), "err");
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
      ? t("settings_saved_next", { time: new Date(data.next_run).toLocaleString() })
      : t("settings_saved_off");
    toast(t("settings_saved_toast"), "ok");
    await loadStatus();
  } catch (e) {
    toast(t("save_error", { msg: e.message }), "err");
  }
}

// --- status ----------------------------------------------------------------

async function loadStatus() {
  try {
    const s = await api("GET", "/api/status");
    const parts = [];
    if (s.disk && s.disk.images_reclaimable_bytes != null) {
      parts.push(t("status_reclaimable", { size: `<strong>${formatBytes(s.disk.images_reclaimable_bytes)}</strong>` }));
    }
    if (s.auto_clean && s.next_run) {
      parts.push(t("status_next", { time: `<strong>${new Date(s.next_run).toLocaleString()}</strong>` }));
    } else {
      parts.push(t("status_auto_off"));
    }
    $("#status").innerHTML = parts.join(" &nbsp;•&nbsp; ");
  } catch (e) {
    $("#status").textContent = "";
  }
}

// --- init ------------------------------------------------------------------

function init() {
  applyI18n();

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
  document.querySelectorAll(".lang-btn").forEach((b) => {
    b.addEventListener("click", () => setLang(b.dataset.lang));
  });

  updateSelectionInfo();
  loadImages();
  loadSettings();
  loadStatus();
}

document.addEventListener("DOMContentLoaded", init);
