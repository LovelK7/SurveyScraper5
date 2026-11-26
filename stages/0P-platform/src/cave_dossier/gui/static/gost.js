// Gost – the guest page (/gost): 3N for a survey that is not in SB.
// The server side is gui/gost.py; this file only draws it.
"use strict";

const TOKEN = window.CD_TOKEN;
const G = { page: null, id: null, project: null, jobs: new Map(), active: null, polling: false,
  view: "koraci",        // or "mapiranje": the main page's Mapiranje (mapping.js) for this project
  sheets: {},            // KORAK 3a menu per _postp (path + mtime) -> {data} | {error} | {loading}
  layout: {},            // the sheet picked per _postp path
};

const KIND_LABEL = {
  raw: "sirovi .csx", prep: "_prep", postp: "_postp", resolved: "_postp_resolved", backup: "backup",
  plan: "tlocrt", profile: "profil", dimenzije: "dimenzije", nacrt: "NACRT", podaci: "podaci", mapiranje: "tema/mapiranje",
  zip: "TopoDroid zip", photo: "slika", pdf: "pdf", other: "",
};
const SURVEY = new Set(["raw", "prep", "postp", "resolved", "backup"]);
// A step is done when the file it produces exists.
const PRODUCES = { k1: ["prep"], k2: ["postp"], k3a: ["resolved"], k3b: ["plan", "profile", "dimenzije"], k3c: ["nacrt"] };
const FILE_KINDS = { raw: ["raw"], prep: ["prep"], postp: ["postp"], resolved: ["resolved"] };

const $ = s => document.querySelector(s);
const hrDash = t => String(t ?? "").replace(/—/g, "–");
function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "class") el.className = v;
    else if (k === "value") el.value = v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat()) {
    if (kid === null || kid === undefined || kid === false) continue;
    el.append(kid instanceof Node ? kid : document.createTextNode(hrDash(kid)));
  }
  return el;
}
const fmtTime = ts => ts ? new Date(ts * 1000).toLocaleString("hr-HR", {
  day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }) : "";
const fileName = p => (p || "").split(/[\\/]/).pop();

let toastTimer;
function toast(text, err) {
  const t = $("#toast");
  t.textContent = hrDash(text);
  t.className = "toast show" + (err ? " err" : "");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.className = "toast"; }, err ? 6000 : 3000);
}

