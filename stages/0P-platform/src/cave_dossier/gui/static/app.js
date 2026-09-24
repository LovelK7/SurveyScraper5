// Speleo nadzorna ploča — the page. Everything it can run comes from
// /api/catalog; this file only knows how to draw it.
"use strict";

const TOKEN = window.CD_TOKEN;
const S = {
  summary: null, catalog: null, caves: [], unprefixed: [],
  broj: null, cave: null, tab: "home",
  jobs: new Map(), activeJob: null, remember: new Set(), polling: false,
};

// Which intake-leaf file kinds a catalog `file_kind` accepts (mirrors state.FILE_KINDS).
const FILE_KINDS = {
  raw: ["raw"], pp: ["pp"], lt: ["lt"], fin: ["fin"], survey: ["raw", "pp", "lt", "fin"],
};
const SURVEY_KINDS = new Set(["raw", "pp", "lt", "fin", "backup"]);

// Files each stage tab lists for the current cave.
const STAGE_FILES = {
  "3N": ["raw", "pp", "lt", "fin", "plan", "profile", "dimenzije", "nacrt"],
  "4O": ["osz", "doc"],
  "4F": ["photo", "photo_processed"],
  "4S": ["sastavnica"],
  "5D": ["nacrt", "osz", "photo_processed", "sastavnica"],
};

const KIND_LABEL = {
  raw: "sirovi", pp: "_pp", lt: "_lt", fin: "_lt_fin", backup: "backup",
  plan: "tlocrt", profile: "profil", dimenzije: "dimenzije", nacrt: "NACRT",
  sastavnica: "sastavnica", osz: "OSZ", doc: "dokument", photo: "foto",
  photo_processed: "foto SB_", pdf: "pdf", other: "",
};

// The per-cave checklist on Pregled: label, test, owning stage.
const CHECKLIST = [
  ["Sirovi TopoDroid .csx", d => has(d, "raw"), "3N"],
  ["_pp — pripremljen (KORAK 1)", d => has(d, "pp"), "3N"],
  ["_lt — uvoz dovršen (KORAK 2)", d => has(d, "lt"), "3N"],
  ["_lt_fin — nacrt dovršen (KORAK 3a)", d => has(d, "fin"), "3N"],
  ["Tlocrt + profil PDF (KORAK 3b)", d => has(d, "plan") && has(d, "profile"), "3N"],
  ["SB_<broj>_nacrt.pdf (KORAK 3c)", d => has(d, "nacrt"), "3N"],
  ["OSZ zapisnik", d => has(d, "osz"), "4O"],
  ["Isječak karte", d => !!(d.karta && d.karta.exists), "4I"],
  ["Obrađene fotografije ulaza", d => has(d, "photo_processed"), "4F"],
  ["Sastavnica (Illustrator)", d => has(d, "sastavnica"), "4S"],
];
const has = (d, kind) => d.files.some(f => f.kind === kind);

// ── tiny DOM helper ──────────────────────────────────────────────────
function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "class") el.className = v;
    else if (k === "html") el.innerHTML = v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat()) {
    if (kid === null || kid === undefined || kid === false) continue;
    el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  }
  return el;
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
  try {
    await api("open", body);
  } catch (e) { toast(e.message, true); }
}

