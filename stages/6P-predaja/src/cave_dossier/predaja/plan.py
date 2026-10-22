"""The last gate: is this cave finished, and what exactly would delivery do?

``build_plan`` is read-only. It answers both questions at once, because the
archivist's review is one question to them: *here is everything, here is what
the click will change — do you confirm?* The CLI dry run prints the plan; the
dashboard's 6P page draws it with every document openable; ``apply.py``
executes it and nothing else.

Checks (each a blocker unless marked as a warning):

- the SB row exists, has no katastarski broj yet (or the delivery is being
  resumed under the number it already got), and SB is read LIVE — a fallback
  copy can lag the live workbook, so the plan it gives is not one to act on;
- the SUE gate (``gate.py``): the SB cells the society needs, a Dubina in SB
  or the zapisnik, and Protokol §5.1 coordinates + pločica. **No izjava** —
  that is CroSpeleo's (5D), the next gate, shown here only as information;
- exactly one intake leaf, no document in it open in Word/Excel;
- the OSZ is there, readable as v10, with no obligatory SUE field empty
  (``osz provjera``), and its Katastarski broj cell empty or already this number;
- the Nacrt PDF is there and its *Katastarski broj* cell can be found
  (``stamp.check_pdf``); a Nacrt older than the OSZ is a **warning**;
- at least one processed entrance photo (``photos process``) — the archive
  never receives a field original; photos still in the queue are a **warning**;
- the number: ``max + 1`` over a dense column (``max == count``, no
  duplicates). A hand-given ``--katastarski-broj`` must be free;
- no archive target exists already: a taken ``<broj>.pdf`` means the number is
  wrong, which is a stop, never a merge.

SB precedence holds even here: the plan only FILLS empty cells (Duljina,
Dubina from the zapisnik) and changes exactly the three cells delivery owns
(Katastarski broj SUE, Napomena, Fotografija ulaza). ``Link Nacrt``, ``Link
Zapisnik`` and ``Godina zadnjeg istraživanja`` are formulas over the number
(measured on the live SB 2026-10-22) and are never written.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from cave_dossier.core.config import Settings
from cave_dossier.core.matching import SB_SERIAL_RE, sanitize_for_filename
from cave_dossier.predaja.stamp import number_text

#: The numbered rows' Napomena convention (live SB 2026-10-22: 768 of 901
#: numbered rows read "ok", most of the rest "ok, <note>").
NAPOMENA_DONE = "ok"
FOTO_YES = "DA"

#: config.yaml ``archive`` key of the archived-leaf folder, and its default.
ARHIVA_KEY = "arhiva_dir"
ARHIVA_DEFAULT = "!!!Digitalizacija/Arhiva"

RUNS = ("runs", "predaja")


@dataclass
class Issue:
    severity: str          # "blocker" | "warning"
    text: str


@dataclass
class FileMove:
    kind: str              # "osz" | "nacrt" | "foto" | "leaf"
    src: str
    dst: str
    #: written with the number in it (OSZ cell, Nacrt title block)
    stamp: bool = False
    #: already at its destination from an earlier, interrupted run
    done: bool = False


@dataclass
class CellChange:
    column: str
    before: object
    after: object
    why: str


@dataclass
class DeliveryPlan:
    serial: int
    name: str = ""
    #: ready · blocked · delivered · resume
    state: str = "blocked"
    sue: int | None = None
    #: proposed · override · existing
    sue_source: str = ""
    sequence: dict = field(default_factory=dict)
    sb_mode: str = ""
    sb_row: int | None = None
    leaf: str | None = None
    #: What the archivist checks, as openable paths (see ``to_json``).
    material: dict = field(default_factory=dict)
    moves: list[FileMove] = field(default_factory=list)
    sb_changes: list[CellChange] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    #: The dossier view (5D ``report.to_view``) — gates, people, the SB row.
    dossier: dict | None = None

    @property
    def blockers(self) -> list[str]:
        return [i.text for i in self.issues if i.severity == "blocker"]

    @property
    def warnings(self) -> list[str]:
        return [i.text for i in self.issues if i.severity == "warning"]

    @property
    def ready(self) -> bool:
        return self.state in ("ready", "resume") and not self.blockers

    def block(self, text: str) -> None:
        self.issues.append(Issue("blocker", text))

    def warn(self, text: str) -> None:
        self.issues.append(Issue("warning", text))

    def to_json(self) -> dict:
        data = asdict(self)
        data["ready"] = self.ready
        data["blockers"] = self.blockers
        data["warnings"] = self.warnings
        data["sue_text"] = number_text(self.sue) if self.sue else None
        return data


# ── pure helpers (tested directly) ──────────────────────────────────


def sequence_stats(values) -> dict:
    """The Katastarski broj SUE column as numbers: max, count, duplicates, gaps.

    Measured dense 1…885 on 2026-09-02 and 1…901 on 2026-10-22, so
    ``max == count`` is a real invariant — a cheap corruption check.
    """
    numbers: list[int] = []
    odd: list[str] = []
    for value in values:
        if value is None or (isinstance(value, float) and value != value) or str(value).strip() == "":
            continue
        try:
            number = float(str(value).strip().replace(",", "."))
        except ValueError:
            odd.append(str(value))
            continue
        if not number.is_integer():
            odd.append(str(value))
            continue
        numbers.append(int(number))
    top = max(numbers) if numbers else 0
    seen = set(numbers)
    return {
        "max": top,
        "count": len(numbers),
        "duplicates": sorted({n for n in numbers if numbers.count(n) > 1}) if len(seen) != len(numbers) else [],
        "gaps": sorted(set(range(1, top + 1)) - seen)[:20],
        "odd": odd[:10],
        "taken": seen,
    }


def allocate(stats: dict, override: int | None = None) -> tuple[int | None, str, list[Issue]]:
    """(number, source, issues): ``max + 1`` when the column is dense, or the
    hand-given number when it is free."""
    issues: list[Issue] = []
    dense = not stats["duplicates"] and not stats["gaps"] and not stats["odd"]
    if override is not None and dense and override == stats["max"] + 1:
        return override, "proposed", issues     # the proposal, confirmed
    if override is not None:
        if override < 1:
            return None, "override", [Issue("blocker", f"Katastarski broj {override} nije valjan.")]
        if override in stats["taken"]:
            return None, "override", [Issue("blocker", f"Katastarski broj {override} je već zauzet u SB-u.")]
        if override != stats["max"] + 1:
            issues.append(Issue("warning", f"{override} nije sljedeći broj (sljedeći je {stats['max'] + 1})."))
        return override, "override", issues
    if not dense:
        parts = []
        if stats["duplicates"]:
            parts.append("dvostruki: " + ", ".join(map(str, stats["duplicates"][:10])))
        if stats["gaps"]:
            parts.append("rupe: " + ", ".join(map(str, stats["gaps"][:10])))
        if stats["odd"]:
            parts.append("nečitljivo: " + ", ".join(stats["odd"][:5]))
        return None, "proposed", [Issue("blocker", "Niz katastarskih brojeva u SB-u nije uredan ("
                                         + "; ".join(parts) + ") – netko je usred dodjele ili je broj "
                                         "obrisan. Uredi SB ili zadaj broj ručno.")]
    return stats["max"] + 1, "proposed", issues


def napomena_after(before: str | None, queue_note: str | None, queued: bool) -> tuple[str | None, str | None]:
    """(new Napomena or None when unchanged, warning or None).

    The *Za istražit* view is ``Napomena`` containing ``za istražit``, the
    *Istraženi* view is ``Katastarski broj SUE`` not empty: writing only the
    number would put the row in both. The queue flag becomes the numbered
    rows' own ``ok`` (keeping the flag's note after a comma, like the 35
    ``ok, sudjelovanje`` rows); any other text is left alone and reported.
    """
    text = (before or "").strip()
    if queued:
        note = (queue_note or "").strip()
        return (f"{NAPOMENA_DONE}, {note}" if note else NAPOMENA_DONE), None
    if not text:
        return NAPOMENA_DONE, None
    if text.lower() == NAPOMENA_DONE or text.lower().startswith(NAPOMENA_DONE + ","):
        return None, None
    return None, (f"Napomena ostaje '{text}' (nije oznaka reda čekanja ni 'ok') – "
                  "uskladi je ručno ako treba.")


def _number(text) -> float | None:
    if text is None:
        return None
    cleaned = re.sub(r"[^\d,.\-]", "", str(text)).replace(",", ".").lstrip("-")
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


def _excel_number(value: float):
    return int(value) if float(value).is_integer() else value


def photo_target(name: str, serial: int, sue: int) -> str:
    """``SB_1234_Ime_LKukuljan_1.jpg`` -> ``886_Ime_LKukuljan_1.jpg``."""
    return re.sub(rf"^SB_0*{serial}_", number_text(sue) + "_", name, flags=re.IGNORECASE)


# ── the plan ────────────────────────────────────────────────────────


def build_plan(settings: Settings, serial: int, *, override: int | None = None,
               reader=None) -> DeliveryPlan:
    """Everything delivery would do for this cave, and why it may not."""
    from cave_dossier.dossier.assemble import assemble
    from cave_dossier.dossier.report import to_view
    from cave_dossier.dossier.sb_mapper import parse_queue_flag
    from cave_dossier.georef import find_by_serial
    from cave_dossier.sb.loader import SBReader

    plan = DeliveryPlan(serial=serial, sb_mode=settings.sb_mode)
    reader = reader or SBReader(settings)
    cave = find_by_serial(reader, settings, serial)
    if cave is None:
        plan.block(f"Nijedan SB red nema Redni broj {serial}.")
        return plan
    plan.name = cave.object_name or ""
    plan.sb_row = cave.row_number
    if settings.sb_mode == "FALLBACK":
        plan.block("SB se čita iz lokalne kopije (živi SB nije dostupan ili je otvoren u Excelu: "
                   f"{settings.sb_mode_reason}). Zatvori ga i osvježi – predaja piše u živi SB.")

    sue_column = settings.sb_archive_reference_column or "Katastarski broj SUE"
    frame = reader.load_rows()
    stats = sequence_stats(frame[sue_column].tolist() if sue_column in frame.columns else [])
    plan.sequence = {k: v for k, v in stats.items() if k != "taken"}
    existing = _number(cave.sue_number)

    leaves = intake_leaves(settings, serial)
    if existing is not None and not leaves:
        plan.state, plan.sue, plan.sue_source = "delivered", int(existing), "existing"
        plan.material = archived_material(settings, int(existing), plan.name)
        plan.notes.append(f"Objekt je već predan pod katastarskim brojem {number_text(int(existing))}.")
        return plan

    if existing is not None:
        plan.sue, plan.sue_source = int(existing), "existing"
        if override is not None and override != existing:
            plan.block(f"SB već ima katastarski broj {int(existing)} – ne dodjeljujem {override}.")
    else:
        number, source, issues = allocate(stats, override)
        plan.sue, plan.sue_source = number, source
        plan.issues.extend(issues)

    # The dossier (5D) is shown for its people, izjave and SB row. Its verdict
    # is CroSpeleo's, the NEXT gate, so it is information here, never a
    # blocker: the SUE gate is gate.py + the leaf checks below (user,
    # 2026-10-22 – izjave are a CroSpeleo requirement, not a SUE one).
    dossier = assemble(settings, cave)
    plan.dossier = to_view(dossier)
    cro = dossier.readiness
    plan.notes.append("CroSpeleo (5D, idući prag, ne priječi predaju): "
                      + ("spreman." if cro.ready else f"{len(cro.blockers)} blokera – vidi karticu 5D."))
    queue = parse_queue_flag(_cell(cave, settings.sb_field_columns.get("note", "Napomena")))

    # ── the leaf ─────────────────────────────────────────────────────
    if not leaves:
        plan.block(f"Objekt nema mapu SB_{serial}_… pod !Za digitalizirat – nema što predati.")
        return plan
    if len(leaves) > 1:
        plan.block("Više mapa za isti Redni broj: " + ", ".join(p.name for p in leaves)
                   + " – spoji ih u jednu.")
        return plan
    leaf = leaves[0]
    plan.leaf = str(leaf)
    locks = [p.name for p in leaf.rglob("~$*")]
    if locks:
        plan.block("Dokument iz mape je otvoren (" + ", ".join(locks) + ") – zatvori Word/Excel.")
    material = leaf_material(settings, leaf, serial)
    plan.material = material

    # ── OSZ ──────────────────────────────────────────────────────────
    osz = material.get("osz")
    recorded: dict = {}
    ticked: tuple = ()
    if not osz:
        plan.block(f"U mapi nema OSZ-a (SB_{serial:04d}_OSZ.docx) – Pripremi OSZ i popuni ga.")
    else:
        try:
            from cave_dossier.osz import provjera
            from cave_dossier.osz.reader import read_osz_content

            content = read_osz_content(Path(osz["path"]))
            recorded, ticked = content.fields, tuple(content.ticked)
            check = provjera.check_content(content.fields, content.ticked)
            material["osz"]["check"] = check.to_json()
            sue_gaps = [g.label for g in check.missing if "SUE" in g.needed_by]
            if sue_gaps:
                plan.block("OSZ: prazna obvezna polja – " + ", ".join(sue_gaps) + ".")
            other = [g.label for g in check.missing if "SUE" not in g.needed_by and "3N" in g.needed_by]
            if other:
                plan.warn("OSZ: prazno (traži ih sastavnica nacrta) – " + ", ".join(other) + ".")
            held = (content.fields.get("katastarski_broj") or "").strip()
            if held and plan.sue and _number(held) != plan.sue:
                plan.block(f"OSZ već ima katastarski broj '{held}', a predaja bi upisala {plan.sue}.")
        except Exception as exc:  # noqa: BLE001 — a blocker, never a crash
            plan.block(f"OSZ se ne može pročitati kao v10 zapisnik ({type(exc).__name__}: {exc}) – "
                       f"pokreni osz prefill {serial}, koji ga migrira.")

    # ── the SUE gate: SB fields, Dubina, §5.1 coordinates + pločica ─
    from cave_dossier.predaja.gate import sue_issues

    for severity, text in sue_issues(dossier, recorded, ticked):
        (plan.block if severity == "blocker" else plan.warn)(text)

    # ── Nacrt ────────────────────────────────────────────────────────
    nacrt = material.get("nacrt")
    if not nacrt:
        plan.block(f"U mapi nema nacrta (SB_{serial:04d}_nacrt.pdf) – 3N KORAK 3c ili Illustrator.")
    else:
        from cave_dossier.predaja.stamp import check_pdf

        pdf = check_pdf(Path(nacrt["path"]), plan.sue)
        material["nacrt"]["stamp"] = {"status": pdf.status, "note": pdf.note,
                                      "illustrator": pdf.illustrator}
        if not pdf.ok:
            plan.block("Nacrt: " + pdf.note)
        if osz and nacrt["modified"] + 1 < _osz_compose_mtime(osz, serial):
            plan.warn("Nacrt je stariji od OSZ-a – ako se zapisnik mijenjao nakon slaganja, "
                      "složi nacrt ponovno (3N KORAK 3c) da sastavnica bude ista.")

    # ── photos ───────────────────────────────────────────────────────
    photos = material.get("photos") or []
    if not photos:
        plan.block("Nema obrađene fotografije ulaza (SB_<broj>_…jpg) – pokreni Obradi fotografije (4F).")
    if material.get("originals"):
        plan.warn(f"{len(material['originals'])} neobrađenih originala ide samo u Arhivu, "
                  "ne u !!Fotografije ulaza.")
    if material.get("queued"):
        plan.warn(f"{len(material['queued'])} fotografija ovog objekta još čeka u redu "
                  "(…za istražit) – povuci ih i obradi prije predaje.")

    if plan.sue is None:
        return plan

    # ── where everything goes ───────────────────────────────────────
    _plan_moves(settings, plan, leaf, material)
    _plan_sb(settings, plan, cave, recorded, queue, bool(photos))
    if plan.sue_source == "existing":
        plan.state = "resume"
        plan.notes.append(f"SB već ima broj {number_text(plan.sue)} – nastavljam prekinutu predaju "
                          "pod tim brojem (SB se mijenja samo gdje se razlikuje).")
    else:
        plan.state = "ready"
    if plan.blockers:
        plan.state = "blocked"
    return plan


def _cell(cave, column: str | None) -> str | None:
    if not column:
        return None
    from cave_dossier.sb.loader import SBReader

    return SBReader._cell_as_text(cave.values, column)


def _osz_compose_mtime(osz: dict, serial: int) -> float:
    """The OSZ's mtime as the nacrt saw it: a KORAK 4 write of the measured
    cells (its sidecar says when) does not count — the same rule the
    dashboard's workflow uses for 3c."""
    try:
        from cave_dossier.osz import backfill

        last = backfill.last_write(serial) or {}
        after, before = last.get("osz_mtime_after"), last.get("osz_mtime_before")
        if after and before and abs(osz["modified"] - float(after)) <= 2:
            return float(before)
    except Exception:  # noqa: BLE001
        pass
    return osz["modified"]


