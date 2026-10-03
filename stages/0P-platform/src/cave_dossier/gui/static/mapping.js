// 3N › Mapiranje — the TDX → cSurvey mapping of one cave, drawn and editable.
// Loaded after app.js and uses its helpers (h, icon, api, toast, S, setTab).
// The page edits a copy of the cave's EFFECTIVE mapping (shared default +
// its tdx-mapping-objekt.json); saving sends it back and the server keeps
// only the difference from the default (gui/mapping.py, tdx_mapping.py).
"use strict";

const M = {
  broj: null, data: null, edit: null, error: null, loading: false,
  cat: null, catError: null,
  kind: "point", filter: "speleo", q: "",
};
const SECTION = { point: "points", line: "lines", area: "areas" };
const KIND_HR = { point: "Točke (znakovi)", line: "Linije", area: "Površine" };

// Properties › Centerline keys, grouped as the page shows them. The type of
// each comes from the server (fix_imported_linetypes.CENTERLINE_TYPES).
const CL_GROUPS = [
  ["Poligon (vlakovi)", [["PlotPenColor", "Boja"], ["PlotPenWidth", "Debljina"],
    ["PlotSelectedPenWidth", "Debljina odabranog"], ["PlotPenStyle", "Stil"]]],
  ["Točke (stanice)", [["PlotPointColor", "Boja"], ["PlotPointSize", "Veličina"],
    ["PlotSelectedPointSize", "Veličina odabrane"], ["PlotPointSymbol", "Oznaka (7 = trokut)"]]],
  ["Opće", [["PlotCenterlineForceColor", "Uvijek ova boja (ne boje segmenata)"],
    ["PlotCenterlineVector", "Vektorski prikaz poligona"]]],
  ["Brojevi točaka i bilješke", [["PlotTextScaleFactor", "Brojevi – mjerilo teksta"],
    ["PlotTextColor", "Brojevi – boja"], ["PlotNoteTextScaleFactor", "Bilješke – mjerilo"],
    ["PlotNoteTextColor", "Bilješke – boja"]]],
  ["Bočni vizuri (splay)", [["PlotSplayPenWidth", "Debljina"], ["PlotSplaySelectedPenWidth", "Debljina odabranog"],
    ["PlotSplayPenStyle", "Stil"], ["PlotSplayCrossScale", "Veličina križića"]]],
  ["LRUD", [["PlotLRUDPenWidth", "Debljina"], ["PlotLRUDSelectedPenWidth", "Debljina odabranog"],
    ["PlotLRUDPenStyle", "Stil"]]],
  ["Linija pomaka", [["PlotTranslationLinePenColor", "Boja"], ["PlotTranslationLinePenWidth", "Debljina"],
    ["PlotTranslationLinePenStyle", "Stil"]]],
  ["Površinski profil", [["SurfaceProfilePenColor", "Boja"], ["SurfaceProfilePenWidth", "Debljina"],
    ["SurfaceProfileSelectedPenWidth", "Debljina odabranog"], ["SurfaceProfilePenStyle", "Stil"]]],
];
const FLAG_KEYS = new Set(["PlotCenterlineForceColor", "PlotCenterlineVector"]);
const PEN_STYLES = [[0, "puna"], [1, "crtkana"], [2, "točkasta"]];
const SIZE_HR = { default: "zadana", verysmall: "vrlo mala", small: "mala", medium: "srednja", large: "velika", verylarge: "vrlo velika" };

const clone = o => JSON.parse(JSON.stringify(o));
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const argbToHex = v => "#" + ((v >>> 0) & 0xffffff).toString(16).padStart(6, "0");
const hexToArgb = hex => (parseInt("ff" + hex.slice(1), 16) | 0);
const norm = s => String(s || "").toLowerCase().replace(/[-_]/g, "");

