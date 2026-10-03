"""One cave's work as a dependency graph: what is done, what is stale, what is next.

The stages are not a straight line for one cave (user, 2026-10-02). The OSZ
needs Duljina/Dubina, which only the 3N survey measures; the composed Nacrt
needs the filled OSZ (its title block reads the zapisnik). So whichever of the
two is done first, the other one has to be refreshed after it. A fixed order
cannot express that, but a graph of **artifacts and their inputs** can. Each
step below names the files it produces and the files it reads. A step whose
output is older than one of its inputs (or disagrees with it) is **stale**,
and the page offers the action that refreshes it. That is the whole "postfill"
mechanism: no separate tool, just re-running the step whose inputs moved.

The order below is the recommended working order. It reflects the real
dependencies, not the stage labels: the automatic steps (karta, OSZ prefill)
first, then the two pieces of human work that can run in parallel (filling
the OSZ, drawing in cSurvey), then the merge, then photos and checks.

Everything is read from file names, modification times and, for the OSZ, the
v10 cells themselves. Nothing is written. Unreadable input becomes a note,
never an error.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

#: OSZ cells only a person fills (the prefill never writes them). Any of them
#: filled means someone has worked on the zapisnik.
HUMAN_OSZ_FIELDS = ("opis", "datum_istrazivanja", "zapisnicar", "clanovi_ekipe",
                    "perspektiva", "geologija", "crtali", "mjerili")

#: OSZ cells the 3N dimensions file answers (4O `osz prefill`, 2026-10-02).
MEASURED_OSZ_FIELDS = ("duljina", "dubina")
#: ...and the entrance cells it answers since 2026-10-03 (project 0005) - only
#: expected when the finisher witnessed the entrance (a sign or a surface leg);
#: an unmarked entrance never fills them, so it must not keep the step "todo".
ENTRANCE_OSZ_FIELDS = ("sirina_ulaza", "visina_duljina_ulaza")

PHASES = (
    ("priprema", "Priprema"),
    ("auto", "Automatski – može odmah"),
    ("rucno", "Ručni rad – paralelno"),
    ("spajanje", "Spajanje – kad su oba gotova"),
    ("zavrsno", "Završno"),
)


@dataclass
class Step:
    id: str
    phase: str
    label: str
    stage: str
    #: done · stale · todo · blocked · optional · unknown · planned
    status: str
    note: str = ""
    action: str | None = None
    current: bool = False
    files: list[str] = field(default_factory=list)
    #: A file the step's work happens in (the OSZ for "fill it in Word") —
    #: the page offers to open it.
    open: str | None = None
    #: Options the step's button ticks when it runs the action (the queue pull
    #: is meant to move, so it carries --apply; the confirm still asks).
    preset: dict = field(default_factory=dict)


def _newest(files: list[dict], *kinds: str) -> dict | None:
    chosen = [f for f in files if f["kind"] in kinds]
    return max(chosen, key=lambda f: f["modified"]) if chosen else None


def _older(output: dict | None, *inputs: dict | None) -> list[dict]:
    """The inputs that changed after ``output`` was made (1 s Drive slack)."""
    if output is None:
        return []
    return [i for i in inputs if i is not None and i["modified"] > output["modified"] + 1]


def _names(*files: dict | None) -> list[str]:
    return [f["name"] for f in files if f is not None]


def read_osz(path: str | None) -> tuple[dict | None, str]:
    """The OSZ's v10 cells, or (None, why) — lxml is an optional extra."""
    if not path:
        return None, ""
    try:
        from cave_dossier.osz.reader import read_osz_content

        return read_osz_content(Path(path)).fields, ""
    except Exception as exc:  # noqa: BLE001 — a note on the page, never a crash
        return None, f"OSZ se ne može pročitati ({type(exc).__name__})"


def _number(text: str | None) -> float | None:
    if not text:
        return None
    cleaned = str(text).replace(",", ".").replace("m", "").replace("-", "").strip()
    try:
        return float(cleaned.split()[0]) if cleaned else None
    except (ValueError, IndexError):
        return None


