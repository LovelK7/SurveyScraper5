// Speleo nadzorna ploča — the page. Everything it can run comes from
// /api/catalog, and each cave's workflow comes from /api/cave/<broj>
// (gui/workflow.py). This file only knows how to draw them.
"use strict";

const TOKEN = window.CD_TOKEN;
const S = {
  summary: null, catalog: null, caves: [], unprefixed: [], queue: {},
  docs: {}, lastStage: null,  // docs: path -> {text} | {error} | {loading}
  sbIndex: null,              // {rows, error} | {loading} — every SB row, for the picker
  menuIdx: -1,
  broj: null, cave: null, tab: "home",
  dossier: null,              // {broj, data, error, loading}
  jobs: new Map(), activeJob: null, remember: new Set(), polling: false,
};

// Which intake-leaf file kinds a catalog `file_kind` accepts (mirrors state.FILE_KINDS).
const FILE_KINDS = {
  raw: ["raw"], pp: ["pp"], lt: ["lt"], fin: ["fin"], survey: ["raw", "pp", "lt", "fin"],
};
const SURVEY_KINDS = new Set(["raw", "pp", "lt", "fin", "backup"]);
const PHOTO_KINDS = new Set(["photo", "photo_processed"]);

// Files each stage tab lists for the current cave (4F draws a gallery instead).
const STAGE_FILES = {
  "3N": ["raw", "pp", "lt", "fin", "plan", "profile", "dimenzije", "nacrt"],
  "4O": ["osz", "doc"],
  "4S": ["sastavnica"],
};

const KIND_LABEL = {
  raw: "sirovi", pp: "_pp", lt: "_lt", fin: "_lt_fin", backup: "backup",
  plan: "tlocrt", profile: "profil", dimenzije: "dimenzije", nacrt: "NACRT",
  sastavnica: "sastavnica", osz: "OSZ", doc: "dokument", photo: "foto",
  photo_processed: "foto SB_", pdf: "pdf", other: "",
};

const STAGE_ICON = {
  home: "home", fast: "star", map3n: "nacrt", "1T": "teren", "2B": "baza", "3N": "nacrt", "4G": "geo", "4I": "karta",
  "4O": "osz", "4F": "foto", "4S": "sastavnica", "5O": "osobe", "5D": "dosje", "6P": "predaja",
};
const DIR_ICON = {
  intake_dir: "inbox", osz_dir: "osz", drawings_dir: "nacrt", statements_dir: "izjava",
  entry_photos_dir: "foto", queued_photos_dir: "foto-red", map_excerpts_dir: "karta",
  runs: "terminal", "sb-sync": "sync",
};
const STATUS = {
  done: { icon: "check", label: "gotovo" },
  stale: { icon: "clock", label: "zastarjelo" },
  todo: { icon: "dot", label: "za napraviti" },
  blocked: { icon: "lock", label: "čeka prethodni korak" },
  optional: { icon: "dot", label: "po potrebi" },
  unknown: { icon: "dot", label: "provjeri" },
  planned: { icon: "dot", label: "planirano" },
};

// ── tiny DOM helpers ─────────────────────────────────────────────────
function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "class") el.className = v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat()) {
    if (kid === null || kid === undefined || kid === false) continue;
    el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  }
  return el;
}
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
const $ = sel => document.querySelector(sel);

function store(key, value) {
  try { value === null ? localStorage.removeItem(key) : localStorage.setItem(key, value); } catch (_) {}
}
function recall(key) {
  try { return localStorage.getItem(key); } catch (_) { return null; }
}

function toast(msg, isErr) {
  const t = $("#toast");
  t.textContent = msg;
  t.className = "toast show" + (isErr ? " err" : "");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => { t.className = "toast"; }, isErr ? 6000 : 2600);
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
  if (!res.ok) {
    const err = new Error(data.error || res.statusText);
    err.status = res.status;
    throw err;
  }
  return data;
}

async function openTarget(body) {
  try { await api("open", body); } catch (e) { toast(e.message, true); }
}