def _plan_moves(settings: Settings, plan: DeliveryPlan, leaf: Path, material: dict) -> None:
    sue = plan.sue
    done = set(previous_manifest(sue).get("done_dst", []))
    root = settings.local_drive_root

    def target(key: str, name: str) -> Path | None:
        if root is None or key not in settings.archive_dirs:
            plan.block(f"Mapa arhive '{key}' nije podešena (config.yaml archive).")
            return None
        directory = root / settings.archive_dirs[key]
        if not directory.is_dir():
            plan.block(f"Mapa arhive ne postoji: {directory}")
            return None
        return directory / name

    def add(kind: str, src: str, dst: Path | None, stamp: bool = False) -> None:
        if dst is None:
            return
        already = str(dst) in done and dst.exists()
        if dst.exists() and not already:
            plan.block(f"{dst.parent.name}\\{dst.name} već postoji – broj {number_text(sue)} je "
                       "zauzet u arhivi. Ništa se ne prepisuje.")
        plan.moves.append(FileMove(kind, src, str(dst), stamp, already))

    if material.get("osz"):
        add("osz", material["osz"]["path"], target("osz_dir", f"{number_text(sue)}.docx"), True)
    if material.get("nacrt"):
        add("nacrt", material["nacrt"]["path"], target("drawings_dir", f"{number_text(sue)}.pdf"), True)
    for photo in material.get("photos") or []:
        add("foto", photo["path"], target("entry_photos_dir", photo_target(photo["name"], plan.serial, sue)))
    arhiva = arhiva_dir(settings)
    if arhiva is None or not arhiva.is_dir():
        plan.block(f"Mapa Arhiva ne postoji: {arhiva}")
    else:
        dst = arhiva / f"{number_text(sue)}_{sanitize_for_filename(plan.name) or 'objekt'}"
        if dst.exists():
            plan.block(f"Arhiva\\{dst.name} već postoji – ništa se ne prepisuje.")
        plan.moves.append(FileMove("leaf", str(leaf), str(dst)))