// ── loading ──────────────────────────────────────────────────────────
async function loadMapping(force) {
  if (S.broj === null) return;
  if (!force && M.broj === S.broj && (M.data || M.loading || M.error)) return;
  if (M.edit && M.broj !== S.broj && isDirty()) toast(`Nespremljene izmjene za SB ${M.broj} su odbačene.`, true);
  const broj = S.broj;
  Object.assign(M, { broj, data: null, edit: null, error: null, loading: true });
  render();
  try {
    const [data, cat] = await Promise.all([
      api("mapping/" + broj), M.cat ? Promise.resolve(M.cat) : api("mapping-catalog")]);
    if (S.broj !== broj) return;
    Object.assign(M, { data, edit: clone(data.effective), cat, loading: false });
  } catch (e) {
    if (S.broj === broj) Object.assign(M, { error: e.message, loading: false });
  }
  render();
}

// Empty sections the page creates while drawing (an absent sign_sizes shown as
// an empty table) are not edits.
function prune(o) {
  if (!o || typeof o !== "object" || Array.isArray(o)) return o;
  const out = {};
  for (const [k, v] of Object.entries(o)) {
    const p = prune(v);
    if (p && typeof p === "object" && !Array.isArray(p) && !Object.keys(p).length) continue;
    out[k] = p;
  }
  return out;
}
function isDirty() { return !!(M.data && M.edit) && !same(prune(M.edit), prune(M.data.effective)); }
const post = () => (M.edit.postimport = M.edit.postimport || {});
const centerline = () => (post().centerline = post().centerline || {});
const defPost = () => (M.data.default.postimport || {});

async function saveMapping() {
  try {
    const data = await api("mapping/" + M.broj, { effective: prune(M.edit) });
    Object.assign(M, { data, edit: clone(data.effective) });
    toast(data.override_path ? "Spremljeno za ovaj objekt." : "Isto kao zadano – prilagodba objekta uklonjena.");
  } catch (e) { toast(e.message, true); }
  render();
}

async function resetMapping() {
  if (!confirm(`Vratiti SB ${M.broj} na zajedničko zadano mapiranje? Prilagodba ovog objekta se briše.`)) return;
  try {
    const data = await api(`mapping/${M.broj}/reset`, {});
    Object.assign(M, { data, edit: clone(data.effective) });
    toast("Vraćeno na zadano.");
  } catch (e) { toast(e.message, true); }
  render();
}

// ── page ─────────────────────────────────────────────────────────────
function renderMapping() {
  const out = [h("div", { class: "page-head" },
    h("span", { class: "stage-chip" }, icon("nacrt", "xl"), h("span", { class: "lbl" }, "3N")),
    h("div", {}, h("h1", {}, "Mapiranje simbola i poligona"),
      h("div", { class: "sub" }, "TopoDroid → cSurvey: koji znak, linija, površina i boja poligona nastaje iz skice. Zadano vrijedi za sve objekte; izmjene ovdje samo za odabrani objekt.")),
    h("div", { class: "spacer" }),
    h("button", { class: "btn ghost", onclick: () => setTab("doc:stages/3N-nacrt/production/csurvey-settings.md") }, icon("book"), "Postavke cSurveya"))];
  if (S.broj === null) {
    out.push(h("div", { class: "card note" }, "Odaberi objekt gore desno – mapiranje se prilagođava po objektu."));
    return out;
  }
  if (M.broj !== S.broj || (!M.data && !M.loading && !M.error)) queueMicrotask(() => loadMapping());
  if (M.loading || M.broj !== S.broj) { out.push(h("div", { class: "empty" }, "Učitavam mapiranje…")); return out; }
  if (M.error) { out.push(h("div", { class: "card note" }, M.error)); return out; }
  out.push(statusCard());
  // in working order: KORAK 1 (before the import) first, then KORAK 2
  out.push(h("h3", { class: "group-title" }, "Simboli, linije i površine – KORAK 1"), symbolsCard());
  out.push(h("h3", { class: "group-title" }, "Poligon – KORAK 2"), centerlineCard());
  out.push(h("h3", { class: "group-title" }, "Veličine i uvoz – KORAK 2"), h("div", { class: "grid" }, sizesCard(), importCard()));
  requestAnimationFrame(() => autofitIn($("#main")));
  return out;
}