const fmtTime = ts => ts ? new Date(ts * 1000).toLocaleString("hr-HR", {
  day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "";
const fmtSize = n => n > 1048576 ? (n / 1048576).toFixed(1) + " MB" : Math.max(1, Math.round(n / 1024)) + " kB";
const shortName = s => (s || "").split("_")[0];
const fileName = p => (p || "").split(/[\\/]/).pop();

// ── loading ──────────────────────────────────────────────────────────
async function loadAll(refresh) {
  if (refresh) await api("refresh", {});
  const [summary, catalog, caves] = await Promise.all([
    api("state"), S.catalog ? Promise.resolve(S.catalog) : api("catalog"),
    api("caves" + (refresh ? "?refresh=1" : "")),
  ]);
  S.summary = summary; S.catalog = catalog;
  S.caves = caves.caves; S.unprefixed = caves.unprefixed; S.queue = caves.queue || {};
  if (refresh) { S.dossier = null; S.sbIndex = null; }
  renderTopbar();
  renderNav();
  if (S.broj !== null) await loadCave(); else render();
}

async function loadCave() {
  if (S.broj === null) { S.cave = null; render(); return; }
  try {
    S.cave = await api("cave/" + S.broj);
  } catch (e) {
    S.cave = null; toast(e.message, true);
  }
  render();
}

async function loadDossier(force) {
  if (S.broj === null) return;
  if (!force && S.dossier && S.dossier.broj === S.broj && (S.dossier.data || S.dossier.loading)) return;
  const broj = S.broj;
  S.dossier = { broj, loading: true };
  render();
  try {
    const data = await api("dossier/" + broj);
    if (S.broj === broj) S.dossier = { broj, data };
  } catch (e) {
    if (S.broj === broj) S.dossier = { broj, error: e.message };
  }
  render();
}

function setCave(broj) {
  S.broj = broj;
  S.dossier = null;
  store("cd.broj", broj === null ? null : String(broj));
  $("#cave-input").value = caveLabel(broj);
  loadCave();
}

// ── cave picker: folders in work first, then every other SB row ──────
const fold = t => String(t || "").normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();
function sbRow(broj) {
  return S.sbIndex && S.sbIndex.rows ? S.sbIndex.rows.find(r => r.broj === broj) : null;
}
// The SB name wins over the folder name: folders carry extra words
// ("Platak-Hrđava špilja_Flavio" for SB's "Hrđava špilja").
function caveName(broj) {
  const row = sbRow(broj);
  if (row && row.name) return row.name;
  const info = S.caves.find(c => c.broj === broj);
  return info ? shortName(info.name) : "";
}
function caveLabel(broj) {
  if (broj === null || broj === undefined) return "";
  const info = S.caves.find(c => c.broj === broj);
  if (info) return `${broj} · ${info.name}`;
  const row = sbRow(broj);
  return row ? `${broj} · ${row.name} (nema mapu)` : String(broj);
}
function isDup(broj) {
  return !!(S.sbIndex && S.sbIndex.duplicates && S.sbIndex.duplicates[String(broj)]);
}
function loadSbIndex() {
  if (S.sbIndex) return;
  S.sbIndex = { loading: true };
  api("sb-index").then(d => { S.sbIndex = d; }).catch(e => { S.sbIndex = { rows: [], error: e.message }; })
    .finally(() => {
      if (S.tab === "home") render();
      if (!$("#cave-menu").hidden) renderMenu();
      if (S.broj !== null && document.activeElement !== $("#cave-input")) $("#cave-input").value = caveLabel(S.broj);
    });
}

function menuItems(query) {
  const q = fold(query.trim());
  const hit = (broj, ...texts) => !q || String(broj).startsWith(q) || texts.some(t => fold(t).includes(q));
  const folders = S.caves.filter(c => hit(c.broj, c.name, c.relative));
  const inFolder = new Set(S.caves.map(c => c.broj));
  let others = [];
  if (S.sbIndex && S.sbIndex.rows && q) {
    others = S.sbIndex.rows.filter(r => !inFolder.has(r.broj) && hit(r.broj, r.name, r.syn, r.sue)).slice(0, 60);
  }
  return { folders, others };
}

function renderMenu() {
  const input = $("#cave-input");
  const menu = $("#cave-menu");
  const query = input.dataset.typed === "1" ? input.value : "";
  const { folders, others } = menuItems(query);
  const items = [];
  const option = (broj, name, extra) => {
    const el = h("div", { class: "opt", role: "option", "data-broj": broj,
      onmousedown: e => { e.preventDefault(); pickCave(broj); } },
      h("span", { class: "opt-n" }, broj), h("span", { class: "opt-name" }, name), ...extra);
    items.push(el);
    return el;
  };
  const kids = [h("div", { class: "opt-group" }, `U radu – imaju mapu (${folders.length})`),
    ...folders.map(c => option(c.broj, c.name, [
      isDup(c.broj) ? h("span", { class: "chip dupchip", title: "Više SB redova nosi ovaj broj" }, "⚠ dvostruki broj") : null,
      S.queue[c.broj] ? h("span", { class: "chip" }, `📷 ${S.queue[c.broj]}`) : null,
      c.group ? h("span", { class: "opt-grp" }, c.group) : null]))];
  if (!folders.length) kids.push(h("div", { class: "opt-empty" }, "Nijedna mapa ne odgovara."));
  kids.push(h("div", { class: "opt-group" }, "Ostali objekti u SB-u – nemaju mapu"));
  if (!S.sbIndex || S.sbIndex.loading) kids.push(h("div", { class: "opt-empty" }, "Učitavam SB…"));
  else if (S.sbIndex.error) kids.push(h("div", { class: "opt-empty" }, S.sbIndex.error));
  else if (!query.trim()) kids.push(h("div", { class: "opt-empty" }, `Upiši ime, sinonim, SUE ili Redni broj za pretragu ${S.sbIndex.rows.length} objekata u SB-u.`));
  else if (!others.length) kids.push(h("div", { class: "opt-empty" }, "Ništa u SB-u ne odgovara."));
  else kids.push(...others.map(r => option(r.broj, r.name || "(bez imena)", [
    r.syn ? h("span", { class: "opt-grp" }, r.syn) : null,
    isDup(r.broj) ? h("span", { class: "chip dupchip", title: "Više SB redova nosi ovaj broj" }, "⚠ dvostruki broj") : null,
    S.queue[r.broj] ? h("span", { class: "chip" }, `📷 ${S.queue[r.broj]}`) : null,
    h("span", { class: "chip" }, "nema mape")])));
  menu.replaceChildren(...kids);
  S.menuItems = items;
  S.menuIdx = Math.min(S.menuIdx, items.length - 1);
  items.forEach((el, i) => el.classList.toggle("active", i === S.menuIdx));
}

function openMenu() {
  const menu = $("#cave-menu");
  loadSbIndex();
  S.menuIdx = -1;
  menu.hidden = false;
  $("#cave-input").setAttribute("aria-expanded", "true");
  renderMenu();
}
function closeMenu() {
  $("#cave-menu").hidden = true;
  $("#cave-input").setAttribute("aria-expanded", "false");
  $("#cave-input").dataset.typed = "";
}
function pickCave(broj) {
  closeMenu();
  $("#cave-input").blur();
  if (broj !== S.broj) setCave(broj); else $("#cave-input").value = caveLabel(broj);
}

function setTab(tab) {
  if (S.catalog && S.catalog.stages.some(s => s.label === tab)) S.lastStage = tab;
  S.tab = tab;
  store("cd.tab", tab);
  renderNav();
  render();
  $("#main").scrollTop = 0;
}

// ── top bar + nav ────────────────────────────────────────────────────
function renderTopbar() {
  const sb = S.summary.sb;
  const badge = $("#sb-mode");
  if (!sb) {
    badge.textContent = "SB nije podešen"; badge.className = "badge sandbox";
  } else {
    badge.textContent = "SB " + sb.mode;
    badge.className = "badge " + sb.mode.toLowerCase();
    badge.title = sb.reason ? sb.reason + "\n" + sb.reading : sb.reading;
  }
  $("#btn-open-sb").disabled = !(sb && sb.live_exists);

}

function renderNav() {
  const item = (id, label, title, status, sub) => h("button", {
    class: "nav-item" + (S.tab === id ? " active" : "") + (sub ? " sub" : ""), onclick: () => setTab(id), title: label ? `${label} · ${title}` : title,
  }, icon(STAGE_ICON[id] || "dot"), title,
     label ? h("span", { class: "nav-label", style: status ? "" : "margin-left:auto" }, label) : null,
     status ? h("span", { class: "dot " + status, title: status, style: "margin-left:6px" }) : null);
  const kids = [item("home", "", "Pregled"), item("fast", "", "Brze radnje")];
  let group = null;
  for (const s of (S.catalog ? S.catalog.stages : [])) {
    if (s.group !== group) { group = s.group; kids.push(h("div", { class: "nav-group" }, group)); }
    kids.push(item(s.label, s.label, s.title, s.status));
    // the mapping page is a sub-page of 3N: listed only while 3N or it is open
    if (s.label === "3N" && (S.tab === "3N" || S.tab === "map3n")) kids.push(item("map3n", "3N", "Mapiranje simbola", null, true));
  }
  kids.push(h("div", { class: "nav-group" }, "Dokumentacija"));
  const docItem = (path, title) => h("button", {
    class: "nav-item" + (S.tab === "doc:" + path ? " active" : ""), title: path, onclick: () => setTab("doc:" + path),
  }, icon("book"), title);
  const stage = currentStage();
  if (stage) kids.push(docItem(stage.readme, `README – ${stage.label} ${stage.title}`));
  for (const [path, title] of DOCS) kids.push(docItem(path, title));
  $("#nav").replaceChildren(...kids);
}

// Project docs the sidebar offers beside the current stage's README.
const DOCS = [
  ["prod/README.md", "Upute (prod)"],
  ["ARCHITECTURE.md", "Arhitektura cjevovoda"],
  ["STATUS.md", "Stanje razvoja"],
  ["docs/commands.md", "Sve naredbe"],
  ["docs/design-decisions.md", "Odluke"],
];

// The stage the README entry follows: the open stage tab, the stage whose
// README is open in the viewer, or the last stage visited.
function currentStage() {
  if (!S.catalog) return null;
  const byTab = S.catalog.stages.find(s => s.label === S.tab);
  if (byTab) return byTab;
  if (S.tab.startsWith("doc:")) {
    const byDoc = S.catalog.stages.find(s => s.readme === S.tab.slice(4));
    if (byDoc) return byDoc;
  }
  return S.catalog.stages.find(s => s.label === S.lastStage) || null;
}

// ── page ─────────────────────────────────────────────────────────────
function render() {
  const main = $("#main");
  if (!S.summary || !S.catalog) { main.replaceChildren(h("div", { class: "empty" }, "Učitavam…")); return; }
  if (S.tab === "home") return main.replaceChildren(...renderHome());
  if (S.tab === "fast") return main.replaceChildren(...renderFast());
  if (S.tab.startsWith("doc:")) return main.replaceChildren(...renderDoc(S.tab.slice(4)));
  if (S.tab === "map3n") return main.replaceChildren(...renderMapping());  // mapping.js
  const stage = S.catalog.stages.find(s => s.label === S.tab);
  if (!stage) return setTab("home");
  main.replaceChildren(...renderStage(stage));
}

function caveInfo() { return S.caves.find(c => c.broj === S.broj); }
function wfStep(id) {
  return S.cave && S.cave.workflow ? S.cave.workflow.steps.find(s => s.id === id) : null;
}

function renderHome() {
  const sum = S.summary;
  const out = [h("div", { class: "page-head" },
    h("div", {}, h("h1", {}, "Pregled"),
      h("div", { class: "sub" }, "Trenutni objekt i njegov tijek rada, Speleo baza, mape na Driveu.")))];
  if (sum.settings_error) out.push(h("div", { class: "card note" }, h("b", {}, "Postavke se ne mogu učitati: "), sum.settings_error));

  const dups = S.sbIndex && S.sbIndex.duplicates ? Object.entries(S.sbIndex.duplicates) : [];
  if (dups.length) {
    out.push(h("div", { class: "card dup", style: "margin-bottom:14px" },
      h("h2", {}, icon("baza", "lg"), `Redni broj nije jedinstven – ${dups.length}`),
      h("p", { class: "help" }, "Ove brojeve nosi više SB redova. Broj je identitet objekta (mapa SB_<broj>_, datoteke, sve naredbe), pa se dva objekta stapaju u jedan. Ispravi u SB-u; dotad intake map i intake create odbijaju te brojeve."),
      h("table", { class: "files" }, ...dups.map(([b, names]) => h("tr", {},
        h("td", { class: "kind" }, b), h("td", { class: "name" }, names.join(" · "))))),
      h("div", { class: "row", style: "margin-top:8px" },
        h("button", { class: "btn primary", onclick: () => openTarget({ what: "sb" }) }, icon("sb"), "Otvori SB u Excelu"))));
  }
  out.push(renderCaveCard());

  const grid = h("div", { class: "grid", style: "margin-top:14px" });
  out.push(grid);
  const sbc = sbCard();
  if (sbc) grid.append(sbc);

  if (sum.drive_dirs) {
    const dirBtn = (ico, label, title, disabled, onclick) => h("button", { class: "dirbtn", title, disabled, onclick },
      h("span", { class: "ico-wrap" }, icon(ico, "lg")), h("span", {}, label));
    grid.append(h("div", { class: "card" },
      h("h2", {}, icon("drive", "lg"), "Mape na Driveu"),
      sum.drive_ok ? null : h("div", { class: "errline" }, "Drive nije dostupan: " + (sum.drive_root || "LOCAL_DRIVE_ROOT nije postavljen")),
      h("div", { class: "dirgrid" },
        dirBtn("drive", "Speleo baza SUE", sum.drive_root || "", !sum.drive_ok, () => openTarget({ what: "drive-root" })),
        ...sum.drive_dirs.map(d => dirBtn(DIR_ICON[d.key] || "folder", d.label, d.path || "", !d.exists,
          () => openTarget({ what: "drive", key: d.key })))),
      h("h3", { style: "margin:14px 0 8px" }, "Radni prostor"),
      h("div", { class: "dirgrid" },
        ...sum.workspace_dirs.map(d => dirBtn(DIR_ICON[d.key] || "folder", d.label, d.path || "", false,
          () => openTarget({ what: "workspace", key: d.key })))),
    ));
  }

  grid.append(h("div", { class: "card" },
    h("h2", {}, icon("terminal", "lg"), "Ovo računalo"),
    h("dl", { class: "kv" },
      h("dt", {}, "Radni prostor"), h("dd", { class: "mono" }, sum.workspace || "–"),
      h("dt", {}, "Drive"), h("dd", { class: "mono" }, sum.drive_root || "–"),
      h("dt", {}, "3N alati"), h("dd", { class: "mono" }, sum.tools_dir || h("span", { class: "warnline" }, "nisu pronađeni")),
      h("dt", {}, "cSurvey"), h("dd", { class: "mono" }, sum.csurvey || h("span", { class: "warnline" }, "nije pronađen (CSURVEY_DIR, Drive, C:\\csurvey64)"))),
  ));

  const queued = Object.entries(S.queue).map(([b, n]) => [parseInt(b, 10), n]).sort((a, b) => a[0] - b[0]);
  if (queued.length) {
    grid.append(h("div", { class: "card hl" },
      h("h2", {}, icon("foto-red", "lg"), `Fotografije u redu čekanja (${queued.reduce((t, q) => t + q[1], 0)})`),
      h("p", { class: "help" }, "Fotografije u !!Fotografije ulaza za istražit koje već nose SB_<broj>_. Odaberi objekt i povuci ih u njegovu mapu (4F)."),
      h("table", { class: "files" }, ...queued.map(([b, n]) => {
        const info = S.caves.find(c => c.broj === b);
        return h("tr", {},
          h("td", { class: "kind" }, String(b)),
          h("td", { class: "name" }, info ? info.name : h("span", { class: "muted" }, "nema mape – povlačenje je napravi")),
          h("td", { class: "kind" }, `📷 ${n}`),
          h("td", { class: "act" }, h("button", { class: "btn small", onclick: () => { setCave(b); setTab("4F"); } }, "Otvori", icon("arrow"))));
      }))));
  }

  if (S.unprefixed.length) {
    grid.append(h("div", { class: "card" },
      h("h2", {}, icon("inbox", "lg"), `Mape bez SB_ prefiksa (${S.unprefixed.length})`),
      h("p", { class: "help" }, "Ove mape pod !Za digitalizirat još nisu povezane sa SB redom, pa ih birač objekata ne vidi."),
      h("ul", { class: "muted" }, ...S.unprefixed.slice(0, 8).map(p => h("li", {}, p))),
      h("button", { class: "btn", onclick: () => setTab("1T") }, "Poveži u 1T", icon("arrow")),
    ));
  }
  return out;
}

function sbCard() {
  const sb = S.summary.sb;
  if (!sb) return null;
  const live = sb.versions.find(v => v.path === sb.live) || null;
  return h("div", { class: "card hl" },
    h("h2", {}, icon("baza", "lg"), "Speleo baza"),
    h("dl", { class: "kv" },
      h("dt", {}, "Živa"), h("dd", {}, sb.live ? fileName(sb.live) : "–"),
      h("dt", {}, "Izmijenjena"), h("dd", {}, live ? fmtTime(live.modified) : "–"),
      h("dt", {}, "Alati čitaju"), h("dd", {}, h("span", { class: "badge " + sb.mode.toLowerCase() }, sb.mode), " ", fileName(sb.reading))),
    sb.reason ? h("div", { class: "warnline" }, "⚠ " + sb.reason + " – čita se zadnja dobra lokalna kopija.") : null,
    sb.newer_than_live.length ? h("div", { class: "warnline" },
      "⚠ Na Driveu postoji novija verzija nego što config.yaml koristi: " + sb.newer_than_live.join(", ") + " – ažuriraj sb.workbook_filename.") : null,
    h("div", { class: "row" },
      h("button", { class: "btn primary", disabled: !sb.live_exists, onclick: () => openTarget({ what: "sb" }) }, icon("sb"), "Otvori SB u Excelu"),
      h("button", { class: "btn", onclick: () => openTarget({ what: "sb", reveal: true }), disabled: !sb.live_exists }, icon("folder"), "Pokaži u mapi"),
      sb.reading !== sb.live ? h("button", { class: "btn ghost", onclick: () => openTarget({ what: "sb-reading" }) }, "Otvori kopiju koju alati čitaju") : null),
    h("p", { class: "help" }, "Dok je SB otvoren u Excelu, alati čitaju lokalnu kopiju (FALLBACK). Zatvori Excel prije pokretanja naredbi ako trebaš najsvježije podatke."),
    sb.versions.length > 1 ? h("details", {}, h("summary", { class: "muted" }, `Sve verzije (${sb.versions.length})`),
      h("table", { class: "files" }, ...sb.versions.map(v => h("tr", {},
        h("td", { class: "name" }, v.name), h("td", { class: "kind" }, fmtTime(v.modified)),
        h("td", { class: "act" }, h("button", { class: "btn small", onclick: () => openTarget({ what: "path", path: v.path }) }, "Otvori")))))) : null,
  );
}

// ── the cave workflow (Pregled) ──────────────────────────────────────
function renderCaveCard() {
  if (S.broj === null) {
    return h("div", { class: "card hl" }, h("h2", {}, icon("home", "lg"), "Trenutni objekt"),
      h("p", { class: "help" }, "Odaberi objekt gore desno (Redni broj ili ime). Ovdje se tada vidi cijeli tijek rada za taj objekt – što je gotovo, što je zastarjelo i što je sljedeće – a sve naredbe na karticama koriste taj broj."),
      h("p", { class: "muted" }, `${S.caves.length} objekata ima mapu SB_<broj>_… pod !Za digitalizirat.`));
  }
  const d = S.cave;
  const info = caveInfo();
  const card = h("div", { class: "card hl wide" });
  const head = h("div", { class: "page-head", style: "margin-bottom:6px" },
    h("div", {}, h("h2", { style: "margin:0" }, icon("home", "lg"), `SB ${S.broj} · ` + (info ? info.name : caveName(S.broj))),
      d && d.leaves.length ? h("div", { class: "muted mono" }, d.leaves.map(l => l.relative).join("  ·  ")) : null),
    h("div", { class: "spacer" }),
    h("button", { class: "btn", onclick: () => setTab("fast") }, icon("star"), "Brze radnje"),
    d && d.leaves.length ? h("button", { class: "btn", onclick: () => openTarget({ what: "path", path: d.leaves[0].path }) }, icon("folder"), "Otvori mapu") : null);
  card.append(head);
  if (!d) { card.append(h("div", { class: "loading" }, "Učitavam objekt…")); return card; }
  if (!d.leaves.length) {
    card.append(h("p", { class: "warnline" }, "Ovaj objekt nema mapu SB_" + S.broj + "_… pod !Za digitalizirat. Naredbe koje trebaju samo broj i dalje rade."));
  }
  if (d.leaves.length > 1) card.append(h("p", { class: "warnline" }, `⚠ ${d.leaves.length} mape nose isti broj – datoteke su spojene.`));
  if (d.locks && d.locks.length) card.append(h("p", { class: "warnline" }, "⚠ Otvoreno u Wordu/Excelu: " + d.locks.join(", ") + " – zatvori prije pokretanja koraka koji pišu u tu datoteku."));
  card.append(h("div", { class: "legend" },
    h("span", {}, h("i", { style: "background:var(--ok)" }), "gotovo"),
    h("span", {}, h("i", { style: "background:var(--brand)" }), "sljedeći korak"),
    h("span", {}, h("i", { style: "background:var(--stale)" }), "zastarjelo – ulaz se promijenio, ponovi"),
    h("span", {}, h("i", { style: "background:var(--neutral)" }), "čeka / po potrebi")));
  card.append(workflowView(d.workflow));
  return card;
}

function workflowView(wf) {
  if (!wf) return h("div", { class: "empty" }, "Nema podataka o tijeku.");
  return h("div", { class: "flow" }, ...wf.phases.map(ph => {
    const steps = wf.steps.filter(s => s.phase === ph.id);
    if (!steps.length) return null;
    return h("div", { class: "phase" }, h("h4", {}, ph.label), ...steps.map(flowStep));
  }));
}

function flowStep(st) {
  const meta = STATUS[st.status] || STATUS.unknown;
  const a = st.action ? S.catalog.actions.find(x => x.id === st.action) : null;
  let btn = null;
  if (st.id === "dosje") {
    btn = h("button", { class: "btn small", onclick: () => setTab("5D") }, "Otvori");
  } else if (st.open && !a) {
    btn = h("button", { class: "btn small" + (st.current ? " primary" : ""), title: fileName(st.open),
      onclick: () => openTarget({ what: "path", path: st.open }) }, icon("open"), "Otvori");
  } else if (a && ["todo", "stale", "unknown", "optional"].includes(st.status)) {
    const label = st.status === "stale" ? "Ponovi" : st.status === "unknown" ? "Provjeri" : "Pokreni";
    btn = h("button", { class: "btn small" + (st.current ? " primary" : ""), title: a.title, onclick: () => quickRun(a, st.preset) }, icon("play"), label);
  }
  return h("div", { class: `fstep ${st.status}` + (st.current ? " current" : ""), title: meta.label },
    h("span", { class: "st" }, icon(meta.icon)),
    h("span", { class: "lab" }, st.label, st.current ? h("span", { class: "now-tag" }, "SADA") : null),
    h("span", { class: "tail" }, btn,
      h("button", { class: "stagelink", title: "Otvori karticu " + st.stage, onclick: () => setTab(st.stage) }, st.stage)),
    st.note ? h("span", { class: "note" }, st.note) : null);
}

// Run an action straight from the workflow with its default options.
function quickRun(a, preset) {
  const vals = {};
  for (const o of a.options) vals[o.flag] = o.default;
  Object.assign(vals, preset || {});
  const files = a.file_kind ? candidates(a.file_kind) : [];
  if (a.file_kind && !files.length) return toast("Nema odgovarajuće datoteke u mapi objekta.", true);
  const ctx = { file: files[0] ? files[0].path : null, query: caveName(S.broj), vals };
  ctx.writes = writesFor(a, vals);
  ctx.cmd = cmdTextFor(a, ctx);
  runAction(a, ctx);
}

// ── ★ Brze radnje: several actions as one job ────────────────────────
// Which workflow step tells whether a recipe step's work already exists.
const STEP_OF_ACTION = {
  "intake-create": "mapa", karta: "karta", "osz-prefill": "osz-prefill",
  "photos-pull": "foto", "photos-process": "foto", "3n-k3c": "3n-k3c",
};

function renderFast() {
  const out = [h("div", { class: "page-head" },
    h("span", { class: "stage-chip" }, icon("star", "xl")),
    h("div", {}, h("h1", {}, "Brze radnje"),
      h("div", { class: "sub" }, "Više koraka za odabrani objekt u jednom potezu – jedan posao u Ispisu, jedna potvrda za sve što piše.")))];
  if (S.broj === null) {
    out.push(h("div", { class: "card note" }, "Odaberi objekt gore desno (Redni broj ili ime). Za novi objekt upiši njegov Redni broj iz SB-a – mapa još ne mora postojati."));
    return out;
  }
  const info = caveInfo();
  out.push(h("p", { class: "muted", style: "margin-top:-6px" }, `Objekt: SB ${S.broj} · ${caveName(S.broj) || "?"}` +
    (info ? ` – mapa ${info.relative}` : " – još nema mapu pod !Za digitalizirat; Novi objekt je napravi.")));
  out.push(h("div", { class: "grid" }, ...S.catalog.recipes.map(recipeCard)));
  return out;
}

function recipeCard(r) {
  const queued = (S.cave && S.cave.queued) ? S.cave.queued.length : 0;
  const skip = new Set();
  const list = h("ol", { class: "recipe" });
  r.steps.forEach((step, index) => {
    const a = S.catalog.actions.find(x => x.id === step.action);
    const inactive = step.when === "queued" && !queued;
    if (inactive) skip.add(index);
    const wf = wfStep(STEP_OF_ACTION[step.action]);
    const done = wf && wf.status === "done" && !["photos-process", "photos-pull"].includes(step.action);
    list.append(h("li", { class: inactive ? "off" : "" },
      h("label", { class: "check" },
        h("input", { type: "checkbox", checked: !inactive, disabled: inactive,
          onchange: e => { e.target.checked ? skip.delete(index) : skip.add(index); } }),
        a ? a.title : step.action),
      writesFor(a, Object.fromEntries(Object.entries(step.options))) ? h("span", { class: "writes-tag" }, "piše") : null,
      done ? h("span", { class: "chip on", title: "već postoji – korak će to prepoznati" }, "✓ postoji") : null,
      inactive ? h("span", { class: "muted" }, "– nema fotografija u redu čekanja") : null,
      step.when === "queued" && queued ? h("span", { class: "chip" }, `📷 ${queued}`) : null,
      step.keep_going ? h("span", { class: "muted", title: "Ako ovaj korak ne uspije, idući se ipak pokreću." }, " ↷") : null));
  });
  const run = h("button", { class: "btn primary" }, icon("star"), "Pokreni sve");
  run.addEventListener("click", () => runRecipe(r, skip));
  return h("div", { class: "card hl" },
    h("h2", {}, icon("star", "lg"), r.title), h("p", { class: "help" }, r.help), list,
    h("div", { class: "row", style: "margin-top:10px" }, run,
      h("span", { class: "muted", style: "font-size:12px" }, "↷ = nastavlja i ako taj korak ne uspije")));
}

async function runRecipe(r, skip) {
  const queued = (S.cave && S.cave.queued) ? S.cave.queued.length : 0;
  const chosen = r.steps.map((st, i) => [st, i]).filter(([st, i]) => !skip.has(i) && !(st.when === "queued" && !queued));
  if (!chosen.length) return toast("Nijedan korak nije odabran.", true);
  const writes = chosen.map(([st]) => {
    const a = S.catalog.actions.find(x => x.id === st.action);
    const w = writesFor(a, Object.fromEntries(Object.entries(st.options)));
    return w ? `• ${a.title}: ${w}` : null;
  }).filter(Boolean);
  if (writes.length) {
    const ok = await confirmDialog({ title: `${r.title} – SB ${S.broj}`, text: "Ovi koraci pišu:\n" + writes.join("\n"),
      cmd: chosen.map(([st]) => st.action).join(" → "), okLabel: "Pokreni sve", remember: false });
    if (!ok) return;
  }
  try {
    addJob(await api("recipe", { recipe: r.id, broj: S.broj, skip: [...skip], confirmed: writes.length > 0 }));
  } catch (e) { toast(e.message, true); }
}

// ── stage tabs ───────────────────────────────────────────────────────
function renderStage(stage) {
  const out = [h("div", { class: "page-head" },
    h("span", { class: "stage-chip" }, icon(STAGE_ICON[stage.label] || "dot", "xl"), h("span", { class: "lbl" }, stage.label)),
    h("div", {}, h("h1", {}, stage.title), h("div", { class: "sub" }, stage.subtitle)),
    h("div", { class: "spacer" }),
    h("span", { class: "status-pill" }, stage.status),
    h("button", { class: "btn ghost", onclick: () => setTab("doc:" + stage.readme) }, icon("book"), "README"))];
  for (const note of stage.notes) out.push(h("div", { class: "card note", style: "margin-bottom:14px" }, note));

  if (stage.label === "6P") { out.push(...renderPredajaMockup()); return out; }
  if (stage.label === "2B") { const c = sbCard(); if (c) out.push(h("div", { class: "grid", style: "margin-bottom:14px" }, c)); }
  if (stage.label === "5D") out.push(...renderDossier());
  if (stage.label === "5O") out.push(...renderPeopleOfCave());
  if (stage.label === "3N") out.push(h("div", { class: "card note", style: "margin-bottom:14px" },
    h("div", { class: "row" }, icon("nacrt", "lg"),
      h("span", { style: "flex:1" }, "Koji TopoDroid simbol postaje koji cSurvey znak, boja poligona, veličine znakova – zadano za sve objekte, a za ovaj objekt se može prilagoditi prije KORAKA 1 ili 2."),
      h("button", { class: "btn", onclick: () => setTab("map3n") }, "Mapiranje simbola →"))));

  const actions = S.catalog.actions.filter(a => a.stage === stage.label);
  const steps = actions.filter(a => a.step);
  const plain = actions.filter(a => !a.step && !a.group);
  const groups = [...new Set(actions.filter(a => !a.step && a.group).map(a => a.group))];

  if (actions.some(a => a.needs_cave) && S.broj === null) {
    out.push(h("div", { class: "card note", style: "margin-bottom:14px" }, "Neke naredbe ovdje rade na jednom objektu – odaberi ga gore desno."));
  }
  if (steps.length) {
    out.push(h("div", { class: "steps" }, ...steps.map(a => {
      const st = stepState(a);
      return h("div", { class: "step" + (a.tool === "manual" ? " manual" : "") + (st ? ` s-${st.status}` + (st.current ? " s-current" : "") : "") },
        h("div", { class: "step-tag" }, a.step,
          st ? h("span", { class: "state" }, icon((STATUS[st.status] || STATUS.unknown).icon),
            st.current ? "SADA" : (STATUS[st.status] || STATUS.unknown).label) : null),
        a.tool === "manual" ? manualCard(a) : actionCard(a, st));
    })));
  }
  if (plain.length) out.push(h("div", { class: "grid", style: steps.length ? "margin-top:18px" : "" }, ...plain.map(a => actionCard(a))));
  for (const g of groups) {
    out.push(h("h3", { class: "group-title" }, g));
    out.push(h("div", { class: "grid" }, ...actions.filter(a => !a.step && a.group === g).map(a => actionCard(a))));
  }
  if (stage.label === "4F" && S.cave) {
    if (S.cave.queued && S.cave.queued.length) {
      const pull = S.catalog.actions.find(x => x.id === "photos-pull");
      out.push(h("h3", { class: "group-title" }, `U redu čekanja (…za istražit) – ${S.cave.queued.length}`),
        h("div", { class: "card note", style: "margin-bottom:12px" },
          h("div", { class: "row" }, icon("foto-red", "lg"),
            h("span", { style: "flex:1" }, "Ove fotografije još nisu u mapi objekta. Povlačenje ih premješta tamo (i stvara mapu ako je nema) i miče SB_ prefiks, da ih obrada vidi."),
            pull ? h("button", { class: "btn primary", onclick: () => quickRun(pull, { "--apply": true }) }, icon("play"), "Povuci u mapu objekta") : null)),
        gallery(S.cave.queued));
    }
    if (S.cave.leaves.length) out.push(h("h3", { class: "group-title" }, "Fotografije u mapi objekta"), gallery());
  }
  const kinds = STAGE_FILES[stage.label];
  if (kinds && S.cave && S.cave.leaves.length) out.push(h("h3", { class: "group-title" }, "Datoteke objekta"), filesCard(kinds));
  if (stage.label === "4I" && S.cave && S.cave.karta) out.push(h("h3", { class: "group-title" }, "Isječak ovog objekta"), kartaView(S.cave.karta));
  return out;
}

// Workflow state for a 3N step card; the two manual cSurvey steps borrow the
// state of the step that proves they happened.
function stepState(a) {
  const proxy = { "3n-m1": "3n-k2", "3n-m2": "3n-k3a" }[a.id];
  const st = wfStep(proxy || a.id);
  if (!st) return null;
  if (proxy) return { status: ["done", "stale"].includes(st.status) ? "done" : st.status === "blocked" ? "blocked" : "todo", current: false };
  return st;
}

function kartaView(k) {
  if (!k.exists) return h("div", { class: "empty" }, "Još nema isječka za ovaj objekt – pokreni Isječak karte (gore).");
  const src = `/api/thumb?broj=${S.broj}&w=1600&t=${encodeURIComponent(TOKEN)}&path=${encodeURIComponent(k.path)}`;
  const rec = k.record || {};
  // Georef zapis = id;ime;X;Y;… as georef.hr stores the point.
  const parts = (rec["Georef zapis"] || "").split(";");
  return h("div", { class: "karta" },
    h("div", { class: "card karta-img", onclick: () => lightboxSrc(src, fileName(k.path)) }, h("img", { src, alt: "Isječak karte" })),
    h("div", { class: "card" }, h("h2", {}, icon("karta", "lg"), fileName(k.path)),
      k.record ? h("dl", { class: "kv" },
        h("dt", {}, "Ime objekta"), h("dd", {}, rec["Ime objekta"] || "–"),
        h("dt", {}, "Datum"), h("dd", {}, rec["Datum"] || "–"),
        h("dt", {}, "georef.hr točka"), h("dd", { class: "mono" }, parts[0] || "–"),
        h("dt", {}, "X / Y (HTRS96)"), h("dd", { class: "mono" }, parts.length > 3 ? `${Math.round(+parts[2])} / ${Math.round(+parts[3])}` : "–"),
        h("dt", {}, "Georef zapis"), h("dd", { class: "mono" }, rec["Georef zapis"] || "–"))
        : h("p", { class: "warnline" }, "Nema retka u !georef_zapisi.csv – idući Isječak karte ga popravlja sam."),
      h("div", { class: "row" },
        h("button", { class: "btn", onclick: () => openTarget({ what: "path", path: k.path }) }, icon("open"), "Otvori PNG"),
        h("button", { class: "btn ghost", onclick: () => openTarget({ what: "path", path: k.path, reveal: true }) }, icon("folder"), "Mapa"))));
}

function renderPredajaMockup() {
  const tile = (title, text) => h("div", { class: "card" }, h("h3", {}, title),
    h("p", { class: "help" }, text), h("button", { class: "btn", disabled: true }, "Uskoro (M6)"));
  return [h("div", { class: "grid" },
    tile("Provjera praga SUE", "Dosje mora biti spreman (5D): Nacrt, OSZ, fotografija, pločica, izjave."),
    tile("Upis dopuna u SB", "Skupljeni dopune-*.csv upisuju se u SB preko Excel COM-a, uz pregled svake promjene."),
    tile("Isporuka u arhivu", "Nacrt → !!Nacrti, OSZ → !!Osnovni zapisnici, fotografije → !!Fotografije ulaza, preimenovano na SUE broj."),
    tile("Predaja CroSpeleu", "Paket za crospeleo-automation (prag 2)."))];
}

// ── 5D dosje + 5O osobe (one /api/dossier call feeds both) ───────────
function dossierState() {
  if (S.broj === null) return { node: h("div", { class: "card note", style: "margin-bottom:14px" }, "Odaberi objekt gore desno.") };
  if (!S.dossier || S.dossier.broj !== S.broj) { loadDossier(false); return { node: h("div", { class: "loading" }, "Učitavam dosje iz SB-a…") }; }
  if (S.dossier.loading) return { node: h("div", { class: "loading" }, "Učitavam dosje iz SB-a…") };
  if (S.dossier.error) return { node: h("div", { class: "card note", style: "margin-bottom:14px" }, "Dosje se ne može složiti: " + S.dossier.error,
    " ", h("button", { class: "btn small", onclick: () => loadDossier(true) }, "Pokušaj ponovno")) };
  return { data: S.dossier.data };
}

function renderDossier() {
  const st = dossierState();
  if (!st.data) return [st.node];
  const d = st.data;
  const out = [h("div", { class: "page-head", style: "margin-bottom:10px" },
    h("div", {}, h("h2", { style: "margin:0" }, d.name),
      h("div", { class: "muted" }, `${d.lifecycle} – ${d.lifecycle_hint}` + (d.excel_row ? ` · Excel red ${d.excel_row}` : ""))),
    h("div", { class: "spacer" }),
    h("button", { class: "btn", onclick: () => loadDossier(true) }, icon("refresh"), "Osvježi dosje"))];
  out.push(h("div", { class: "grid" }, ...d.gates.map(g => h("div", { class: "card gate " + (g.ready ? "ready" : "not") },
    h("div", { class: "verdict" }, h("span", { class: "big" }, icon(g.ready ? "check" : "lock", "lg")),
      h("div", {}, `Prag ${g.ordinal} – ${g.label}`, h("div", { class: "muted", style: "font-weight:400;font-size:12.5px" },
        g.ready ? "SPREMAN" : "NIJE SPREMAN" + (g.ordinal === 2 ? " (uz sve iz praga 1)" : "")))),
    h("ul", { class: "issues" },
      ...g.blockers.map(m => h("li", {}, h("span", { class: "sev blocker" }, "BLOKIRA"), m)),
      ...g.warnings.map(m => h("li", {}, h("span", { class: "sev warning" }, "UPOZORENJE"), m))),
    // Unchecked rules wait on a source nobody has gathered yet; they are the
    // long tail, so they fold away and the real findings lead.
    g.unchecked.length ? h("details", {}, h("summary", { class: "muted" },
      `Još neprovjereno: ${g.unchecked.length} pravila (izvor nije prikupljen)`),
      h("ul", { class: "issues" }, ...g.unchecked.map(u => h("li", {},
        h("span", { class: "sev unchecked" }, u.severity === "blocker" ? "BLOKIRA AKO NEDOSTAJE" : "UPOZORENJE"),
        `${u.label} – treba ${u.source_label}`)))) : null,
    !g.blockers.length && !g.warnings.length && !g.unchecked.length ? h("p", { class: "muted" }, "Nema nalaza.") : null))));
  out.push(h("div", { class: "grid", style: "margin-top:14px" },
    h("div", { class: "card" }, h("h2", {}, icon("dosje", "lg"), "Izvori"),
      h("div", { class: "chips" }, ...d.sources.map(s => h("span", { class: "chip" + (s.gathered ? " on" : ""), title: s.gathered ? "prikupljeno" : "još nije prikupljeno" }, (s.gathered ? "✓ " : "· ") + s.label))),
      d.survey ? h("dl", { class: "kv", style: "margin-top:10px" },
        h("dt", {}, "Duljina / dubina"), h("dd", {}, `${d.survey.length_m ?? "–"} / ${d.survey.depth_m ?? "–"} m`)) : null,
      d.files.length ? h("ul", { class: "muted mono" }, ...d.files.map(f => h("li", {}, f))) : null),
    peopleCard(d),
    d.sb.length ? h("div", { class: "card" }, h("h2", {}, icon("baza", "lg"), "SB red"),
      h("dl", { class: "kv" }, ...d.sb.flatMap(([k, v]) => [h("dt", {}, k), h("dd", {}, v)]))) : null));
  out.push(h("h3", { class: "group-title" }, "Naredbe"));
  return out;
}

function peopleCard(d) {
  const mark = { ok: "✓", scope: "~", missing: "✗", unknown: "?" };
  const tip = { ok: "izjava pokriva ovaj objekt", scope: "izjava postoji, ali ne pokriva ovaj objekt",
    missing: "nema izjave", unknown: "nije u registru osoba" };
  return h("div", { class: "card" }, h("h2", {}, icon("osobe", "lg"), "Osobe · izjave",
      h("span", { class: "tip", tabindex: "0", "aria-label": "Objašnjenje oznaka" }, "?",
        h("span", { class: "tip-body", role: "tooltip" },
          h("b", {}, "Oznake"),
          ...Object.keys(mark).map(k => h("div", {}, h("span", { class: "pstat " + k }, mark[k]), " ", tip[k]))))),
    d.people.length ? h("table", { class: "files" }, ...d.people.map(p => h("tr", { title: tip[p.status] },
      h("td", { class: "pstat " + p.status }, mark[p.status] || "?"),
      h("td", { class: "name" }, p.name), h("td", { class: "kind" }, p.roles.join(", ")),
      h("td", { class: "kind" }, p.files.join(", ") || "nema izjave"))))
      : h("p", { class: "muted" }, "SB red ne navodi autore kojima treba izjava."));
}

function renderPeopleOfCave() {
  const st = dossierState();
  if (!st.data) return [st.node];
  return [h("div", { class: "grid", style: "margin-bottom:14px" }, peopleCard(st.data))];
}

// ── documentation viewer ─────────────────────────────────────────────
function renderDoc(path) {
  const doc = S.docs[path];
  if (!doc) {
    S.docs[path] = { loading: true };
    api("doc?path=" + encodeURIComponent(path))
      .then(d => { S.docs[path] = d; }).catch(e => { S.docs[path] = { error: e.message }; })
      .finally(() => { if (S.tab === "doc:" + path) render(); });
    return [h("div", { class: "loading" }, "Učitavam " + path + "…")];
  }
  if (doc.loading) return [h("div", { class: "loading" }, "Učitavam " + path + "…")];
  if (doc.error) return [h("div", { class: "card note" }, doc.error)];
  const head = h("div", { class: "page-head" },
    h("span", { class: "stage-chip" }, icon("book", "xl")),
    h("div", {}, h("h1", {}, fileName(path)), h("div", { class: "sub mono" }, path)),
    h("div", { class: "spacer" }),
    h("button", { class: "btn ghost", onclick: () => { delete S.docs[path]; render(); } }, icon("refresh"), "Ponovno učitaj"),
    h("button", { class: "btn", onclick: () => openTarget({ what: "readme", path }) }, icon("open"), "Otvori u editoru"));
  const body = h("article", { class: "card md" });
  body.append(...markdown(doc.text, path));
  return [head, body];
}

// A small Markdown renderer: headings (with GitHub-style ids), paragraphs,
// lists, fenced code, tables, quotes, rules and inline code/bold/italic/links.
// Built with DOM nodes, never innerHTML, so a doc can't inject markup.
function slug(text) {
  return text.trim().toLowerCase().replace(/[^\p{L}\p{N}\s_-]/gu, "").replace(/\s/g, "-");
}
function inline(text, base) {
  const out = [];
  const re = /(`[^`]+`)|(\*\*[^*]+\*\*)|(\*[^*\s][^*]*\*)|(\[([^\]]+)\]\(([^)\s]+)\))|(<a name="[^"]*"><\/a>)|(<\/?(?:sub|br)\s*\/?>)/g;
  let last = 0, m;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index));
    if (m[1]) out.push(h("code", {}, m[1].slice(1, -1)));
    else if (m[2]) out.push(h("strong", {}, ...inline(m[2].slice(2, -2), base)));
    else if (m[3]) out.push(h("em", {}, ...inline(m[3].slice(1, -1), base)));
    else if (m[4]) out.push(docLink(m[5], m[6], base));
    last = re.lastIndex;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}
function resolvePath(base, rel) {
  const parts = base.split("/").slice(0, -1);
  for (const seg of rel.split("/")) {
    if (seg === "..") parts.pop(); else if (seg && seg !== ".") parts.push(seg);
  }
  return parts.join("/");
}
function docLink(label, href, base) {
  const a = h("a", { href: href }, ...inline(label, base));
  if (/^https?:/i.test(href)) { a.target = "_blank"; a.rel = "noopener"; return a; }
  a.addEventListener("click", e => {
    e.preventDefault();
    const [file, hash] = href.split("#");
    if (!file) return scrollToId(hash);
    const target = resolvePath(base, decodeURIComponent(file));
    if (/\.md$/i.test(target)) { setTab("doc:" + target); if (hash) setTimeout(() => scrollToId(hash), 400); }
    else openTarget({ what: "readme", path: target });
  });
  return a;
}
function scrollToId(id) {
  const el = document.getElementById(decodeURIComponent(id || ""));
  if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
}
function markdown(text, base) {
  const lines = text.replace(/\r/g, "").split("\n");
  const out = [];
  let i = 0;
  const isTable = l => /^\s*\|.*\|\s*$/.test(l);
  const isItem = l => /^\s*([-*]|\d+\.)\s/.test(l);
  const cells = l => l.trim().replace(/^\||\|$/g, "").split("|").map(c => c.trim());
  while (i < lines.length) {
    const line = lines[i];
    if (/^```/.test(line)) {
      const buf = [];
      for (i++; i < lines.length && !/^```/.test(lines[i]); i++) buf.push(lines[i]);
      i++;
      out.push(h("pre", { class: "cmd" }, buf.join("\n")));
    } else if (/^#{1,6}\s/.test(line)) {
      const level = line.match(/^#+/)[0].length;
      const txt = line.replace(/^#+\s*/, "");
      const plain = txt.replace(/\[([^\]]*)\]\([^)]*\)/g, "$1").replace(/[`*]/g, "");
      out.push(h("h" + Math.min(level + 1, 6), { id: slug(plain) }, ...inline(txt, base)));
      i++;
    } else if (/^\s*(---|\*\*\*)\s*$/.test(line)) {
      out.push(h("hr", {})); i++;
    } else if (isTable(line) && i + 1 < lines.length && /^\s*\|[\s:|-]+\|\s*$/.test(lines[i + 1])) {
      const head = cells(line);
      const rows = [];
      for (i += 2; i < lines.length && isTable(lines[i]); i++) rows.push(cells(lines[i]));
      out.push(h("div", { class: "md-table" }, h("table", { class: "files" },
        h("thead", {}, h("tr", {}, ...head.map(c => h("th", {}, ...inline(c, base))))),
        h("tbody", {}, ...rows.map(r => h("tr", {}, ...r.map(c => h("td", {}, ...inline(c, base)))))))));
    } else if (isItem(line)) {
      const list = h(/^\s*\d+\./.test(line) ? "ol" : "ul", {});
      while (i < lines.length && isItem(lines[i])) {
        let item = lines[i].replace(/^\s*([-*]|\d+\.)\s+/, "");
        for (i++; i < lines.length && /^\s{2,}\S/.test(lines[i]) && !isItem(lines[i]); i++) item += " " + lines[i].trim();
        list.append(h("li", {}, ...inline(item, base)));
      }
      out.push(list);
    } else if (/^>\s?/.test(line)) {
      const buf = [];
      for (; i < lines.length && /^>\s?/.test(lines[i]); i++) buf.push(lines[i].replace(/^>\s?/, ""));
      out.push(h("blockquote", {}, ...inline(buf.join(" "), base)));
    } else if (!line.trim()) {
      i++;
    } else {
      const buf = [];
      for (; i < lines.length && lines[i].trim() && !/^(#{1,6}\s|```|>)/.test(lines[i]) && !isItem(lines[i]) && !isTable(lines[i]); i++) buf.push(lines[i].trim());
      if (!buf.length) { buf.push(line); i++; }
      out.push(h("p", {}, ...inline(buf.join(" "), base)));
    }
  }
  return out;
}

// ── 4F gallery ───────────────────────────────────────────────────────
function thumbUrl(f, w) {
  return `/api/thumb?broj=${S.broj}&w=${w}&t=${encodeURIComponent(TOKEN)}&path=${encodeURIComponent(f.path)}`;
}

function gallery(list) {
  if (list) return h("div", { class: "gallery" }, ...list.map(photoCard));
  const photos = S.cave.files.filter(f => PHOTO_KINDS.has(f.kind))
    .sort((a, b) => (a.kind === b.kind ? a.name.localeCompare(b.name) : a.kind === "photo_processed" ? -1 : 1));
  if (!photos.length) return h("div", { class: "empty" }, "U mapi objekta nema fotografija. Ubaci ih ili ih povuci iz reda čekanja (gore).");
  return h("div", { class: "gallery" }, ...photos.map(photoCard));
}

const PHOTO_BADGE = { photo_processed: ["done", "obrađena"], photo: ["orig", "original"], queued: ["queued", "u redu čekanja"] };
function photoCard(f) {
  const [cls, label] = PHOTO_BADGE[f.kind] || ["orig", f.kind];
  return h("div", { class: "card photo" },
    h("div", { class: "img", onclick: () => lightbox(f) },
      /\.heic$/i.test(f.name) ? h("span", { class: "muted" }, "HEIC – nema pregleda")
        : h("img", { src: thumbUrl(f, 480), loading: "lazy", alt: f.name })),
    h("div", { class: "meta" },
      h("span", { class: "k " + cls }, label),
      f.relative, h("div", { class: "muted" }, `${fmtSize(f.size)} · ${fmtTime(f.modified)}`)),
    h("div", { class: "acts" },
      h("button", { class: "btn small", onclick: () => openTarget({ what: "path", path: f.path }) }, icon("open"), "Otvori"),
      h("button", { class: "btn small ghost", onclick: () => openTarget({ what: "path", path: f.path, reveal: true }) }, icon("folder"), "Mapa"),
      h("button", { class: "btn small danger", onclick: () => deletePhoto(f) }, icon("trash"), "Obriši")));
}

function lightbox(f) {
  if (/\.heic$/i.test(f.name)) return openTarget({ what: "path", path: f.path });
  lightboxSrc(thumbUrl(f, 1600), f.relative);
}
function lightboxSrc(src, caption) {
  $("#lightbox-img").src = src;
  $("#lightbox-cap").textContent = caption;
  const dlg = $("#lightbox");
  dlg.showModal();
  dlg.onclick = () => dlg.close();
}

async function deletePhoto(f) {
  const ok = await confirmDialog({
    title: "Obriši fotografiju",
    text: "Datoteka ide u koš: s Drivea u Google Drive smeće (30 dana), s lokalnog diska u Koš za smeće. Odande se može vratiti.",
    cmd: f.relative, okLabel: "Obriši", remember: false,
  });
  if (!ok) return;
  try {
    await api("delete", { broj: S.broj, path: f.path, confirmed: true });
    toast("Obrisano: " + f.name);
    loadCave();
  } catch (e) { toast(e.message, true); }
}

// ── action cards ─────────────────────────────────────────────────────
function candidates(kind) {
  if (!S.cave) return [];
  const kinds = FILE_KINDS[kind] || [];
  return S.cave.files.filter(f => kinds.includes(f.kind)).sort((a, b) => b.modified - a.modified);
}

function manualCard(a) {
  const files = candidates(a.file_kind);
  const newest = files[0];
  return h("div", { class: "card" },
    h("h3", {}, a.title), h("p", { class: "help" }, a.manual),
    h("div", { class: "row" },
      h("button", { class: "btn", disabled: !newest, title: newest ? newest.path : "",
        onclick: () => openTarget({ what: "csurvey", path: newest.path }) },
        icon("nacrt"), newest ? "Otvori " + newest.name + " u cSurveyu" : "Nema datoteke za ovaj korak"),
      S.cave && S.cave.leaves.length ? h("button", { class: "btn ghost", onclick: () => openTarget({ what: "path", path: S.cave.leaves[0].path }) }, icon("folder"), "Mapa objekta") : null));
}

function quote(a) { return a === "" || /\s/.test(a) ? `"${a}"` : a; }

function argsFor(a, ctx) {
  const args = [];
  for (const t of a.args) {
    args.push(t.replace("{broj}", S.broj ?? "<broj>").replace("{file}", ctx.file || "<datoteka>").replace("{query}", ctx.query || "<ime>"));
  }
  for (const o of a.options) {
    const v = ctx.vals[o.flag];
    if (o.kind === "flag") { if (v) args.push(o.flag); }
    else if (v !== "" && v !== null && v !== undefined && v !== false) args.push(o.flag, String(v));
  }
  return args;
}
function writesFor(a, vals) {
  const ticked = a.options.filter(o => o.kind === "flag" && vals[o.flag]);
  if (a.writes && !ticked.some(o => o.safe)) return a.writes;
  if (a.unsafe_writes && ticked.some(o => o.unsafe)) return a.unsafe_writes;
  return null;
}
const cmdTextFor = (a, ctx) => (a.tool === "cli" ? "cavedossier " : `python $T\\${a.tool} `) + argsFor(a, ctx).map(quote).join(" ");

function actionCard(a, st) {
  const card = h("div", { class: "card" });
  const ctx = { vals: {}, file: null, query: caveName(S.broj) };
  for (const o of a.options) ctx.vals[o.flag] = o.default;

  const preview = h("code", { class: "cmd" });
  const runBtn = h("button", { class: "btn primary" }, "Pokreni");
  const writesTag = h("span", { class: "writes-tag" });

  const missing = () => {
    if (a.args.some(t => t.includes("{broj}") || t.includes("{file}")) && S.broj === null) return "Odaberi objekt.";
    if (a.file_kind && !ctx.file) return "Nema odgovarajuće datoteke u mapi objekta.";
    if (a.args.some(t => t.includes("{query}")) && !(ctx.query || "").trim()) return "Upiši ime objekta.";
    return null;
  };
  const refresh = () => {
    preview.textContent = cmdTextFor(a, ctx);
    const w = writesFor(a, ctx.vals);
    writesTag.textContent = w ? "piše" : "";
    writesTag.style.display = w ? "" : "none";
    writesTag.title = w || "";
    runBtn.className = "btn " + (w ? "warn" : "primary");
    runBtn.replaceChildren(icon("play"), st && st.status === "stale" ? "Ponovi" : w ? "Pokreni…" : "Pokreni");
    const m = missing();
    runBtn.disabled = !!m;
    runBtn.title = m || "";
  };

  card.append(h("div", { class: "action-head" }, h("h3", {}, a.title), writesTag));
  if (st && st.note) card.append(h("p", { class: st.status === "stale" ? "warnline" : "help", style: "margin:4px 0" }, st.note));
  if (a.help) card.append(h("p", { class: "help" }, a.help));

  if (a.file_kind) {
    const files = candidates(a.file_kind);
    ctx.file = files[0] ? files[0].path : null;
    const sel = h("select", { onchange: e => { ctx.file = e.target.value; refresh(); } },
      ...files.map(f => h("option", { value: f.path }, `${f.relative}  ·  ${fmtTime(f.modified)}`)));
    const openBtn = h("button", { class: "btn small ghost", title: "Otvori odabranu datoteku u cSurveyu",
      onclick: () => ctx.file && openTarget({ what: "csurvey", path: ctx.file }) }, icon("nacrt"), "cSurvey");
    card.append(h("label", { class: "field" }, h("span", {}, "Datoteka"),
      files.length ? h("div", { class: "cmd-row" }, sel, openBtn)
        : h("span", { class: "muted" }, S.broj === null ? "– odaberi objekt –" : "– nema datoteke za ovaj korak u mapi objekta –")));
  }
  if (a.args.some(t => t.includes("{query}"))) {
    card.append(h("label", { class: "field" }, h("span", {}, "Objekt (ime, SUE broj ili broj pločice)"),
      h("input", { type: "text", value: ctx.query, oninput: e => { ctx.query = e.target.value; refresh(); } })));
  }
  if (a.options.length) {
    const opts = h("div", { class: "opts" });
    for (const o of a.options) {
      if (o.kind === "flag") {
        opts.append(h("label", { class: "check", title: o.help || o.flag },
          h("input", { type: "checkbox", checked: !!o.default, onchange: e => { ctx.vals[o.flag] = e.target.checked; refresh(); } }), o.label));
      } else if (o.kind === "choice") {
        opts.append(h("label", { class: "opt-inline", title: o.help || o.flag }, o.label,
          h("select", { onchange: e => { ctx.vals[o.flag] = e.target.value; refresh(); } },
            ...o.choices.map(c => h("option", { value: c, selected: c === o.default }, c)))));
      } else {
        opts.append(h("label", { class: "opt-inline", title: o.help || o.flag }, o.label,
          h("input", { type: o.kind === "int" ? "number" : "text", value: o.default || "",
            style: o.kind === "text" ? "width:160px" : "", oninput: e => { ctx.vals[o.flag] = e.target.value; refresh(); } })));
      }
    }
    card.append(opts);
  }
  const copyBtn = h("button", { class: "btn small ghost", title: "Kopiraj naredbu za terminal",
    onclick: () => copy(cmdTextFor(a, ctx)) }, icon("copy"), "Kopiraj");
  card.append(h("div", { class: "cmd-row" }, preview, copyBtn));
  runBtn.addEventListener("click", () => runAction(a, { ...ctx, writes: writesFor(a, ctx.vals), cmd: cmdTextFor(a, ctx) }));
  card.append(h("div", { class: "row", style: "margin-top:8px" }, runBtn));
  refresh();
  return card;
}

function filesCard(kinds) {
  const files = S.cave.files.filter(f => kinds.includes(f.kind)).sort((a, b) => b.modified - a.modified);
  if (!files.length) return h("div", { class: "empty" }, "Još nema datoteka ove faze u mapi objekta.");
  return h("div", { class: "card" }, h("table", { class: "files" }, ...files.map(f => h("tr", {},
    h("td", { class: "kind" }, KIND_LABEL[f.kind] || f.kind),
    h("td", { class: "name" }, f.relative),
    h("td", { class: "kind" }, fmtTime(f.modified)),
    h("td", { class: "kind" }, fmtSize(f.size)),
    h("td", { class: "act" },
      SURVEY_KINDS.has(f.kind) ? h("button", { class: "btn small", onclick: () => openTarget({ what: "csurvey", path: f.path }) }, "cSurvey") : null, " ",
      h("button", { class: "btn small", onclick: () => openTarget({ what: "path", path: f.path }) }, "Otvori"), " ",
      h("button", { class: "btn small ghost", onclick: () => openTarget({ what: "path", path: f.path, reveal: true }) }, "Mapa"))))));
}

async function copy(text) {
  try { await navigator.clipboard.writeText(text); toast("Kopirano."); }
  catch (_) { toast("Kopiranje nije uspjelo.", true); }
}

// ── running ──────────────────────────────────────────────────────────
function confirmDialog({ title, text, cmd, okLabel, remember }) {
  const dlg = $("#confirm");
  $("#confirm-title").textContent = title;
  $("#confirm-text").textContent = text;
  $("#confirm-cmd").textContent = cmd || "";
  $("#confirm-ok").textContent = okLabel || "Pokreni";
  $("#confirm-remember").checked = false;
  $("#confirm-remember-row").style.display = remember ? "" : "none";
  return new Promise(resolve => {
    dlg.addEventListener("close", () => resolve(dlg.returnValue === "ok"), { once: true });
    dlg.returnValue = "";
    dlg.showModal();
  });
}

async function runAction(a, ctx) {
  if (ctx.writes && !S.remember.has(a.id)) {
    const ok = await confirmDialog({ title: a.title, text: "Ova radnja " + ctx.writes + ".", cmd: ctx.cmd, okLabel: "Pokreni", remember: true });
    if (!ok) return;
    if ($("#confirm-remember").checked) S.remember.add(a.id);
  }
  try {
    const job = await api("run", {
      action: a.id, broj: S.broj, file: ctx.file, query: ctx.query, options: { ...ctx.vals }, confirmed: !!ctx.writes,
    });
    addJob(job);
  } catch (e) { toast(e.message, true); }
}

function addJob(job) {
  S.jobs.set(job.id, { ...job });
  S.activeJob = job.id;
  openConsole();
  renderJobs();
  poll();
}

async function poll() {
  if (S.polling) return;
  S.polling = true;
  try {
    while ([...S.jobs.values()].some(j => j.running)) {
      for (const j of S.jobs.values()) {
        if (!j.running) continue;
        try {
          const upd = await api(`job/${j.id}?since=${j.offset}`);
          j.text += upd.text; j.offset = upd.offset;
          const finished = !upd.running && j.running;
          Object.assign(j, { running: upd.running, returncode: upd.returncode, log: upd.log });
          if (finished) onJobDone(j);
        } catch (_) { j.running = false; }
      }
      renderJobs();
      await new Promise(r => setTimeout(r, 400));
    }
  } finally { S.polling = false; }
}

function onJobDone(j) {
  toast(`${j.title}: ${j.returncode === 0 || j.returncode === 1 ? "gotovo" : "završilo s kodom " + j.returncode}`, ![0, 1].includes(j.returncode));
  if (S.broj !== null) { S.dossier = null; loadCave(); }
}

function renderJobs() {
  const list = [...S.jobs.values()].sort((a, b) => b.id - a.id);
  $("#console-count").textContent = list.length ? `(${list.filter(j => j.running).length} radi / ${list.length})` : "";
  $("#job-tabs").replaceChildren(...list.map(j => h("button", {
    class: "job-tab" + (j.id === S.activeJob ? " active" : ""),
    onclick: () => { S.activeJob = j.id; renderJobs(); },
  }, h("span", { class: "st" }, j.running ? "●" : (j.returncode === 0 || j.returncode === 1) ? "✓" : "✗"), `#${j.id} ${j.title}`)));
  const j = S.jobs.get(S.activeJob);
  const out = $("#job-output");
  const atBottom = out.scrollHeight - out.scrollTop - out.clientHeight < 40;
  out.textContent = j ? j.text : "Još ništa nije pokrenuto. Pokreni naredbu s bilo koje kartice.";
  if (atBottom) out.scrollTop = out.scrollHeight;
  $("#job-kill").disabled = !(j && j.running);
  $("#job-input").disabled = !(j && j.running);
  $("#job-copy").disabled = !j;
  $("#job-log").disabled = !(j && j.log);
}

function openConsole() {
  $("#console").classList.remove("collapsed");
  $("#console-arrow").textContent = "▾";
}

// ── wiring ───────────────────────────────────────────────────────────
function parseCave(text) {
  const m = String(text).trim().match(/^(?:SB_?)?(\d{1,4})\b/i);
  if (m) return parseInt(m[1], 10);
  const needle = fold(text.trim());
  if (!needle) return null;
  const hit = S.caves.find(c => fold(c.name).includes(needle))
    || (S.sbIndex && S.sbIndex.rows || []).find(r => fold(r.name).includes(needle) || fold(r.syn).includes(needle));
  return hit ? hit.broj : undefined;
}

function wire() {
  const input = $("#cave-input");
  input.addEventListener("focus", () => { input.select(); openMenu(); });
  input.addEventListener("click", () => { if ($("#cave-menu").hidden) openMenu(); });
  input.addEventListener("input", () => { input.dataset.typed = "1"; S.menuIdx = 0; renderMenu(); });
  input.addEventListener("blur", () => setTimeout(() => {
    if (document.activeElement !== input) { closeMenu(); input.value = caveLabel(S.broj); }
  }, 120));
  input.addEventListener("keydown", e => {
    const items = S.menuItems || [];
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      if ($("#cave-menu").hidden) openMenu();
      S.menuIdx = Math.max(0, Math.min(items.length - 1, S.menuIdx + (e.key === "ArrowDown" ? 1 : -1)));
      items.forEach((el, i) => el.classList.toggle("active", i === S.menuIdx));
      if (items[S.menuIdx]) items[S.menuIdx].scrollIntoView({ block: "nearest" });
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (items[S.menuIdx]) return pickCave(parseInt(items[S.menuIdx].dataset.broj, 10));
      const broj = parseCave(input.value);
      if (broj === undefined || broj === null) return toast("Nema takvog objekta.", true);
      pickCave(broj);
    } else if (e.key === "Escape") {
      closeMenu(); input.value = caveLabel(S.broj); input.blur();
    }
  });
  $("#cave-toggle").addEventListener("mousedown", e => {
    e.preventDefault();
    if ($("#cave-menu").hidden) { input.focus(); } else { closeMenu(); input.blur(); }
  });
  $("#btn-cave-clear").addEventListener("click", () => setCave(null));
  $("#btn-cave-folder").addEventListener("click", () => {
    if (S.cave && S.cave.leaves.length) openTarget({ what: "path", path: S.cave.leaves[0].path });
    else toast("Objekt nema mapu pod !Za digitalizirat.", true);
  });
  $("#btn-open-sb").addEventListener("click", () => openTarget({ what: "sb" }));
  $("#btn-refresh").addEventListener("click", () => loadAll(true).then(() => toast("Osvježeno.")).catch(e => toast(e.message, true)));

  $("#console-toggle").addEventListener("click", () => {
    const c = $("#console");
    if (c.classList.contains("collapsed")) openConsole();
    else if (!c.classList.contains("tall")) c.classList.add("tall");
    else { c.classList.remove("tall"); c.classList.add("collapsed"); $("#console-arrow").textContent = "▸"; }
  });
  $("#job-kill").addEventListener("click", async () => {
    try { await api(`job/${S.activeJob}/kill`, {}); } catch (e) { toast(e.message, true); }
  });
  $("#job-copy").addEventListener("click", () => {
    const j = S.jobs.get(S.activeJob);
    if (j) copy(j.display);
  });
  $("#job-log").addEventListener("click", () => {
    const j = S.jobs.get(S.activeJob);
    if (j && j.log) openTarget({ what: "path", path: j.log });
  });
  $("#job-input-form").addEventListener("submit", async e => {
    e.preventDefault();
    const field = $("#job-input");
    try {
      await api(`job/${S.activeJob}/input`, { line: field.value });
      field.value = "";
    } catch (err) { toast(err.message, true); }
  });
}

(async function main() {
  wire();
  S.tab = recall("cd.tab") || "home";
  const saved = recall("cd.broj");
  S.broj = saved ? parseInt(saved, 10) : null;
  render();
  try {
    await loadAll(false);
    if (S.broj !== null) $("#cave-input").value = caveLabel(S.broj);
    loadSbIndex();
    const jobs = await api("jobs");
    for (const j of jobs.jobs.reverse()) {
      S.jobs.set(j.id, await api(`job/${j.id}?since=0`));
      S.activeJob = j.id;
    }
    renderJobs();
    poll();
  } catch (e) {
    $("#main").replaceChildren(h("div", { class: "card note" }, "Ne mogu dohvatiti podatke sa servera: " + e.message));
  }
})();