def _plan_sb(settings: Settings, plan: DeliveryPlan, cave, recorded: dict, queue,
             has_photo: bool) -> None:
    cols = settings.sb_field_columns
    sue_col = settings.sb_archive_reference_column or "Katastarski broj SUE"
    before_sue = _number(cave.sue_number)
    if before_sue != plan.sue:
        plan.sb_changes.append(CellChange(sue_col, cave.sue_number, plan.sue, "katastarski broj – predaja"))
    note_col = cols.get("note", "Napomena")
    before_note = _cell(cave, note_col)
    after_note, warning = napomena_after(before_note, queue.note, queue.queued)
    if warning:
        plan.warn(warning)
    if after_note is not None:
        plan.sb_changes.append(CellChange(note_col, before_note, after_note,
                                          "red čekanja → istraženo" if queue.queued else "istraženo"))
    foto_col = cols.get("entrance_photo_flag", "Fotografija ulaza")
    before_foto = _cell(cave, foto_col)
    if has_photo and (before_foto or "").strip().upper() != FOTO_YES:
        plan.sb_changes.append(CellChange(foto_col, before_foto, FOTO_YES, "fotografija ulaza predana"))
    # SB wins: the zapisnik's numbers only FILL an empty cell.
    for key, osz_key in (("length_m", "duljina"), ("depth_m", "dubina")):
        column = cols.get(key)
        if not column:
            continue
        sb_value = _number(_cell(cave, column))
        osz_value = _number(recorded.get(osz_key))
        if osz_value is None:
            continue
        if sb_value is None:
            plan.sb_changes.append(CellChange(column, None, _excel_number(osz_value), "iz OSZ-a (prazno u SB-u)"))
        elif round(sb_value, 1) != round(osz_value, 1):
            plan.warn(f"{column}: SB {_excel_number(sb_value)}, OSZ {_excel_number(osz_value)} – SB ostaje "
                      "(SB ima prednost); uskladi ručno ako je izmjera točnija.")