const fmtTime = ts => ts ? new Date(ts * 1000).toLocaleString("hr-HR", {
  day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "";
const fmtSize = n => n > 1048576 ? (n / 1048576).toFixed(1) + " MB" : Math.max(1, Math.round(n / 1024)) + " kB";
const shortName = s => (s || "").split("_")[0];

// ── loading ──────────────────────────────────────────────────────────
async function loadAll(refresh) {
  if (refresh) await api("refresh", {});
  const [summary, catalog, caves] = await Promise.all([
    api("state"), S.catalog ? Promise.resolve(S.catalog) : api("catalog"),
    api("caves" + (refresh ? "?refresh=1" : "")),
  ]);
  S.summary = summary; S.catalog = catalog;
  S.caves = caves.caves; S.unprefixed = caves.unprefixed;
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

function setCave(broj) {
  S.broj = broj;
  store("cd.broj", broj === null ? null : String(broj));
  const info = S.caves.find(c => c.broj === broj);
  $("#cave-input").value = broj === null ? "" : info ? `${broj} · ${info.name}` : String(broj);
  loadCave();
}

function setTab(tab) {
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
  const dl = $("#cave-list");
  dl.replaceChildren(...S.caves.map(c => h("option", { value: `${c.broj} · ${c.name}` })));
}

function renderNav() {
  const nav = $("#nav");
  const item = (id, label, title, status) => h("button", {
    class: "nav-item" + (S.tab === id ? " active" : ""), onclick: () => setTab(id),
  }, h("span", { class: "nav-label" }, label), title,
     status ? h("span", { class: "dot " + status, title: status }) : null);
  const stages = S.catalog ? S.catalog.stages : [];
  nav.replaceChildren(
    item("home", "⌂", "Pregled"),
    h("div", { class: "nav-sep" }),
    ...stages.map(s => item(s.label, s.label, s.title, s.status)),
  );
}

// ── page ─────────────────────────────────────────────────────────────
function render() {
  const main = $("#main");
  if (!S.summary || !S.catalog) { main.replaceChildren(h("div", { class: "empty" }, "Učitavam…")); return; }
  if (S.tab === "home") return main.replaceChildren(...renderHome());
  const stage = S.catalog.stages.find(s => s.label === S.tab);
  if (!stage) return setTab("home");
  main.replaceChildren(...renderStage(stage));
}

function caveInfo() { return S.caves.find(c => c.broj === S.broj); }

function renderHome() {
  const sum = S.summary;
  const out = [h("div", { class: "page-head" },
    h("div", {}, h("h1", {}, "Pregled"),
      h("div", { class: "sub" }, "Speleo baza, trenutni objekt, mape na Driveu i stanje ovog računala.")))];

  if (sum.settings_error) out.push(h("div", { class: "card note" }, h("b", {}, "Postavke se ne mogu učitati: "), sum.settings_error));

  const grid = h("div", { class: "grid" });
  out.push(grid);

  const sbc = sbCard();
  if (sbc) grid.append(sbc);

  // Current cave
  grid.append(renderCaveCard());

  // Drive dirs
  if (sum.drive_dirs) {
    grid.append(h("div", { class: "card" },
      h("h2", {}, "Mape na Driveu"),
      sum.drive_ok ? null : h("div", { class: "errline" }, "Drive nije dostupan: " + (sum.drive_root || "LOCAL_DRIVE_ROOT nije postavljen")),
      h("div", { class: "row" },
        h("button", { class: "btn", onclick: () => openTarget({ what: "drive-root" }), disabled: !sum.drive_ok }, "Speleo baza SUE"),
        ...sum.drive_dirs.map(d => h("button", {
          class: "btn", disabled: !d.exists, title: d.path || "",
          onclick: () => openTarget({ what: "drive", key: d.key }),
        }, d.label))),
      h("h3", { style: "margin-top:12px" }, "Radni prostor"),
      h("div", { class: "row", style: "margin-top:6px" },
        ...sum.workspace_dirs.map(d => h("button", { class: "btn ghost", onclick: () => openTarget({ what: "workspace", key: d.key }) }, d.label))),
    ));
  }

  // Machine
  grid.append(h("div", { class: "card" },
    h("h2", {}, "Ovo računalo"),
    h("dl", { class: "kv" },
      h("dt", {}, "Radni prostor"), h("dd", { class: "mono" }, sum.workspace || "—"),
      h("dt", {}, "Drive"), h("dd", { class: "mono" }, sum.drive_root || "—"),
      h("dt", {}, "3N alati"), h("dd", { class: "mono" }, sum.tools_dir || h("span", { class: "warnline" }, "nisu pronađeni")),
      h("dt", {}, "cSurvey"), h("dd", { class: "mono" }, sum.csurvey || h("span", { class: "warnline" }, "nije instaliran (C:\\csurvey64)"))),
  ));

  // Intake not yet prefixed
  if (S.unprefixed.length) {
    grid.append(h("div", { class: "card" },
      h("h2", {}, `Mape bez SB_ prefiksa (${S.unprefixed.length})`),
      h("p", { class: "help" }, "Ove mape pod !Za digitalizirat još nisu povezane sa SB redom, pa ih birač objekata ne vidi."),
      h("ul", { class: "muted" }, ...S.unprefixed.slice(0, 8).map(p => h("li", {}, p))),
      h("button", { class: "btn", onclick: () => setTab("1T") }, "Poveži u 1T →"),
    ));
  }

  out.push(h("h3", { class: "group-title" }, "Faze"));
  out.push(h("div", { class: "stagegrid" }, ...S.catalog.stages.map(s => h("button", {
    class: "stagetile", onclick: () => setTab(s.label),
  }, h("div", { class: "t" }, h("span", { class: "nav-label" }, s.label), s.title, h("span", { class: "dot " + s.status })),
     h("div", { class: "s" }, s.subtitle)))));
  return out;
}

function sbCard() {
  const sb = S.summary.sb;
  if (!sb) return null;
  const live = sb.versions.find(v => v.path === sb.live) || null;
  return h("div", { class: "card hl" },
    h("h2", {}, "Speleo baza"),
    h("dl", { class: "kv" },
      h("dt", {}, "Živa"), h("dd", {}, sb.live ? sb.live.split(/[\\/]/).pop() : "—"),
      h("dt", {}, "Izmijenjena"), h("dd", {}, live ? fmtTime(live.modified) : "—"),
      h("dt", {}, "Alati čitaju"), h("dd", {}, h("span", { class: "badge " + sb.mode.toLowerCase() }, sb.mode), " ", sb.reading.split(/[\\/]/).pop())),
    sb.reason ? h("div", { class: "warnline" }, "⚠ " + sb.reason + " — čita se zadnja dobra lokalna kopija.") : null,
    sb.newer_than_live.length ? h("div", { class: "warnline" },
      "⚠ Na Driveu postoji novija verzija nego što config.yaml koristi: " + sb.newer_than_live.join(", ") + " — ažuriraj sb.workbook_filename.") : null,
    h("div", { class: "row" },
      h("button", { class: "btn primary", disabled: !sb.live_exists, onclick: () => openTarget({ what: "sb" }) }, "Otvori SB u Excelu"),
      h("button", { class: "btn", onclick: () => openTarget({ what: "sb", reveal: true }), disabled: !sb.live_exists }, "Pokaži u mapi"),
      sb.reading !== sb.live ? h("button", { class: "btn ghost", onclick: () => openTarget({ what: "sb-reading" }) }, "Otvori kopiju koju alati čitaju") : null),
    h("p", { class: "help" }, "Dok je SB otvoren u Excelu, alati čitaju lokalnu kopiju (FALLBACK). Zatvori Excel prije pokretanja naredbi ako trebaš najsvježije podatke."),
    sb.versions.length > 1 ? h("details", {}, h("summary", { class: "muted" }, `Sve verzije (${sb.versions.length})`),
      h("table", { class: "files" }, ...sb.versions.map(v => h("tr", {},
        h("td", { class: "name" }, v.name), h("td", { class: "kind" }, fmtTime(v.modified)),
        h("td", { class: "act" }, h("button", { class: "btn small", onclick: () => openTarget({ what: "path", path: v.path }) }, "Otvori")))))) : null,
  );
}

function renderCaveCard() {
  if (S.broj === null) {
    return h("div", { class: "card" }, h("h2", {}, "Trenutni objekt"),
      h("p", { class: "help" }, "Odaberi objekt gore desno (Redni broj ili ime). Sve naredbe na karticama tada koriste taj broj."),
      h("p", { class: "muted" }, `${S.caves.length} objekata ima mapu SB_<broj>_… pod !Za digitalizirat.`));
  }
  const d = S.cave;
  const info = caveInfo();
  const card = h("div", { class: "card hl" }, h("h2", {}, `SB ${S.broj}` + (info ? ` · ${info.name}` : "")));
  if (!d) return card;
  if (!d.leaves.length) {
    card.append(h("p", { class: "warnline" }, "Ovaj objekt nema mapu SB_" + S.broj + "_… pod !Za digitalizirat. Naredbe koje trebaju samo broj i dalje rade."));
    return card;
  }
  if (d.leaves.length > 1) card.append(h("p", { class: "warnline" }, `⚠ ${d.leaves.length} mape nose isti broj — datoteke su spojene.`));
  card.append(h("div", { class: "muted mono" }, d.leaves.map(l => l.relative).join("\n")));
  const list = h("ul", { class: "checklist" });
  let next = null;
  for (const [label, test, stage] of CHECKLIST) {
    const ok = test(d);
    if (!ok && !next && stage === "3N") next = label;
    list.append(h("li", {},
      h("span", { class: "tick " + (ok ? "yes" : "no") }, ok ? "✓" : "·"),
      label.replace("<broj>", S.broj),
      h("a", { href: "#", class: "stage-link", onclick: e => { e.preventDefault(); setTab(stage); } }, stage)));
  }
  card.append(list);
  card.append(h("div", { class: "row", style: "margin-top:8px" },
    h("button", { class: "btn", onclick: () => openTarget({ what: "path", path: d.leaves[0].path }) }, "Otvori mapu"),
    h("button", { class: "btn primary", onclick: () => setTab("3N") }, next ? "Nacrt: sljedeći korak →" : "Nacrt →")));
  return card;
}

function renderStage(stage) {
  const out = [h("div", { class: "page-head" },
    h("span", { class: "stage-chip" }, stage.label),
    h("div", {}, h("h1", {}, stage.title), h("div", { class: "sub" }, stage.subtitle)),
    h("div", { class: "spacer" }),
    h("span", { class: "status-pill" }, stage.status),
    h("button", { class: "btn ghost", onclick: () => openTarget({ what: "readme", path: stage.readme }) }, "README"))];
  for (const note of stage.notes) out.push(h("div", { class: "card note" }, note));

  if (stage.label === "6P") { out.push(...renderPredajaMockup()); return out; }
  if (stage.label === "2B") { const c = sbCard(); if (c) out.push(h("div", { class: "grid", style: "margin-bottom:14px" }, c)); }

  const actions = S.catalog.actions.filter(a => a.stage === stage.label);
  const steps = actions.filter(a => a.step);
  const plain = actions.filter(a => !a.step && !a.group);
  const groups = [...new Set(actions.filter(a => !a.step && a.group).map(a => a.group))];

  if (actions.some(a => a.needs_cave) && S.broj === null) {
    out.push(h("div", { class: "card note" }, "Neke naredbe ovdje rade na jednom objektu — odaberi ga gore desno."));
  }
  if (steps.length) {
    out.push(h("div", { class: "steps" }, ...steps.map(a => h("div", { class: "step" + (a.tool === "manual" ? " manual" : "") },
      h("div", { class: "step-tag" }, a.step), a.tool === "manual" ? manualCard(a) : actionCard(a)))));
  }
  if (plain.length) out.push(h("div", { class: "grid", style: steps.length ? "margin-top:18px" : "" }, ...plain.map(actionCard)));
  for (const g of groups) {
    out.push(h("h3", { class: "group-title" }, g));
    out.push(h("div", { class: "grid" }, ...actions.filter(a => !a.step && a.group === g).map(actionCard)));
  }
  const kinds = STAGE_FILES[stage.label];
  if (kinds && S.cave && S.cave.leaves.length) out.push(h("h3", { class: "group-title" }, "Datoteke objekta"), filesCard(kinds));
  if (stage.label === "4I" && S.cave && S.cave.karta) {
    const k = S.cave.karta;
    out.push(h("h3", { class: "group-title" }, "Isječak ovog objekta"), h("div", { class: "card" },
      k.exists ? h("div", { class: "row" }, "✓ " + k.path.split(/[\\/]/).pop(),
        h("button", { class: "btn small", onclick: () => openTarget({ what: "path", path: k.path }) }, "Otvori"))
        : h("span", { class: "muted" }, "Još nema isječka za ovaj objekt.")));
  }
  return out;
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
        newest ? "Otvori " + newest.name + " u cSurveyu" : "Nema datoteke za ovaj korak"),
      S.cave && S.cave.leaves.length ? h("button", { class: "btn ghost", onclick: () => openTarget({ what: "path", path: S.cave.leaves[0].path }) }, "Mapa objekta") : null));
}