// What applies, what changed, and which KORAK to redo.
function statusCard() {
  const d = M.data, dirty = isDirty();
  const custom = !!d.override_path;
  const pending = dirty ? changedSections(d.effective, M.edit) : [];
  const saved = d.changed || [];
  const redo = redoHints();
  return h("div", { class: "card" + (dirty ? " hl" : ""), id: "map-status" },
    h("div", { class: "row" },
      h("span", { class: "badge " + (custom ? "fallback" : "live") }, custom ? "PRILAGOĐENO ZA OVAJ OBJEKT" : "ZADANO MAPIRANJE"),
      custom ? h("span", { class: "muted" }, `${saved.length} ${saved.length === 1 ? "dio" : "dijela"} drukčije: ${saved.map(sectionHr).join(", ")}`) : null,
      h("div", { class: "spacer" }),
      dirty ? h("button", { class: "btn", onclick: () => { M.edit = clone(d.effective); render(); } }, "Odbaci izmjene") : null,
      custom ? h("button", { class: "btn danger", onclick: resetMapping }, icon("refresh"), "Vrati na zadano") : null,
      h("button", { class: "btn primary", disabled: !dirty, onclick: saveMapping }, icon("check"), "Spremi za SB " + d.broj)),
    // always one line, so editing below never shifts the page
    h("div", { class: "help" }, dirty ? "Nespremljeno: " + pending.map(sectionHr).join(", ") + "." : "Nema nespremljenih izmjena."),
    d.error ? h("div", { class: "help", style: "color:var(--danger)" }, d.error) : null,
    h("div", { class: "help" },
      custom ? ["Prilagodba: ", h("a", { href: "#", onclick: e => { e.preventDefault(); openTarget({ what: "path", path: d.override_path, reveal: true }); } }, "tdx-mapping-objekt.json"), " u mapi objekta. "] : "Ovaj objekt koristi zajednički tdx-mapping.json. Promjena ovdje stvara tdx-mapping-objekt.json u mapi objekta. ",
      "Simboli, linije i površine djeluju u KORAKU 1 (prije uvoza u cSurvey); poligon, veličine i uvozne postavke u KORAKU 2."),
    ...redo.map(t => h("div", { class: "card note", style: "margin-top:8px;padding:8px 12px" }, icon("clock"), " ", t)));
}

function sectionHr(s) {
  return { points: "točke", lines: "linije", areas: "površine", generic: "opće", postimport: "poligon/veličine" }[s] || s;
}
function changedSections(a, b) {
  return ["points", "lines", "areas", "generic", "postimport"].filter(s => !same(prune(a[s] || {}), prune(b[s] || {})));
}

// A saved override newer than the cave's _pp / _lt means those files were made
// with the old mapping.
function redoHints() {
  const d = M.data;
  if (!d.override_modified || !S.cave) return [];
  const newest = kind => Math.max(0, ...S.cave.files.filter(f => f.kind === kind).map(f => f.modified));
  const k1 = (d.changed || []).some(s => d.korak_of[s] === 1), k2 = (d.changed || []).some(s => d.korak_of[s] === 2);
  const out = [];
  const pp = newest("pp"), lt = newest("lt");
  if (k1 && pp && pp < d.override_modified) out.push("_pp je napravljen prije ove prilagodbe simbola: ponovi KORAK 1, pa uvoz u cSurvey i KORAK 2.");
  else if (k2 && lt && lt < d.override_modified) out.push("_lt je napravljen prije ove prilagodbe: ponovi KORAK 2 na datoteci spremljenoj iz cSurveya.");
  return out;
}

// ── centerline ───────────────────────────────────────────────────────
function centerlineCard() {
  const types = M.data.centerline_types;
  const groups = CL_GROUPS.map(([title, fields]) => h("div", { class: "cl-group" },
    h("div", { class: "cl-title" }, title),
    ...fields.filter(([k]) => types[k]).map(([k, label]) => clField(k, label, types[k]))));
  return h("div", { class: "card cl-card" },
    h("div", { class: "cl-preview paper", id: "cl-preview" }, clPreview()),
    h("div", { class: "cl-fields" }, ...groups));
}