async function api(path, body) {
  const opts = { headers: { "X-Token": TOKEN } };
  if (body !== undefined) {
    opts.method = "POST";
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch("/api/" + path, opts);
  let data = {};
  try { data = await res.json(); } catch (_) {}
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
}

// ── what mapping.js (the main page's Mapiranje) expects from its page ─
// The main page keys a cave by Redni broj; here S.broj is the project id and
// MAP_TARGET sends the mapping calls to the project folder (gui/gost.py).
const S = { get broj() { return G.id; }, get cave() { return G.project; } };
window.MAP_TARGET = {
  url: (key, reset) => `gost-mapping?id=${encodeURIComponent(key)}${reset ? "&reset=1" : ""}`,
  label: key => `projekt „${key}”`,
};
const SVG_NS = "http://www.w3.org/2000/svg";
function icon(name, cls) {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("class", "ico" + (cls ? " " + cls : ""));
  svg.setAttribute("aria-hidden", "true");
  const use = document.createElementNS(SVG_NS, "use");
  use.setAttribute("href", "#i-" + name);
  svg.append(use);
  return svg;
}
const fold = t => String(t || "").normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();
async function copy(text) {
  try { await navigator.clipboard.writeText(text); toast("Kopirano."); }
  catch (_) { toast("Kopiranje nije uspjelo.", true); }
}
// The help texts are help.js's; here a "?" shows them as a tooltip and a toast.
function helpBtn(key) {
  const e = (typeof HELP !== "undefined" ? HELP : {})[key];
  if (!e) return null;
  const text = e.t + (e.d ? " – " + e.d : "");
  return h("button", { class: "qhelp", type: "button", title: text, "aria-label": "Pomoć: " + e.t,
    onclick: ev => { ev.preventDefault(); toast(text); } }, "?");
}
async function openTarget(body) {
  try { await api("gost-open", { id: G.id, path: body.path, reveal: !!body.reveal, csurvey: body.what === "csurvey" }); }
  catch (e) { toast(e.message, true); }
}
// mapping.js links to "3N" (back to the steps) and to the repo docs (main page).
function setTab(tab) {
  if (tab === "3N") { G.view = "koraci"; render(); window.scrollTo(0, 0); return; }
  localSet("cd.tab", tab);
  window.open("/", "_blank");
}

// ── loading ──────────────────────────────────────────────────────────
async function loadPage(selectId) {
  G.page = await api("gost");
  $("#root").textContent = G.page.root;
  const sel = $("#project");
  const projects = G.page.projects;
  sel.replaceChildren(
    h("option", { value: "" }, projects.length ? "— odaberi projekt —" : "— još nema projekata —"),
    ...projects.map(p => h("option", { value: p.id }, p.name + (p.name !== p.id ? ` (${p.id})` : ""))));
  let id = selectId || G.id || localGet("gost.project");
  if (!projects.some(p => p.id === id)) id = projects[0]?.id || null;
  sel.value = id || "";
  await selectProject(id);
  // /gost#mapiranje opens straight on the project's Mapiranje
  if (location.hash === "#mapiranje" && G.project) { G.view = "mapiranje"; render(); }
}

async function selectProject(id) {
  G.id = id || null;
  localSet("gost.project", G.id || "");
  $("#btn-folder").disabled = !G.id;
  G.view = "koraci";
  if (!G.id) { G.project = null; render(); return; }
  try { G.project = await api("gost-project?id=" + encodeURIComponent(G.id)); }
  catch (e) { G.project = null; toast(e.message, true); }
  render();
}

async function reloadProject() {
  if (!G.id) return;
  try { G.project = await api("gost-project?id=" + encodeURIComponent(G.id)); render(); }
  catch (e) { toast(e.message, true); }
}

function localGet(k) { try { return localStorage.getItem(k); } catch (_) { return null; } }
function localSet(k, v) { try { localStorage.setItem(k, v); } catch (_) {} }

// ── drawing ──────────────────────────────────────────────────────────
function render() {
  const view = $("#project-view");
  const p = G.project;
  if (!p) {
    view.replaceChildren(h("section", { class: "card" },
      h("p", { class: "muted", style: "margin:0" }, "Odaberi projekt gore desno ili napravi novi.")));
    return;
  }
  if (G.view === "mapiranje") {
    view.replaceChildren(h("div", { class: "row", style: "margin-bottom:10px" },
      h("button", { class: "btn", onclick: () => setTab("3N") }, "← Natrag na korake"),
      h("span", { class: "muted" }, `Mapiranje za projekt „${p.id}” – sprema se u njegovu mapu.`)),
      ...renderMapping());
    return;
  }
  view.replaceChildren(filesCard(p), dataCard(p), stepsCard(p));
}

function filesCard(p) {
  const input = h("input", { type: "file", multiple: true, hidden: true,
    accept: ".csx,.csz,.zip,.png,.jpg,.jpeg", onchange: e => uploadAll(e.target.files) });
  const drop = h("div", { class: "drop", onclick: () => input.click() },
    "Ispusti ovdje TopoDroid izvoz (.csx) – ili klikni za odabir. ",
    h("span", { class: "muted" }, "Logo udruge za sastavnicu: logo.png ili logo.jpg."));
  drop.addEventListener("dragover", e => { e.preventDefault(); drop.classList.add("over"); });
  drop.addEventListener("dragleave", () => drop.classList.remove("over"));
  drop.addEventListener("drop", e => { e.preventDefault(); drop.classList.remove("over"); uploadAll(e.dataTransfer.files); });

  const rows = p.files.map(f => h("tr", {},
    h("td", { class: "name" }, f.name),
    h("td", { class: "kind" }, KIND_LABEL[f.kind] ?? f.kind),
    h("td", { class: "kind" }, fmtTime(f.modified)),
    h("td", { class: "act" },
      SURVEY.has(f.kind) ? h("button", { class: "btn small", onclick: () => openFile(f.path, true) }, "cSurvey") : null, " ",
      h("button", { class: "btn small ghost", onclick: () => openFile(f.path) }, "Otvori"))));
  return h("section", { class: "card" },
    h("h2", {}, h("span", { class: "num" }, "1"), "Datoteke"),
    drop, input,
    rows.length ? h("table", { class: "files" }, h("tbody", {}, rows))
                : h("p", { class: "muted" }, "Mapa je prazna."),
    p.logo ? h("p", { class: "muted" }, "Logo udruge pronađen – ide na sastavnicu umjesto loga arhive.")
           : h("p", { class: "muted" }, "Bez logo.png/jpg polje loga na sastavnici ostaje prazno."));
}

function dataCard(p) {
  const inputs = {};
  const fields = G.page.fields.map(f => {
    const measured = p.measured[f.key];
    const inp = h("input", { type: "text", value: p.data[f.key] || "",
      class: measured ? "measured" : null,
      placeholder: measured ? `iz izmjere: ${measured}` : f.hint });
    inputs[f.key] = inp;
    return h("label", { class: "field" }, h("span", {}, f.label), inp);
  });
  const form = h("form", { onsubmit: async e => {
    e.preventDefault();
    const data = {};
    for (const [k, inp] of Object.entries(inputs)) data[k] = inp.value;
    try {
      G.project = await api("gost-save", { id: G.id, data });
      toast("Podaci spremljeni.");
      render();
    } catch (err) { toast(err.message, true); }
  } }, h("div", { class: "form-grid" }, fields),
    h("div", { class: "row", style: "margin-top:8px" },
      h("button", { class: "btn primary" }, "Spremi podatke"),
      h("span", { class: "muted" }, "Prazno polje: izmjera (duljine, dubina, mjerilo), HTRS (lokacija, visina) ili „?” na sastavnici.")));
  return h("section", { class: "card" },
    h("h2", {}, h("span", { class: "num" }, "2"), "Podaci za sastavnicu"), form);
}

function stepsCard(p) {
  const have = new Set(p.files.map(f => f.kind));
  const steps = G.page.steps.map(s => {
    const done = PRODUCES[s.id] && PRODUCES[s.id].every(k => have.has(k));
    const files = s.kind ? p.files.filter(f => (FILE_KINDS[s.kind] || []).includes(f.kind))
      .sort((a, b) => b.modified - a.modified) : [];
    const pick = files.length > 1 ? h("select", {}, files.map(f => h("option", { value: f.path }, f.name))) : null;
    const chosen = () => pick ? pick.value : files[0]?.path;
    let body, layoutInput = null;
    if (pick) pick.addEventListener("change", () => { if (s.layout) render(); });
    if (s.manual) {
      body = h("div", {}, h("div", { class: "title" }, s.title), h("div", { class: "muted" }, s.help),
        files.length ? h("div", { class: "row", style: "margin-top:6px" }, pick,
          h("button", { class: "btn small", onclick: () => openFile(chosen(), true) }, "Otvori u cSurveyu")) : null);
    } else {
      const layout = s.layout ? h("input", { type: "number", min: 1, style: "width:70px", placeholder: "1",
        value: G.layout[chosen()] || "", oninput: e => { G.layout[chosen()] = e.target.value; markSheets(); } }) : null;
      layoutInput = layout;
      const missing = s.kind && !files.length;
      body = h("div", {},
        h("div", { class: "title" }, s.title),
        s.help ? h("div", { class: "muted" }, s.help) : null,
        h("div", { class: "row", style: "margin-top:6px" },
          pick || (files[0] ? h("span", { class: "mono muted" }, files[0].name) : null),
          layout ? h("label", { class: "opt-inline" }, "Raspored br.", layout) : null,
          s.layout ? h("button", { class: "btn small", disabled: missing,
            onclick: () => runStep(s, chosen(), layout.value, true) }, "Pokaži rasporede") : null,
          h("button", { class: "btn small primary", disabled: missing,
            onclick: () => runStep(s, chosen(), layout && layout.value, false) },
            "Pokreni"),
          missing ? h("span", { class: "muted" }, "čeka prethodni korak") : null));
    }
    if (s.id === "k1") body.append(h("div", { class: "row", style: "margin-top:8px" },
      h("button", { class: "btn small", onclick: () => { G.view = "mapiranje"; render(); window.scrollTo(0, 0); } },
        "Mapiranje simbola…"),
      h("span", { class: "muted" }, "TopoDroid → cSurvey: znakovi, linije, površine i poligon, samo za ovaj projekt.")));
    if (s.id === "k2") { const tp = themePicker(); if (tp) body.append(tp); }   // mapping.js
    if (s.layout && files.length) body.append(sheetPicker(chosen(), layoutInput));
    return h("div", { class: "gost-step" + (done ? " done" : "") + (s.manual ? " manual" : "") },
      h("div", { class: "tag" }, s.step, done ? " ✓" : ""), body);
  });
  const nacrt = p.files.find(f => f.kind === "nacrt");
  return h("section", { class: "card" },
    h("h2", {}, h("span", { class: "num" }, "3"), "Koraci"),
    h("div", {}, steps),
    nacrt ? h("div", { class: "row", style: "margin-top:10px" },
      h("button", { class: "btn primary", onclick: () => openFile(nacrt.path) }, "Otvori nacrt: " + nacrt.name)) : null);
}

// KORAK 3a: the layout menu nacrt_finish.py would print, drawn as A4 sheets
// like on the main page (GET gost-layouts runs it with --layouts-json, writing
// nothing). A click puts the sheet's number into "Raspored br.".
function svgEl(tag, attrs) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  return node;
}
function markSheets() {
  for (const tile of document.querySelectorAll(".sheets .sheet")) {
    const file = tile.closest(".sheets").dataset.file;
    tile.classList.toggle("on", Number(tile.dataset.n) === (Number(G.layout[file]) || 1));
  }
}
function sheetPicker(file, input) {
  const f = G.project.files.find(x => x.path === file);
  const key = file + "|" + (f ? f.modified : "");
  const el = h("div", { class: "sheets", "data-file": file });
  const state = G.sheets[key];
  if (!state) {
    G.sheets[key] = { loading: true };
    api(`gost-layouts?id=${encodeURIComponent(G.id)}&path=${encodeURIComponent(file)}`)
      .then(data => { G.sheets[key] = { data }; }, e => { G.sheets[key] = { error: e.message }; })
      .then(() => { if (G.view === "koraci") render(); });
  }
  if (!state || state.loading) { el.append(h("p", { class: "help" }, "Računam rasporede…")); return el; }
  if (state.error) { el.append(h("p", { class: "warnline" }, "Raspored: " + state.error)); return el; }
  const data = state.data;
  const pick = n => { G.layout[file] = String(n); if (input) input.value = n; markSheets(); };
  const design = (svg, name, box) => {
    const d = data.designs[name];
    svg.append(svgEl("rect", { class: "sheet-box", x: box.x, y: box.y, width: box.width, height: box.height }));
    if (d && d.size_m[0] > 0 && d.size_m[1] > 0) {
      const sx = box.width / d.size_m[0], sy = box.height / d.size_m[1];
      for (const line of d.lines) {
        svg.append(svgEl("polyline", { class: "sheet-wall",
          points: line.map(([x, y]) => `${(box.x + x * sx).toFixed(1)},${(box.y + y * sy).toFixed(1)}`).join(" ") }));
      }
    }
    const label = svgEl("text", { class: "sheet-label", x: box.x + 2, y: box.y + 9 });
    label.textContent = `${name === "plan" ? "tlocrt" : "profil"} 1:${box.scale}`;
    svg.append(label);
  };
  const tile = l => {
    const [w, hgt] = data.page_mm, t = data.title_block_mm;
    const svg = svgEl("svg", { viewBox: `0 0 ${w} ${hgt}`, class: "sheet-page", role: "img",
      "aria-label": `Raspored ${l.n}: ${l.note}` });
    svg.append(svgEl("rect", { class: "sheet-paper", x: 0, y: 0, width: w, height: hgt }));
    svg.append(svgEl("rect", { class: "sheet-block", x: t.x, y: t.y, width: t.width, height: t.height }));
    design(svg, "profile", l.profile);
    design(svg, "plan", l.plan);
    return h("button", { class: "sheet", type: "button", "data-n": l.n, title: l.note, onclick: () => pick(l.n) },
      svg, h("span", { class: "sheet-cap" }, h("b", {}, `${l.n})`), ` ${l.mjerilo}`,
        l.proposal ? h("span", { class: "sheet-tag" }, "prijedlog") : null));
  };
  const head = h("div", { class: "sheets-head" }, h("span", {}, "Raspored na stranici"),
    h("span", { class: "muted" }, "klikni list – broj ide u „Raspored br.”"));
  if (!data.layouts.length) {
    el.append(head, h("p", { class: "warnline" }, `Ništa ne stane ni u 1:500 (${data.no_fit_reason}) – ispis ide na „fit to page”.`));
    return el;
  }
  // start from the proposal, so the run takes the highlighted sheet
  if (!G.layout[file]) { G.layout[file] = "1"; if (input) input.value = 1; }
  el.append(head, h("div", { class: "sheet-row" }, ...data.layouts.map(tile)));
  if (data.warnings.length) el.append(h("ul", { class: "sheet-warn" }, ...data.warnings.map(w => h("li", {}, w))));
  requestAnimationFrame(markSheets);
  return el;
}

