"""Every action the dashboard can run — one table, the blueprint of the GUI.

The page renders its buttons from this list and the server builds argv from it,
so a button can never run anything that is not written down here. Adding a
command to the GUI is one ``Action`` entry; nothing in the HTML changes.

An action runs one of two kinds of tool:

* ``tool="cli"`` — a ``cavedossier`` subcommand, run with the same interpreter
  as the server (so the venv is always the right one).
* ``tool="<script>.py"`` — a 3N script from ``stages/3N-nacrt/production/tools``.
  3N is deliberately not part of the package (its README), so it is reached
  as a file, exactly like the Drive ``.bat`` kit does.

Argument tokens: ``{broj}`` is the current cave's Redni broj, ``{file}`` a file
picked from the cave's intake leaf (``file_kind`` says which), ``{query}`` the
free-text cave lookup some SB commands take (prefilled with the cave's name).

Writes (user decision 2026-09-24): read-only and dry-run runs go with one
click; anything that writes to Drive, to a cave's folder or to a server asks
first, and the server refuses an unconfirmed writing run. Output that only
lands in the workspace's ``runs/`` / ``sb-sync/`` does not count as a write —
every command already leaves a run dir behind.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class Option:
    """One optional argument the page shows as a checkbox or input.

    ``kind``: ``flag`` (checkbox, emits ``flag``), ``int`` / ``text`` (an input,
    emits ``flag value`` when non-empty), ``choice`` (a select over ``choices``).
    ``safe``: ticking this flag makes a writing action read-only (``--dry-run``,
    ``--local`` keeps output in runs/). ``unsafe``: ticking it makes a read-only
    action write (``--apply``).
    """

    flag: str
    label: str
    kind: str = "flag"
    default: bool | str = False
    help: str = ""
    choices: tuple[str, ...] = ()
    safe: bool = False
    unsafe: bool = False


@dataclass(frozen=True)
class Action:
    id: str
    stage: str
    title: str
    help: str
    tool: str
    args: tuple[str, ...]
    options: tuple[Option, ...] = ()
    #: What the run writes, in words, for the confirm dialog. None = read-only.
    writes: str | None = None
    #: Where the write lands when ``unsafe`` flags are ticked on a read-only action.
    unsafe_writes: str | None = None
    #: Which intake-leaf files ``{file}`` may be: see ``state.FILE_KINDS``.
    file_kind: str | None = None
    #: Label of the step inside the stage tab ("KORAK 1"), for ordering/grouping.
    step: str = ""
    #: A manual step shown between runs (no command): cSurvey work etc.
    manual: str = ""
    group: str = ""

    @property
    def needs_cave(self) -> bool:
        return any(t in a for a in self.args for t in ("{broj}", "{file}", "{query}"))

    def to_json(self) -> dict:
        data = asdict(self)
        data["needs_cave"] = self.needs_cave
        return data


OFFLINE = Option("--offline", "Bez mreže (--offline)",
                 help="Samo lokalni podaci; ništa se ne dohvaća s interneta.")
FORCE = Option("--force", "Prepiši postojeće (--force)",
               help="Prepisuje izlaznu datoteku koja već postoji.")
LOCAL = Option("--local", "Samo lokalno (--local)", safe=True,
               help="Rezultat ostaje u runs/, ne isporučuje se u mapu objekta.")


ACTIONS: tuple[Action, ...] = (
    # ── 1T — intake ──────────────────────────────────────────────────
    Action(
        "intake-map", "1T", "Poveži mape s SB-om",
        "Za svaku mapu pod !Za digitalizirat pronađi SB red i predloži prefiks "
        "SB_<broj>_. Bez --apply ništa ne mijenja.",
        "cli", ("intake", "map"),
        options=(
            Option("--unmatched-only", "Samo nepovezane"),
            Option("--apply", "Preimenuj mape (--apply)", unsafe=True),
        ),
        unsafe_writes="preimenuje mape pod !Za digitalizirat na Driveu",
    ),
    # ── 2B — SB ──────────────────────────────────────────────────────
    Action("sb-stats", "2B", "Statistika SB-a",
           "Listovi, broj redaka, popunjenost ključnih stupaca.",
           "cli", ("sb", "stats"), group="Pregled SB-a"),
    Action("sb-columns", "2B", "Stupci SB-a",
           "Prepoznati red zaglavlja i svi nazivi stupaca.",
           "cli", ("sb", "columns"), group="Pregled SB-a"),
    Action("sb-inspect", "2B", "Red objekta u SB-u",
           "Ispis cijelog SB reda za objekt (ime, SUE broj ili broj pločice; "
           "dio imena je dovoljan).",
           "cli", ("sb", "inspect", "--cave", "{query}"), group="Pregled SB-a"),
    Action("sb-audit-authors", "2B", "Nečitljivi autori",
           "Ćelije 'Autori nacrta ili izvor' koje razdjelnik imena ne razumije.",
           "cli", ("sb", "audit-authors"),
           options=(Option("--limit", "Koliko redaka", kind="int", default="40"),),
           group="Revizije"),
    Action("sb-unclassified", "2B", "Neklasificirani redovi",
           "Imenovani redovi bez SUE broja i bez oznake u Napomeni.",
           "cli", ("sb", "unclassified"),
           options=(Option("--limit", "Koliko redaka", kind="int", default="60"),),
           group="Revizije"),
    Action("sat-sync", "2B", "Liburnija tablica vs SB",
           "Četiri liste razlika između Liburnija LiDAR tablice i SB-a.",
           "cli", ("sat", "sync"),
           options=(
               Option("--coords", "Uspoređuj i koordinate (--coords)"),
               Option("--out", "Zapiši liste u sb-sync/ (--out)"),
           ),
           group="Satelitske tablice"),
    # ── 3N — nacrt ───────────────────────────────────────────────────
    Action(
        "3n-k1", "3N", "Pripremi sirovi .csx",
        "TopoDroid izvoz → <ime>_pp.csx (simboli preimenovani da prežive uvoz).",
        "preprocess_tdx_csx.py", ("{file}",),
        options=(Option("--force", "Prepiši postojeći _pp (--force)", default=True),),
        writes="zapisuje <ime>_pp.csx u mapu objekta",
        file_kind="raw", step="KORAK 1",
    ),
    Action(
        "3n-m1", "3N", "cSurvey: otvori _pp i spremi",
        "", "manual", (), file_kind="pp", step="cSurvey",
        manual="Otvori <ime>_pp.csx u cSurveyu, pa File › Save As (isto ime).",
    ),
    Action(
        "3n-k2", "3N", "Dovrši uvoz",
        "Spremljena datoteka → <ime>_lt.csx (linije u splajnove, voda, veličine znakova).",
        "fix_imported_linetypes.py", ("{file}",),
        options=(Option("--force", "Prepiši postojeći _lt (--force)", default=True),),
        writes="zapisuje <ime>_lt.csx u mapu objekta",
        file_kind="pp", step="KORAK 2",
    ),
    Action(
        "3n-m2", "3N", "cSurvey: ispravi skicu",
        "", "manual", (), file_kind="lt", step="cSurvey",
        manual="Otvori <ime>_lt.csx u cSurveyu, ispravi skicu i spremi.",
    ),
    Action(
        "3n-k3a", "3N", "Dovrši nacrt (_lt → _lt_fin)",
        "Ulaz, dubina, mjerilo, strelica sjevera, A4 postavke ispisa. Bez --yes "
        "i --layout pokazuje izbornik rasporeda — odgovori u polju ispod ispisa.",
        "nacrt_finish.py", ("{file}",),
        options=(
            FORCE,
            Option("--yes", "Prihvati predloženi raspored (--yes)"),
            Option("--layout", "Raspored br.", kind="int", default="",
                   help="Broj iz izbornika rasporeda (1 = prijedlog)."),
            Option("--dry-run", "Samo pokaži (--dry-run)", safe=True),
        ),
        writes="zapisuje <ime>_lt_fin.csx u mapu objekta",
        file_kind="lt", step="KORAK 3a",
    ),
    Action(
        "3n-k3b", "3N", "Ispiši tlocrt i profil (cSurvey bez dijaloga)",
        "Pokreće instalirani cSurvey: <ime>_plan.pdf, <ime>_profile.pdf, "
        "<ime>_dimenzije.json. Treba C:\\csurvey64 i pisač Microsoft Print to PDF.",
        "csurvey_driver.py", ("finish", "{file}"),
        writes="zapisuje _plan.pdf, _profile.pdf i _dimenzije.json u mapu objekta",
        file_kind="fin", step="KORAK 3b",
    ),
    Action(
        "3n-k3c", "3N", "Složi Nacrt na sastavnicu",
        "Tlocrt + profil na stranicu sastavnice → SB_<broj>_nacrt.pdf. Ako crtež "
        "ne stane, javlja preklop u mm: ponovi 3a s --layout N.",
        "cli", ("nacrt", "{broj}"),
        options=(OFFLINE, LOCAL, Option("--force", "Prepiši tuđi nacrt (--force)")),
        writes="isporučuje SB_<broj>_nacrt.pdf u mapu objekta",
        step="KORAK 3c",
    ),
    Action("3n-inspect", "3N", "Statistika datoteke",
           "Samo čitanje: statistika bilo koje .csz/.csx datoteke.",
           "inspect_survey.py", ("{file}",), file_kind="survey",
           group="Dijagnostika"),
    Action("3n-info", "3N", "cSurvey info",
           "cSurvey bez dijaloga: osnovni podaci o datoteci.",
           "csurvey_driver.py", ("info", "{file}"), file_kind="survey",
           group="Dijagnostika"),
    Action("3n-dimensions", "3N", "cSurvey dimenzije",
           "cSurvey bez dijaloga: duljina i dubina.",
           "csurvey_driver.py", ("dimensions", "{file}"), file_kind="survey",
           group="Dijagnostika"),
    # ── 4G — geo ─────────────────────────────────────────────────────
    Action("geo-locate", "4G", "Lokalitet iz koordinata",
           "Županija, grad/općina, najbliže mjesto i lokalitet iz X/Y reda, "
           "usporedno s onim što piše u SB-u.",
           "cli", ("geo", "locate", "{broj}"), options=(OFFLINE,)),
    Action("geo-kota", "4G", "Kota ulaza (DMV)",
           "Kota ulaza iz DGU DMV rastera nasuprot Z iz SB-a.",
           "cli", ("geo", "kota", "{broj}"), options=(OFFLINE,)),
    Action("geo-fetch", "4G", "Preuzmi geo podatke",
           "Jednokratno: granice (GeoPackage) + RGI gazeteer u data/geo.",
           "cli", ("geo", "fetch-data"),
           options=(Option("--no-inspire-au", "Preskoči INSPIRE AU (~209 MB)"),),
           writes="preuzima velike datoteke u data/geo", group="Jednokratno"),
    # ── 4I — isječak ─────────────────────────────────────────────────
    Action("karta", "4I", "Isječak karte (georef.hr)",
           "Stvara točku na georef.hr i sprema isječak karte + zapis.",
           "cli", ("karta", "{broj}"),
           options=(
               Option("--force", "Osvježi postojeći (--force)"),
               Option("--debug", "Prikaži preglednik (--debug)"),
           ),
           writes="STVARA TOČKU NA georef.hr i sprema PNG u !!Isječci karte"),
    # ── 4O — OSZ ─────────────────────────────────────────────────────
    Action("osz-prefill", "4O", "Pripremi OSZ",
           "SB + tražilice → popunjeni SB_<broj>_OSZ.docx u mapi objekta, "
           "+ dopune-sb.csv za ručni unos u SB.",
           "cli", ("osz", "prefill", "{broj}"),
           options=(
               OFFLINE,
               Option("--force-karta", "Ponovno dohvati isječak (--force-karta)"),
               Option("--debug", "Prikaži preglednik (--debug)"),
           ),
           writes="isporučuje SB_<broj>_OSZ.docx u mapu objekta "
                  "(stari OSZ ostaje kao <ime>_stari_<datum>.docx)"),
    Action("osz-backfill", "4O", "Iz popunjenog OSZ-a u SB (prijedlog)",
           "Čita popunjeni OSZ i predlaže dopune SB-a — CSV za ručni unos, "
           "SB se nikad ne mijenja.",
           "cli", ("osz", "backfill", "{broj}")),
    # ── 4F — fotografije ─────────────────────────────────────────────
    Action("photos-process", "4F", "Obradi fotografije ulaza",
           "Kopije SB_<broj>_<Ime>_<Autor>_<n>.jpg pokraj originala "
           "(1920 px / 1.5 MB). Originali ostaju.",
           "cli", ("photos", "process", "{broj}"),
           options=(
               Option("--dry-run", "Samo plan (--dry-run)", safe=True),
               Option("--author", "Autor", kind="text", default="",
                      help="Kad OSZ ne navodi autora fotografije."),
               Option("--overwrite", "Ponovno izreži (--overwrite)"),
           ),
           writes="dodaje obrađene kopije fotografija u mapu objekta"),
    Action("photos-pull", "4F", "Povuci fotografije iz reda čekanja",
           "Fotografije iz '…za istražit' u mapu objekta. Bez --apply samo plan.",
           "cli", ("photos", "pull-staged", "{broj}"),
           options=(Option("--apply", "Premjesti (--apply)", unsafe=True),),
           unsafe_writes="PREMJEŠTA fotografije iz reda čekanja u mapu objekta"),
    Action("photos-check-flag", "4F", "Fotografije vs oznaka u SB-u",
           "Fotografije u redu čekanja nasuprot 'Fotografija ulaza = DA'.",
           "cli", ("photos", "check-flag"), group="Revizije"),
    # ── 4S — sastavnica ──────────────────────────────────────────────
    Action("sastavnica", "4S", "Sastavnica (Illustrator)",
           "Popunjena sastavnica Nacrta iz SB-a + popunjenog OSZ-a.",
           "cli", ("sastavnica", "{broj}"),
           options=(OFFLINE, LOCAL, Option("--force", "Prepiši tuđu (--force)")),
           writes="isporučuje SB_<broj>_sastavnica.pdf u mapu objekta"),
    # ── 5O — osobe ───────────────────────────────────────────────────
    Action("people-list", "5O", "Registar osoba",
           "Svaka osoba iz registra, njeni nadimci i povezane izjave.",
           "cli", ("people", "list")),
    Action("people-check", "5O", "Provjera izjava",
           "Osobe bez izjave, izjave bez osobe, SB autori koje registar ne zna.",
           "cli", ("people", "check")),
    # ── 5D — dosje ───────────────────────────────────────────────────
    Action("report", "5D", "Dosje objekta (oba praga)",
           "Što postoji, što nedostaje, što blokira — prag SUE i prag CroSpeleo.",
           "cli", ("report", "--cave", "{query}"),
           options=(
               Option("--json", "Kao JSON (--json)"),
               Option("--gate", "Izlazni kod prati prag", kind="choice",
                      default="sue", choices=("sue", "crospeleo")),
           )),
)

BY_ID: dict[str, Action] = {a.id: a for a in ACTIONS}


class ActionError(ValueError):
    """The page asked for something the catalog does not allow."""


def is_write(action: Action, selected: dict[str, object]) -> str | None:
    """What this run would write, or None when it is read-only as configured."""
    ticked = {o.flag for o in action.options if o.kind == "flag" and selected.get(o.flag)}
    if action.writes and not any(o.safe and o.flag in ticked for o in action.options):
        return action.writes
    if action.unsafe_writes and any(o.unsafe and o.flag in ticked for o in action.options):
        return action.unsafe_writes
    return None


def build_args(
    action: Action,
    *,
    broj: int | None = None,
    file: str | None = None,
    query: str | None = None,
    selected: dict[str, object] | None = None,
) -> list[str]:
    """argv for the tool (without the interpreter), from validated inputs only."""
    selected = selected or {}
    out: list[str] = []
    for token in action.args:
        if "{broj}" in token:
            if broj is None:
                raise ActionError("Odaberi objekt (Redni broj).")
            token = token.replace("{broj}", str(int(broj)))
        if "{file}" in token:
            if not file:
                raise ActionError("Odaberi datoteku.")
            token = token.replace("{file}", file)
        if "{query}" in token:
            if not query or not str(query).strip():
                raise ActionError("Upiši ime, SUE broj ili broj pločice.")
            token = token.replace("{query}", str(query).strip())
        out.append(token)
    for option in action.options:
        value = selected.get(option.flag)
        if option.kind == "flag":
            if value:
                out.append(option.flag)
        elif value not in (None, ""):
            text = str(value).strip()
            if option.kind == "int":
                if not text.lstrip("-").isdigit():
                    raise ActionError(f"{option.label}: očekujem broj, a ne '{text}'.")
            elif option.kind == "choice" and text not in option.choices:
                raise ActionError(f"{option.label}: '{text}' nije ponuđen.")
            if text:
                out.extend([option.flag, text])
    return out


@dataclass(frozen=True)
class Stage:
    label: str
    title: str
    subtitle: str
    readme: str
    status: str
    notes: tuple[str, ...] = field(default_factory=tuple)


#: The tabs, in pipeline order. Status mirrors pipeline.yaml.
STAGES: tuple[Stage, ...] = (
    Stage("1T", "Teren", "Mape s terena pod !Za digitalizirat",
          "stages/1T-teren/README.md", "parked"),
    Stage("2B", "Speleo baza", "SB radna knjiga i satelitske tablice",
          "stages/2B-baza/README.md", "operational"),
    Stage("3N", "Nacrt", "TopoDroid .csx → SB_<broj>_nacrt.pdf preko cSurveya",
          "stages/3N-nacrt/README.md", "operational"),
    Stage("4G", "Geo", "Lokalitet i kota iz otvorenih DGU servisa",
          "stages/4G-geo/README.md", "operational"),
    Stage("4I", "Isječak karte", "Isječak karte s georef.hr",
          "stages/4I-isjecak/README.md", "operational"),
    Stage("4O", "OSZ", "Osnovni speleološki zapisnik (v10 predložak)",
          "stages/4O-osz/README.md", "operational"),
    Stage("4F", "Fotografije", "Fotografije ulaza",
          "stages/4F-fotografije/README.md", "partial"),
    Stage("4S", "Sastavnica", "Sastavnica Nacrta za Illustrator",
          "stages/4S-sastavnica/README.md", "operational"),
    Stage("5O", "Osobe", "Registar osoba i izjave",
          "stages/5O-osobe/README.md", "operational"),
    Stage("5D", "Dosje", "Dosje objekta i dva praga",
          "stages/5D-dosje/README.md", "partial"),
    Stage("6P", "Predaja", "Isporuka u arhivu i upis u SB",
          "stages/6P-predaja/README.md", "planned",
          notes=("Samo dizajn (M6): upis u SB preko Excel COM-a i premještanje "
                 "u arhivske mape. Gumbi ispod su maketa budućeg sučelja.",)),
)


def catalog_json() -> dict:
    return {
        "stages": [asdict(s) for s in STAGES],
        "actions": [a.to_json() for a in ACTIONS],
    }