function clField(key, label, type) {
  const cur = centerline()[key], def = (defPost().centerline || {})[key];
  const changed = !same(cur, def);
  const set = v => {
    if (v === undefined) delete centerline()[key]; else centerline()[key] = v;
    refreshCenterline();
  };
  let input;
  if (type === "color") {
    input = h("input", { type: "color", value: argbToHex(cur === undefined ? -16777216 : cur), oninput: e => set(hexToArgb(e.target.value)),
      class: cur === undefined ? "unset" : null, title: cur === undefined ? "nije postavljeno – cSurvey zadano" : null });
  } else if (FLAG_KEYS.has(key)) {
    input = h("input", { type: "checkbox", checked: cur === 1, onchange: e => set(e.target.checked ? 1 : 0) });
  } else if (/PenStyle$/.test(key)) {
    input = h("select", { onchange: e => set(e.target.value === "" ? undefined : parseInt(e.target.value, 10)) },
      h("option", { value: "", selected: cur === undefined }, "cSurvey zadano"),
      ...PEN_STYLES.map(([v, l]) => h("option", { value: v, selected: cur === v }, l)));
  } else {
    input = h("input", { type: "number", step: type === "integer" ? "1" : "0.1", min: "0", value: cur === undefined ? "" : cur,
      placeholder: "cSurvey zadano", oninput: e => {
        const v = e.target.value === "" ? undefined : (type === "integer" ? parseInt(e.target.value, 10) : parseFloat(e.target.value));
        if (v === undefined || !isNaN(v)) set(v);
      } });
  }
  return h("label", { class: "cl-field" + (changed ? " changed" : ""), "data-key": key, title: key },
    h("span", { class: "cl-label" }, label),
    input,
    changed ? h("button", { class: "btn small ghost", title: "Vrati zadano: " + (def === undefined ? "cSurvey zadano" : def),
      onclick: e => { e.preventDefault(); set(def === undefined ? undefined : clone(def)); render(); } }, "↺") : null);
}

function refreshCenterline() {
  const p = $("#cl-preview");
  if (p) p.replaceChildren(clPreview());
  document.querySelectorAll(".cl-field").forEach(el => {
    const k = el.dataset.key;
    el.classList.toggle("changed", !same(centerline()[k], (defPost().centerline || {})[k]));
  });
  refreshStatus();
}

function refreshStatus() {
  const old = $("#map-status");
  if (old) old.replaceWith(statusCard());
}