// ── actions ──────────────────────────────────────────────────────────
async function uploadAll(files) {
  for (const file of files) {
    try {
      const res = await fetch(`/api/gost-upload?id=${encodeURIComponent(G.id)}&name=${encodeURIComponent(file.name)}`,
        { method: "POST", headers: { "X-Token": TOKEN }, body: file });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || res.statusText);
      G.project = data;
      toast(`${file.name} dodan.`);
    } catch (e) { toast(`${file.name}: ${e.message}`, true); }
  }
  render();
}

async function openFile(path, csurvey) {
  try { await api("gost-open", { id: G.id, path, csurvey: !!csurvey }); }
  catch (e) { toast(e.message, true); }
}

async function runStep(s, file, layout, dryRun) {
  try {
    const job = await api("gost-run", { id: G.id, step: s.id, file, layout: layout || "", dry_run: !!dryRun });
    G.jobs.set(job.id, job);
    G.active = job.id;
    $("#console").classList.remove("collapsed");
    $("#console-arrow").textContent = "▾";
    renderJobs();
    poll();
  } catch (e) { toast(e.message, true); }
}

async function poll() {
  if (G.polling) return;
  G.polling = true;
  try {
    while ([...G.jobs.values()].some(j => j.running)) {
      for (const j of G.jobs.values()) {
        if (!j.running) continue;
        try {
          const upd = await api(`job/${j.id}?since=${j.offset}`);
          j.text += upd.text; j.offset = upd.offset;
          const finished = !upd.running;
          Object.assign(j, { running: upd.running, returncode: upd.returncode });
          if (finished) {
            toast(`${j.title}: ${j.returncode === 0 ? "gotovo" : "završilo s kodom " + j.returncode}`, j.returncode !== 0);
            reloadProject();
          }
        } catch (_) { j.running = false; }
      }
      renderJobs();
      await new Promise(r => setTimeout(r, 400));
    }
  } finally { G.polling = false; }
}