def build(detail: dict, osz_fields: dict | None = None, osz_note: str = "",
          dims: dict | None = None) -> list[Step]:
    """The cave's steps in working order, each with a status and its action."""
    files = detail.get("files", [])
    has_leaf = bool(detail.get("leaves"))
    steps: list[Step] = []
    add = steps.append

    # ── priprema ────────────────────────────────────────────────────
    add(Step("mapa", "priprema", "Mapa objekta pod !Za digitalizirat", "1T",
             "done" if has_leaf else "todo",
             "" if has_leaf else "Napravi mapu SB_<broj>_<Ime> ili pokreni povezivanje mapa.",
             action=None if has_leaf else "intake-map"))

    # ── automatski ──────────────────────────────────────────────────
    karta = detail.get("karta") or {}
    add(Step("karta", "auto", "Isječak karte", "4I",
             "done" if karta.get("exists") else "todo",
             "" if karta.get("exists") else "georef.hr stvara točku i isječak (piše na server).",
             action="karta"))

    osz = _newest(files, "osz")
    add(Step("osz-prefill", "auto", "OSZ pripremljen (SB + geo + karta)", "4O",
             "done" if osz else "todo",
             action="osz-prefill", files=_names(osz)))

    # ── ručni rad ───────────────────────────────────────────────────
    locked = detail.get("locks") or []
    if osz is None:
        filled = Step("osz-filled", "rucno", "OSZ popunjen (Word)", "4O", "blocked",
                      "Prvo pripremi OSZ.")
    elif osz_fields is None:
        filled = Step("osz-filled", "rucno", "OSZ popunjen (Word)", "4O", "unknown",
                      osz_note or "Sadržaj OSZ-a nije pročitan.", files=_names(osz),
                      open=osz["path"])
    else:
        done = [k for k in HUMAN_OSZ_FIELDS if osz_fields.get(k)]
        filled = Step("osz-filled", "rucno", "OSZ popunjen (Word)", "4O",
                      "done" if done else "todo",
                      f"{len(done)}/{len(HUMAN_OSZ_FIELDS)} ručnih polja popunjeno"
                      if done else f"Otvori {osz['name']} i upiši terenske podatke.",
                      files=_names(osz), open=osz["path"])
    if locked:
        filled.note = (filled.note + " · " if filled.note else "") + "otvoren u Wordu"
    add(filled)

    raw = _newest(files, "raw")
    pp = _newest(files, "pp")
    lt = _newest(files, "lt")
    fin = _newest(files, "fin")
    plan = _newest(files, "plan")
    profile = _newest(files, "profile")
    dimenzije = _newest(files, "dimenzije")

    def chain(step_id: str, label: str, out: dict | None, src: dict | None,
              action: str, missing_src: str) -> None:
        if out is not None:
            moved = _older(out, src)
            add(Step(step_id, "rucno", label, "3N", "stale" if moved else "done",
                     f"{moved[0]['name']} je noviji – ponovi korak" if moved else "",
                     action=action, files=_names(out)))
        elif src is None:
            add(Step(step_id, "rucno", label, "3N", "blocked", missing_src, action=action))
        else:
            add(Step(step_id, "rucno", label, "3N", "todo", action=action, files=_names(src)))

    chain("3n-k1", "KORAK 1 – pripremi sirovi .csx (_pp)", pp, raw, "3n-k1",
          "Ubaci TopoDroid .csx izvoz u mapu objekta.")
    chain("3n-k2", "KORAK 2 – dovrši uvoz (_lt)", lt, pp, "3n-k2",
          "Prvo KORAK 1, pa otvori _pp u cSurveyu i spremi.")
    chain("3n-k3a", "KORAK 3a – ispravljena skica dovršena (_lt_fin)", fin, lt, "3n-k3a",
          "Prvo KORAK 2, pa ispravi skicu u cSurveyu.")
    printed = [plan, profile, dimenzije]
    if all(printed):
        moved = _older(min(printed, key=lambda f: f["modified"]), fin)
        add(Step("3n-k3b", "rucno", "KORAK 3b – tlocrt, profil, dimenzije", "3N",
                 "stale" if moved else "done",
                 f"{fin['name']} je noviji – ispiši ponovno" if moved else "",
                 action="3n-k3b", files=_names(*printed)))
    else:
        add(Step("3n-k3b", "rucno", "KORAK 3b – tlocrt, profil, dimenzije", "3N",
                 "todo" if fin else "blocked",
                 "" if fin else "Prvo KORAK 3a.", action="3n-k3b"))

    # ── spajanje ────────────────────────────────────────────────────
    if osz is None or dimenzije is None:
        add(Step("osz-dims", "spajanje", "OSZ ← duljina, dubina i ulaz iz izmjere", "4O", "blocked",
                 "Treba OSZ i KORAK 3b (dimenzije).", action="osz-prefill"))
    elif osz_fields is None:
        add(Step("osz-dims", "spajanje", "OSZ ← duljina, dubina i ulaz iz izmjere", "4O", "unknown",
                 osz_note, action="osz-prefill"))
    else:
        expected = list(MEASURED_OSZ_FIELDS)
        entrance = dims.get("entrance_size") if isinstance(dims, dict) else None
        if isinstance(entrance, dict):
            if entrance.get("count"):
                expected.append("broj_ulaza")
            if entrance.get("witnessed"):
                expected.extend(ENTRANCE_OSZ_FIELDS)
        empty = [k for k in expected if not osz_fields.get(k)]
        measured = _number(str(dims.get("l"))) if dims and dims.get("l") is not None else None
        recorded = _number(osz_fields.get("duljina"))
        differs = (measured is not None and recorded is not None
                   and round(measured) != round(recorded))
        if empty:
            add(Step("osz-dims", "spajanje", "OSZ ← duljina, dubina i ulaz iz izmjere", "4O", "todo",
                     "Ponovno pokreni Pripremi OSZ: upisuje izmjerene vrijednosti, "
                     "popunjeni sadržaj ostaje.", action="osz-prefill"))
        elif differs:
            add(Step("osz-dims", "spajanje", "OSZ ← duljina, dubina i ulaz iz izmjere", "4O", "stale",
                     f"OSZ kaže {osz_fields.get('duljina')}, izmjera {dims.get('l')} m.",
                     action="osz-prefill"))
        else:
            add(Step("osz-dims", "spajanje", "OSZ ← duljina, dubina i ulaz iz izmjere", "4O", "done"))

    nacrt = _newest(files, "nacrt")
    if not all(printed):
        add(Step("3n-k3c", "spajanje", "KORAK 3c – Nacrt na sastavnici", "3N", "blocked",
                 "Treba KORAK 3b.", action="3n-k3c", files=_names(nacrt)))
    elif nacrt is None:
        add(Step("3n-k3c", "spajanje", "KORAK 3c – Nacrt na sastavnici", "3N", "todo",
                 "" if osz else "Bez OSZ-a sastavnica ostaje djelomična – složi ponovno kad ga popuniš.",
                 action="3n-k3c"))
    else:
        moved = _older(nacrt, plan, profile, dimenzije, osz)
        add(Step("3n-k3c", "spajanje", "KORAK 3c – Nacrt na sastavnici", "3N",
                 "stale" if moved else "done",
                 ("Noviji: " + ", ".join(_names(*moved)) + " – složi ponovno") if moved else "",
                 action="3n-k3c", files=_names(nacrt)))

    sastavnica = _newest(files, "sastavnica")
    if sastavnica is None:
        add(Step("sastavnica", "spajanje", "Sastavnica za Illustrator (ruta B)", "4S",
                 "optional", "Samo ako se nacrt crta u Illustratoru.", action="sastavnica"))
    else:
        moved = _older(sastavnica, osz, dimenzije)
        add(Step("sastavnica", "spajanje", "Sastavnica za Illustrator (ruta B)", "4S",
                 "stale" if moved else "done",
                 ("Noviji: " + ", ".join(_names(*moved))) if moved else "",
                 action="sastavnica", files=_names(sastavnica)))

    # ── završno ─────────────────────────────────────────────────────
    originals = [f for f in files if f["kind"] == "photo"]
    processed = [f for f in files if f["kind"] == "photo_processed"]
    queued = detail.get("queued") or []
    if queued:
        # Photos of this cave waiting in the shared queue nobody browses:
        # they come first, whatever else the folder holds (user, 2026-10-02).
        add(Step("foto", "zavrsno", "Fotografije ulaza obrađene", "4F", "todo",
                 f"{len(queued)} fotografija čeka u redu čekanja (…za istražit) – "
                 "povuci ih u mapu objekta, pa obradi.",
                 action="photos-pull", preset={"--apply": True}))
    elif processed:
        add(Step("foto", "zavrsno", "Fotografije ulaza obrađene", "4F", "done",
                 f"{len(processed)} obrađenih" + (f", {len(originals)} originala" if originals else ""),
                 action="photos-process"))
    else:
        add(Step("foto", "zavrsno", "Fotografije ulaza obrađene", "4F",
                 "todo" if originals else "blocked",
                 f"{len(originals)} originala čeka obradu" if originals
                 else "Nema fotografija u mapi – ubaci ih ili povuci iz reda čekanja.",
                 action="photos-process" if originals else "photos-pull"))
    add(Step("izjave", "zavrsno", "Izjave autora", "5O", "unknown",
             "Provjeri za ovaj objekt.", action="people-check-cave"))
    add(Step("dosje", "zavrsno", "Dosje – prag SUE i CroSpeleo", "5D", "unknown",
             "Otvori Dosje za oba praga.", action="report"))
    add(Step("predaja", "zavrsno", "Predaja u arhivu i upis u SB", "6P", "planned",
             "M6 – još nije izgrađeno."))

    for step in steps:
        if step.status in ("todo", "stale"):
            step.current = True
            break
    return steps


def read_dims(path: str | None) -> dict | None:
    if not path:
        return None
    try:
        import json

        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def for_detail(detail: dict) -> dict:
    """The JSON the page draws: phases + steps, the OSZ read once."""
    osz = _newest(detail.get("files", []), "osz")
    fields, note = read_osz(osz["path"] if osz else None)
    dims_file = _newest(detail.get("files", []), "dimenzije")
    steps = build(detail, fields, note, read_dims(dims_file["path"] if dims_file else None))
    return {
        "phases": [{"id": key, "label": label} for key, label in PHASES],
        "steps": [asdict(step) for step in steps],
    }