// A stylized plan: five stations, splays, LRUD ticks and a note, in the
// chosen colours, widths and text scales. cSurvey's own drawing differs in
// detail; colours, styles and proportions are what this is for.
function clPreview() {
  const c = centerline();
  const col = k => c[k] === undefined ? "#000000" : argbToHex(c[k]);
  const dash = (k, w) => ({ 1: `${4 * w},${2 * w}`, 2: `${w},${1.6 * w}` })[c[k]] || "none";
  const pw = c.PlotPenWidth ?? 1, ps = c.PlotPointSize ?? 1, sw = c.PlotSplayPenWidth ?? 0.5, lw = c.PlotLRUDPenWidth ?? 0.5;
  const pen = c.PlotCenterlineForceColor === 1 ? col("PlotPenColor") : "#1f6fd1";
  const pts = [[30, 120], [95, 82], [170, 98], [240, 52], [320, 70]];
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("viewBox", "0 0 350 160");
  svg.setAttribute("class", "cl-svg");
  const add = (tag, attrs) => {
    const el = document.createElementNS(SVG_NS, tag);
    for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
    svg.append(el); return el;
  };
  const splays = [[0, -38, -18], [0, -10, 34], [1, -22, -30], [1, 18, 30], [2, 6, 36], [2, -28, -26], [3, -12, -34], [3, 30, 22], [4, 24, -24], [4, 6, 34]];
  for (const [i, dx, dy] of splays) {
    const [x, y] = pts[i];
    add("line", { x1: x, y1: y, x2: x + dx, y2: y + dy, stroke: "#7a7a7a", "stroke-width": sw * 1.4, "stroke-dasharray": dash("PlotSplayPenStyle", sw * 1.4) });
    const s = 3 * (c.PlotSplayCrossScale ?? 1);
    add("path", { d: `M${x + dx - s},${y + dy - s}L${x + dx + s},${y + dy + s}M${x + dx - s},${y + dy + s}L${x + dx + s},${y + dy - s}`, stroke: "#7a7a7a", "stroke-width": 0.8 });
  }
  for (const [x, y] of pts) add("line", { x1: x, y1: y - 16, x2: x, y2: y + 16, stroke: "#b08a2e", "stroke-width": lw * 1.4, "stroke-dasharray": dash("PlotLRUDPenStyle", lw * 1.4) });
  add("path", { d: "M50,150 L120,140", stroke: col("PlotTranslationLinePenColor"), "stroke-width": (c.PlotTranslationLinePenWidth ?? 1) * 1.2, "stroke-dasharray": dash("PlotTranslationLinePenStyle", 1.5), fill: "none" });
  add("polyline", { points: pts.map(p => p.join(",")).join(" "), fill: "none", stroke: pen, "stroke-width": pw * 1.5,
    "stroke-dasharray": dash("PlotPenStyle", pw * 1.5), "stroke-linejoin": "round" });
  const r = 3.2 * ps;
  pts.forEach(([x, y], i) => {
    if ((c.PlotPointSymbol ?? 7) === 7) add("path", { d: `M${x},${y - r}L${x + r * 0.9},${y + r * 0.6}L${x - r * 0.9},${y + r * 0.6}Z`, fill: col("PlotPointColor") });
    else add("circle", { cx: x, cy: y, r, fill: col("PlotPointColor") });
    const t = add("text", { x: x + 6, y: y - 7, "font-size": 11 * (c.PlotTextScaleFactor ?? 1), fill: col("PlotTextColor"), "font-family": "Segoe UI, sans-serif" });
    t.textContent = String(i);
  });
  const n = add("text", { x: 200, y: 145, "font-size": 11 * (c.PlotNoteTextScaleFactor ?? 0.5), fill: col("PlotNoteTextColor"), "font-family": "Segoe UI, sans-serif" });
  n.textContent = "bilješka uz točku";
  return svg;
}

// ── sizes + import switches ──────────────────────────────────────────
function sizesCard() {
  const p = post();
  const signs = p.sign_sizes = p.sign_sizes || {};
  const labels = p.label_sizes = p.label_sizes || {};
  const sizeSel = (obj, key) => h("select", { onchange: e => { obj[key] = e.target.value; render(); } },
    ...M.data.sizes.map(s => h("option", { value: s, selected: obj[key] === s }, SIZE_HR[s] || s)));
  const del = (obj, key) => h("button", { class: "btn small ghost", title: "Ukloni", onclick: () => { delete obj[key]; render(); } }, icon("trash"));
  const def = defPost();
  const mark = (defObj, obj, key) => (!same((defObj || {})[key], obj[key]) ? " changed" : "");
  const unusedSigns = M.data.sign_names.filter(n => !(n in signs));
  return h("div", { class: "card" },
    h("h2", {}, "Veličine znakova i oznaka"),
    h("div", { class: "help" }, "KORAK 2 postavlja veličinu znaka na uvezenim stavkama koje je još nemaju."),
    h("table", { class: "sizes" }, ...Object.keys(signs).map(k => h("tr", { class: mark(def.sign_sizes, signs, k) },
      h("td", {}, k), h("td", {}, sizeSel(signs, k)), h("td", {}, del(signs, k))))),
    h("div", { class: "row", style: "margin-top:6px" },
      h("select", { id: "add-sign" }, ...unusedSigns.map(n => h("option", { value: n }, n))),
      h("button", { class: "btn small", onclick: () => { const v = $("#add-sign").value; if (v) { signs[v] = "medium"; render(); } } }, "+ znak")),
    h("div", { class: "help", style: "margin-top:12px" }, "Tekstualne oznake (npr. ! iz TopoDroida):"),
    h("table", { class: "sizes" }, ...Object.keys(labels).map(k => h("tr", { class: mark(def.label_sizes, labels, k) },
      h("td", {}, h("code", {}, k)), h("td", {}, sizeSel(labels, k)), h("td", {}, del(labels, k))))),
    h("div", { class: "row", style: "margin-top:6px" },
      h("input", { id: "add-label", placeholder: "tekst", style: "width:80px" }),
      h("button", { class: "btn small", onclick: () => { const v = $("#add-label").value.trim(); if (v) { labels[v] = "large"; render(); } } }, "+ oznaka")));
}