# ── files ───────────────────────────────────────────────────────────


def intake_leaves(settings: Settings, serial: int) -> list[Path]:
    """Every intake leaf named ``SB_<broj>_…`` (padded or not)."""
    from cave_dossier.intake.scanner import find_leaf_folders

    root = settings.local_drive_root
    if root is None or "intake_dir" not in settings.archive_dirs:
        return []
    intake = root / settings.archive_dirs["intake_dir"]
    found = []
    for leaf in find_leaf_folders(intake, settings.intake_ignore_folders):
        match = SB_SERIAL_RE.match(leaf.path.name)
        if match and not leaf.ignored and int(match.group(1)) == serial:
            found.append(leaf.path)
    return found


def _file(path: Path) -> dict:
    stat = path.stat()
    return {"name": path.name, "path": str(path), "modified": stat.st_mtime, "size": stat.st_size}


def leaf_material(settings: Settings, leaf: Path, serial: int) -> dict:
    """What the archivist opens: the documents, the photos, the map excerpt."""
    from cave_dossier.osz.dopune import pick_osz_docx
    from cave_dossier.photos.matcher import list_photos
    from cave_dossier.photos.process import source_photos, staged_for_cave

    material: dict = {"leaf": str(leaf), "leaf_name": leaf.name}
    osz, _pool = pick_osz_docx(leaf)
    material["osz"] = _file(osz) if osz else None
    nacrti = sorted((p for p in leaf.iterdir() if p.is_file() and p.name.lower().endswith("_nacrt.pdf")
                     and not p.name.startswith("~$")), key=lambda p: p.stat().st_mtime, reverse=True)
    material["nacrt"] = _file(nacrti[0]) if nacrti else None
    if len(nacrti) > 1:
        material["nacrt_others"] = [p.name for p in nacrti[1:]]
    sastavnice = [p for p in leaf.iterdir() if p.is_file() and p.name.lower().endswith("_sastavnica.pdf")]
    material["sastavnica"] = _file(sastavnice[0]) if sastavnice else None
    processed = re.compile(rf"^SB_0*{serial}_.+\.jpe?g$", re.IGNORECASE)
    material["photos"] = [_file(p) for p in list_photos(leaf) if processed.match(p.name)]
    originals, _ignored = source_photos(leaf, serial, settings.photo_ignore_names)
    material["originals"] = [_file(p) for p in originals]
    try:
        material["queued"] = [_file(p) for p in staged_for_cave(settings, serial)]
    except Exception:  # noqa: BLE001 — the queue is a warning, never a crash
        material["queued"] = []
    excerpts = settings.archive_dirs.get("map_excerpts_dir")
    if settings.local_drive_root and excerpts:
        png = settings.local_drive_root / excerpts / f"SB_{serial:04d}.png"
        material["karta"] = _file(png) if png.is_file() else None
    material["files"] = sorted(p.name for p in leaf.rglob("*") if p.is_file())
    return material