function renderJobs() {
  const list = [...G.jobs.values()].sort((a, b) => b.id - a.id);
  $("#job-tabs").replaceChildren(...list.map(j => h("button", {
    class: "job-tab" + (j.id === G.active ? " active" : ""),
    onclick: () => { G.active = j.id; renderJobs(); },
  }, h("span", { class: "st" }, j.running ? "●" : j.returncode === 0 ? "✓" : "✗"), `#${j.id} ${j.title}`)));
  const j = G.jobs.get(G.active);
  const out = $("#job-output");
  out.textContent = j ? hrDash(j.text) : "Još ništa nije pokrenuto.";
  out.scrollTop = out.scrollHeight;
  $("#job-kill").disabled = !(j && j.running);
  $("#job-input").disabled = !(j && j.running);
}

// ── wiring ───────────────────────────────────────────────────────────
$("#project").addEventListener("change", e => selectProject(e.target.value));
$("#btn-folder").addEventListener("click", () => G.id && openFile(G.project?.path));
$("#new-form").addEventListener("submit", async e => {
  e.preventDefault();
  const name = $("#new-name").value.trim();
  if (!name) { toast("Upiši ime objekta.", true); return; }
  try {
    const p = await api("gost-new", { name });
    $("#new-name").value = "";
    toast(`Projekt „${p.id}” napravljen – ispusti u njega .csx.`);
    await loadPage(p.id);
  } catch (err) { toast(err.message, true); }
});
$("#console-toggle").addEventListener("click", () => {
  const c = $("#console");
  c.classList.toggle("collapsed");
  $("#console-arrow").textContent = c.classList.contains("collapsed") ? "▸" : "▾";
});
$("#job-kill").addEventListener("click", async () => {
  if (G.active) try { await api(`job/${G.active}/kill`, {}); } catch (e) { toast(e.message, true); }
});
$("#job-input-form").addEventListener("submit", async e => {
  e.preventDefault();
  const inp = $("#job-input");
  try { await api(`job/${G.active}/input`, { line: inp.value }); inp.value = ""; }
  catch (err) { toast(err.message, true); }
});
// The server stops itself when no page has pinged for a while (prod launcher).
setInterval(() => api("ping", {}).catch(() => {}), 60000);

// mapping.js loads after this file; start once everything is in.
window.addEventListener("load", () => loadPage().catch(e => toast(e.message, true)));