function importCard() {
  const p = post(), g = (M.edit.generic = M.edit.generic || {}), dp = defPost(), dg = M.data.default.generic || {};
  const box = (obj, def, key, label, help) => h("label", { class: "cl-field" + (!same(obj[key], def[key]) ? " changed" : "") },
    h("input", { type: "checkbox", checked: !!obj[key], onchange: e => { obj[key] = e.target.checked; refreshStatus(); } }),
    h("span", {}, h("b", {}, label), h("div", { class: "help", style: "margin:0" }, help)));
  return h("div", { class: "card" },
    h("h2", {}, "Uvozne postavke"),
    box(p, dp, "spline_linetypes", "Linije u splajnove (KORAK 2)", "Bez ovoga kosine, skokovi i sl. ne pokazuju strelice i crtice."),
    box(p, dp, "nonstandard_water", "Nestandardna četka za vodu (KORAK 2)", "Vodene površine dobiju cSurveyevu 'Not standard' vodu."),
    box(p, dp, "wall_merge", "Spajanje zidova (KORAK 2)", "Zidove svježeg uvoza spoji u jedan obrub; linije bez snimka u blizini (npr. površina) ostanu kako su nacrtane."),
    box(p, dp, "wall_orientation", "Smjer zidova (KORAK 2)", "U spojenim obrubima okreće sekvencu koja gleda na krivu stranu; unutrašnjost se određuje iz vlakova i vizura."),
    box(p, dp, "wall_reorder", "Redoslijed zidova (KORAK 2)", "Presloži sekvence spojenog obruba tako da ispuna zatvara ulaze, a ne presijeca kanale."),
    box(g, dg, "strip_line_subtypes", "Podvrste linija na osnovnu (KORAK 1)", "npr. wall:blocks → wall kad nema izričitog mapiranja."),
    box(g, dg, "strip_area_suffix", "Površine bez nastavka -area (KORAK 1)", "npr. clay-area → clay."));
}

// ── symbols ──────────────────────────────────────────────────────────
function targetsOf(kind) { return (M.cat.targets || {})[kind] || []; }
function targetFor(kind, entry) {
  if (!entry || !entry.to) return null;
  const want = kind === "point" ? norm(entry.to) : entry.to;
  return targetsOf(kind).find(t => (kind === "point" ? norm(t.to) : t.to) === want) || null;
}
function entryOf(row) { return (M.edit[SECTION[row.kind]] || {})[row.name]; }
function defEntryOf(row) { return (M.data.default[SECTION[row.kind]] || {})[row.name]; }

// TopoDroid's symbol sets (symbols-git/symbols_<set>). "extra" is the set the
// manual calls "Extra speleo symbols" and the palette lists as the second
// speleo set, so the page calls it "speleo 2" and shows it by default.
const SET_HR = {
  speleo: "speleo", extra: "speleo 2", system: "sustavni", karst: "krš", geo: "geologija",
  mine: "rudarstvo", archeo: "arheologija", anthro: "antropogeno", paleo: "paleontologija", bio: "biologija",
};
const SPELEO_SETS = new Set(["speleo", "extra", "system"]);

// Would not arrive as itself: no mapping entry, and the natural import gives
// an empty sign (points), a plain border instead of the line, or generic soil.
function isBlank(r) {
  return !entryOf(r) && (r.natural || {}).css !== "ok";
}