def archived_material(settings: Settings, sue: int, name: str) -> dict:
    """Where a delivered cave's files are (and which are missing)."""
    root = settings.local_drive_root
    out: dict = {"archived": True}
    if root is None:
        return out
    text = number_text(sue)
    for key, archive_key, filename in (("osz", "osz_dir", f"{text}.docx"),
                                       ("nacrt", "drawings_dir", f"{text}.pdf")):
        path = root / settings.archive_dirs.get(archive_key, "") / filename
        out[key] = _file(path) if path.is_file() else None
    photos_dir = root / settings.archive_dirs.get("entry_photos_dir", "")
    try:
        out["photos"] = [_file(p) for p in sorted(photos_dir.glob(f"{text}_*"))]
    except OSError:
        out["photos"] = []
    arhiva = arhiva_dir(settings)
    if arhiva is not None and arhiva.is_dir():
        leaves = sorted(arhiva.glob(f"{text}_*"))
        out["leaf"] = str(leaves[0]) if leaves else None
    return out


def arhiva_dir(settings: Settings) -> Path | None:
    if settings.local_drive_root is None:
        return None
    return settings.local_drive_root / settings.archive_dirs.get(ARHIVA_KEY, ARHIVA_DEFAULT)


def run_dir(sue: int) -> Path:
    from cave_dossier.core.paths import workspace

    return workspace(*RUNS, number_text(sue))


def previous_manifest(sue: int | None) -> dict:
    """The last apply's manifest for this number (resume knows what is done)."""
    if not sue:
        return {}
    try:
        return json.loads((run_dir(sue) / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