function quote(a) { return a === "" || /\s/.test(a) ? `"${a}"` : a; }

function actionCard(a) {
  const card = h("div", { class: "card" });
  const vals = {};
  for (const o of a.options) vals[o.flag] = o.default;
  const info = caveInfo();
  let query = info ? shortName(info.name) : "";
  let file = null;

  const preview = h("code", { class: "cmd" });
  const runBtn = h("button", { class: "btn primary" }, "Pokreni");
  const writesTag = h("span", { class: "writes-tag" });

  const argsFor = () => {
    const args = [];
    for (let t of a.args) {
      t = t.replace("{broj}", S.broj ?? "<broj>").replace("{file}", file || "<datoteka>").replace("{query}", query || "<ime>");
      args.push(t);
    }
    for (const o of a.options) {
      const v = vals[o.flag];
      if (o.kind === "flag") { if (v) args.push(o.flag); }
      else if (v !== "" && v !== null && v !== undefined && v !== false) args.push(o.flag, String(v));
    }
    return args;
  };
  const writes = () => {
    const ticked = a.options.filter(o => o.kind === "flag" && vals[o.flag]);
    if (a.writes && !ticked.some(o => o.safe)) return a.writes;
    if (a.unsafe_writes && ticked.some(o => o.unsafe)) return a.unsafe_writes;
    return null;
  };
  const cmdText = () => (a.tool === "cli" ? "cavedossier " : `python $T\\${a.tool} `) + argsFor().map(quote).join(" ");
  const missing = () => {
    if (a.args.some(t => t.includes("{broj}") || t.includes("{file}")) && S.broj === null) return "Odaberi objekt.";
    if (a.file_kind && !file) return "Nema odgovarajuće datoteke u mapi objekta.";
    if (a.args.some(t => t.includes("{query}")) && !query.trim()) return "Upiši ime objekta.";
    return null;
  };
  const refresh = () => {
    preview.textContent = cmdText();
    const w = writes();
    writesTag.textContent = w ? "piše" : "";
    writesTag.style.display = w ? "" : "none";
    writesTag.title = w || "";
    runBtn.className = "btn " + (w ? "warn" : "primary");
    runBtn.textContent = w ? "Pokreni…" : "Pokreni";
    const m = missing();
    runBtn.disabled = !!m;
    runBtn.title = m || "";
  };

  card.append(h("div", { class: "action-head" }, h("h3", {}, a.title), writesTag));
  if (a.help) card.append(h("p", { class: "help" }, a.help));

  if (a.file_kind) {
    const files = candidates(a.file_kind);
    file = files[0] ? files[0].path : null;
    const sel = h("select", { onchange: e => { file = e.target.value; refresh(); } },
      ...files.map(f => h("option", { value: f.path }, `${f.relative}  ·  ${fmtTime(f.modified)}`)));
    const openBtn = h("button", { class: "btn small ghost", title: "Otvori odabranu datoteku u cSurveyu",
      onclick: () => file && openTarget({ what: "csurvey", path: file }) }, "cSurvey");
    card.append(h("label", { class: "field" }, h("span", {}, "Datoteka"),
      files.length ? h("div", { class: "cmd-row" }, sel, openBtn)
        : h("span", { class: "muted" }, S.broj === null ? "— odaberi objekt —" : "— nema datoteke za ovaj korak u mapi objekta —")));
  }
  if (a.args.some(t => t.includes("{query}"))) {
    card.append(h("label", { class: "field" }, h("span", {}, "Objekt (ime, SUE broj ili broj pločice)"),
      h("input", { type: "text", value: query, oninput: e => { query = e.target.value; refresh(); } })));
  }
  if (a.options.length) {
    const opts = h("div", { class: "opts" });
    for (const o of a.options) {
      if (o.kind === "flag") {
        opts.append(h("label", { class: "check", title: o.help || o.flag },
          h("input", { type: "checkbox", checked: !!o.default, onchange: e => { vals[o.flag] = e.target.checked; refresh(); } }), o.label));
      } else if (o.kind === "choice") {
        opts.append(h("label", { class: "opt-inline", title: o.help || o.flag }, o.label,
          h("select", { onchange: e => { vals[o.flag] = e.target.value; refresh(); } },
            ...o.choices.map(c => h("option", { value: c, selected: c === o.default }, c)))));
      } else {
        opts.append(h("label", { class: "opt-inline", title: o.help || o.flag }, o.label,
          h("input", { type: o.kind === "int" ? "number" : "text", value: o.default || "",
            style: o.kind === "text" ? "width:160px" : "", oninput: e => { vals[o.flag] = e.target.value; refresh(); } })));
      }
    }
    card.append(opts);
  }
  const copyBtn = h("button", { class: "btn small ghost", title: "Kopiraj naredbu za terminal",
    onclick: () => copy(cmdText()) }, "Kopiraj");
  card.append(h("div", { class: "cmd-row" }, preview, copyBtn));
  runBtn.addEventListener("click", () => runAction(a, { file, query, vals, writes: writes(), cmd: cmdText() }));
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
function confirmRun(a, writes, cmd) {
  if (S.remember.has(a.id)) return Promise.resolve(true);
  const dlg = $("#confirm");
  $("#confirm-title").textContent = a.title;
  $("#confirm-text").textContent = "Ova radnja " + writes + ".";
  $("#confirm-cmd").textContent = cmd;
  $("#confirm-remember").checked = false;
  return new Promise(resolve => {
    dlg.addEventListener("close", () => {
      const ok = dlg.returnValue === "ok";
      if (ok && $("#confirm-remember").checked) S.remember.add(a.id);
      resolve(ok);
    }, { once: true });
    dlg.showModal();
  });
}

async function runAction(a, ctx) {
  if (ctx.writes && !(await confirmRun(a, ctx.writes, ctx.cmd))) return;
  const options = {};
  for (const [k, v] of Object.entries(ctx.vals)) options[k] = v;
  try {
    const job = await api("run", {
      action: a.id, broj: S.broj, file: ctx.file, query: ctx.query, options, confirmed: !!ctx.writes,
    });
    addJob(job);
  } catch (e) { toast(e.message, true); }
}

function addJob(job) {
  S.jobs.set(job.id, { ...job, text: job.text });
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
  if (S.broj !== null) loadCave();
}

function renderJobs() {
  const tabs = $("#job-tabs");
  const list = [...S.jobs.values()].sort((a, b) => b.id - a.id);
  $("#console-count").textContent = list.length ? `(${list.filter(j => j.running).length} radi / ${list.length})` : "";
  tabs.replaceChildren(...list.map(j => h("button", {
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
  const c = $("#console");
  c.classList.remove("collapsed");
  $("#console-toggle").firstChild.textContent = "▾ Ispis ";
}

// ── wiring ───────────────────────────────────────────────────────────
function parseCave(text) {
  const m = String(text).trim().match(/^(?:SB_?)?(\d{1,4})\b/i);
  if (m) return parseInt(m[1], 10);
  const needle = text.trim().toLowerCase();
  if (!needle) return null;
  const hit = S.caves.find(c => c.name.toLowerCase().includes(needle));
  return hit ? hit.broj : undefined;
}

function wire() {
  const input = $("#cave-input");
  const pick = () => {
    const broj = parseCave(input.value);
    if (broj === undefined) return toast("Nema takvog objekta među mapama.", true);
    if (broj !== S.broj) setCave(broj);
  };
  input.addEventListener("change", pick);
  input.addEventListener("keydown", e => { if (e.key === "Enter") pick(); });
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
    else { c.classList.remove("tall"); c.classList.add("collapsed"); $("#console-toggle").firstChild.textContent = "▸ Ispis "; }
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
    if (S.broj !== null) {
      const info = caveInfo();
      $("#cave-input").value = info ? `${S.broj} · ${info.name}` : String(S.broj);
    }
    const jobs = await api("jobs");
    for (const j of jobs.jobs.reverse()) {
      const full = await api(`job/${j.id}?since=0`);
      S.jobs.set(j.id, full);
      S.activeJob = j.id;
    }
    renderJobs();
    poll();
  } catch (e) {
    $("#main").replaceChildren(h("div", { class: "card note" }, "Ne mogu dohvatiti podatke sa servera: " + e.message));
  }
})();