function symbolRows(filter) {
  const q = fold(M.q), f = filter || M.filter;
  return M.cat.tdx.filter(r => r.kind === M.kind).filter(r => {
    if (q && !fold(`${r.name} ${r.label} ${r.label_it} ${SET_HR[r.set] || r.set}`).includes(q)) return false;
    if (f === "mapped") return !!entryOf(r) || !!defEntryOf(r);
    if (f === "speleo") return SPELEO_SETS.has(r.set) || !!entryOf(r) || !!defEntryOf(r);
    if (f === "blank") return SPELEO_SETS.has(r.set) && isBlank(r);
    return true;
  });
}

function symbolsCard() {
  const counts = k => M.cat.tdx.filter(r => r.kind === k).length;
  const seg = (val, cur, label, set) => h("button", { class: "seg" + (cur === val ? " on" : ""), onclick: () => { set(val); render(); } }, label);
  const list = h("div", { class: "sym-list", id: "sym-list" }, ...symbolRows().map(symbolRow));
  return h("div", { class: "card" },
    h("div", { class: "row" },
      h("div", { class: "segs" }, ...["point", "line", "area"].map(k => seg(k, M.kind, `${KIND_HR[k]} (${counts(k)})`, v => (M.kind = v)))),
      h("div", { class: "spacer" }),
      h("div", { class: "segs" }, seg("mapped", M.filter, "Mapirani", v => (M.filter = v)),
        seg("speleo", M.filter, "Speleo 1 + 2", v => (M.filter = v)),
        seg("blank", M.filter, `Bez pravog znaka (${symbolRows("blank").length})`, v => (M.filter = v)),
        seg("all", M.filter, "Svi setovi", v => (M.filter = v))),
      h("input", { type: "search", placeholder: "traži…", value: M.q, style: "width:150px",
        oninput: e => { M.q = e.target.value; const l = $("#sym-list"); l.replaceChildren(...symbolRows().map(symbolRow)); autofitIn(l); } })),
    h("div", { class: "help" }, "Lijevo TopoDroidov alat, desno što postaje u cSurveyu. ",
      h("span", { class: "tag def" }, "zadano"), " = zajedničko mapiranje, ",
      h("span", { class: "tag own" }, "ovaj objekt"), " = prilagodba samo za ovaj objekt. Bez mapiranja vrijedi prirodni uvoz (siva sličica); ",
      h("span", { style: "color:var(--danger)" }, "crveno"), " = cSurvey bi nacrtao prazan X."),
    list);
}

function symbolRow(row) {
  const kind = row.kind, entry = entryOf(row), def = defEntryOf(row);
  const own = !same(entry, def);
  const tgt = targetFor(kind, entry);
  const natural = row.natural || {};
  const natTarget = natural.num ? targetsOf(kind).find(t => t.num === natural.num) : null;

  let pic, caption, dim = false, bad = false;
  if (entry && entry.label !== undefined) { pic = h("div", { class: "label-pic" }, entry.label); caption = "tekstna oznaka"; }
  else if (entry && entry.leave) { pic = h("div", { class: "label-pic muted" }, "–"); caption = "ostavi kako jest"; }
  else if (tgt) { pic = svgTile(tgt.svg); caption = tgt.label; }
  else if (natTarget) { pic = svgTile(natTarget.svg); caption = natTarget.label; dim = true; }
  else { pic = h("div", { class: "label-pic", style: "color:var(--danger)" }, "✕"); caption = "nema znaka u cSurveyu"; bad = !entry; }

  const sel = h("select", { onchange: e => setEntry(row, e.target.value) },
    h("option", { value: "", selected: !entry }, naturalText(natural, natTarget)),
    kind === "point" ? h("option", { value: "@label", selected: !!entry && entry.label !== undefined }, "tekstna oznaka…") : null,
    h("option", { value: "@leave", selected: !!entry && !!entry.leave }, "ostavi (bez upozorenja)"),
    h("optgroup", { label: "cSurvey" }, ...targetsOf(kind).map(t =>
      h("option", { value: t.to, selected: !!tgt && tgt.to === t.to }, `${t.num} · ${t.label}`))));
  const extra = [];
  if (entry && entry.label !== undefined) extra.push(h("input", { value: entry.label, style: "width:70px", title: "tekst oznake",
    onchange: e => { entry.label = e.target.value; refreshRow(row); } }));
  if (kind === "line" && entry && entry.to) extra.push(h("label", { class: "mini" }, h("input", { type: "checkbox", checked: !!entry.reverse,
    onchange: e => { if (e.target.checked) entry.reverse = true; else delete entry.reverse; refreshRow(row); } }), "obrni smjer"));
  if (kind === "point" && entry && entry.to) extra.push(h("label", { class: "mini" }, "kut",
    h("input", { type: "number", step: "15", style: "width:62px", value: entry.orientation ?? "", placeholder: "–",
      onchange: e => { if (e.target.value === "") delete entry.orientation; else entry.orientation = parseInt(e.target.value, 10); refreshRow(row); } })));

  return h("div", { class: "sym-row" + (own ? " own" : "") + (bad ? " bad" : ""), "data-key": kind + ":" + row.name },
    svgTile(row.svg),
    h("div", { class: "sym-name" }, h("b", {}, row.name), " ", h("span", { class: "tag" }, SET_HR[row.set] || row.set),
      h("div", { class: "muted small" }, [row.label !== row.name ? row.label : "", row.label_it].filter(Boolean).join(" · "))),
    h("div", { class: "sym-arrow" }, "→"),
    h("div", { class: "sym-target" + (dim ? " dim" : "") }, pic, h("div", { class: "small" }, caption)),
    h("div", { class: "sym-edit" }, sel, ...extra,
      own ? h("span", { class: "tag own" }, "ovaj objekt") : def ? h("span", { class: "tag def" }, "zadano") : null,
      own ? h("button", { class: "btn small ghost", title: "Vrati na zadano", onclick: () => { setRaw(row, def ? clone(def) : undefined); } }, "↺") : null));
}

// What the converter does with no mapping entry, in words. The generator's
// verdicts are English ("Clay — renders"); only the target name is kept.
function naturalText(natural, natTarget) {
  if (natTarget) return "prirodno → " + natTarget.label + (natural.css === "warn" ? " (zamjena)" : "");
  if (natural.verdict && /label/.test(natural.verdict)) return "prirodno: tekstna oznaka";
  if (natural.verdict && /cross-section/.test(natural.verdict)) return "prirodno: presjek";
  return "prirodno: ✕ prazan znak";
}

function setRaw(row, value) {
  const sec = (M.edit[SECTION[row.kind]] = M.edit[SECTION[row.kind]] || {});
  if (value === undefined) delete sec[row.name]; else sec[row.name] = value;
  refreshRow(row);
}

function setEntry(row, v) {
  const old = entryOf(row) || {};
  if (v === "") return setRaw(row, undefined);
  if (v === "@leave") return setRaw(row, { leave: true });
  if (v === "@label") return setRaw(row, { label: old.label ?? "?" });
  const next = { to: v };
  if (row.kind === "line" && old.reverse) next.reverse = true;
  if (row.kind === "point" && old.orientation !== undefined) next.orientation = old.orientation;
  setRaw(row, next);
}

function refreshRow(row) {
  const el = document.querySelector(`.sym-row[data-key="${CSS.escape(row.kind + ":" + row.name)}"]`);
  if (el) { const nu = symbolRow(row); el.replaceWith(nu); autofitIn(nu); }
  refreshStatus();
}

// ── pictures ─────────────────────────────────────────────────────────
function svgTile(markup) {
  const d = h("div", { class: "tile paper" });
  d.innerHTML = markup || "";
  return d;
}
// Gallery SVGs carry their own odd viewBoxes; fit each to its drawing.
function autofitIn(root) {
  if (!root) return;
  root.querySelectorAll("svg.autofit").forEach(s => {
    try {
      const b = s.getBBox();
      if (b.width > 0.01 && b.height > 0.01) {
        const p = 0.12 * Math.max(b.width, b.height);
        s.setAttribute("viewBox", `${b.x - p} ${b.y - p} ${b.width + 2 * p} ${b.height + 2 * p}`);
      }
    } catch (_) {}
  });
}
