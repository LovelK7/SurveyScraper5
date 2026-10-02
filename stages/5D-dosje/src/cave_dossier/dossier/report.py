"""Render a dossier for a human — what is present, what is missing, what blocks.

Deliberately plain text on stdout (no GUI yet, function over form). The layout
follows crospeleo-automation's ``cli/dossier_report.py``: identity first, then
the data by source, then the two gate verdicts last so they read as the
conclusion.
"""

from __future__ import annotations

from cave_dossier.dossier.model import (
    GATE_LABELS,
    CaveDossier,
    GateLevel,
    LifecycleState,
    Severity,
    Source,
)

_WIDTH = 74

_SOURCE_LABELS: dict[Source, str] = {
    Source.SB: "SB (2B)",
    Source.ARCHIVE: "arhiva na Driveu (5D)",
    Source.STATEMENTS: "izjave + registar osoba (5O)",
    Source.SURVEY: "survey (3N)",
    Source.OSZ: "zapisnik (4O)",
    Source.MAP: "isječak karte (4I)",
    Source.PHOTOS: "obrada fotografija (2.1d)",
}

_LIFECYCLE_HINT: dict[LifecycleState, str] = {
    LifecycleState.ISTRAZENI: "has a SUE number — gate 1 already passed",
    LifecycleState.ZA_ISTRAZIT: "queue: not explored yet",
    LifecycleState.NESREDENI: "queue: explored, not finished",
    LifecycleState.SUDJELOVANJE: "another society's cave, SUE took part",
    LifecycleState.UNCLASSIFIED: "queue: in none of SB's three views",
}


def render(dossier: CaveDossier) -> str:
    lines: list[str] = []
    add = lines.append

    add("─" * _WIDTH)
    add(f"  {dossier.display_name}")
    add(f"  SB status: {dossier.lifecycle.value}  —  {_LIFECYCLE_HINT[dossier.lifecycle]}")
    add("─" * _WIDTH)

    add("")
    add("  Sources gathered")
    for source in Source:
        gathered = dossier.has(source)
        mark = "✓" if gathered else "·"
        state = "" if gathered else "(not gathered yet)"
        add(f"    {mark} {_SOURCE_LABELS[source]:<26} {state}".rstrip())

    if dossier.has(Source.SB):
        add("")
        # Redni broj is the working ID until a SUE number exists; the Excel row
        # is bookkeeping (the M6 write-back handle), not an identifier.
        add(f"  SB — Redni broj {dossier.serial_number or '—'}  ·  working ID "
            f"{dossier.working_id or '—'}  ·  Excel row {dossier.sb_row_number}")
        for label, value in _sb_pairs(dossier):
            add(f"    {label:<22} {value}")

    if dossier.survey:
        add("")
        add("  Survey (2.1a)")
        survey = dossier.survey
        add(f"    {'duljina / dubina':<22} {_num(survey.length_m)} / {_num(survey.depth_m)} m")
        add(f"    {'horiz. / vert.':<22} {_num(survey.horizontal_length_m)} / "
            f"{_num(survey.vertical_difference_m)} m")

    files = _file_lines(dossier)
    if files:
        add("")
        add("  Files")
        for line in files:
            add(f"    {line}")

    people = _people_lines(dossier)
    if people:
        add("")
        add("  Osobe · izjave")
        for line in people:
            add(f"    {line}")

    for gate in (GateLevel.SUE, GateLevel.CROSPELEO):
        add("")
        _render_gate(dossier, gate, add)

    add("")
    return "\n".join(lines)


def _render_gate(dossier: CaveDossier, gate: GateLevel, add) -> None:
    report = dossier.readiness
    ready = report.ready_for(gate)
    ordinal = "1" if gate is GateLevel.SUE else "2"
    add(f"  Gate {ordinal} — {GATE_LABELS[gate]}: {'READY' if ready else 'NOT READY'}")

    blockers = report.blockers_for(gate)
    warnings = report.warnings_for(gate)
    unchecked = report.unchecked_for(gate)

    if gate is GateLevel.CROSPELEO:
        # Gate 2 repeats every gate-1 finding; show only what it adds on top.
        blockers = [i for i in blockers if i.level is GateLevel.CROSPELEO]
        warnings = [i for i in warnings if i.level is GateLevel.CROSPELEO]
        unchecked = [u for u in unchecked if u.level is GateLevel.CROSPELEO]
        add("    (everything gate 1 needs, plus:)")

    for issue in blockers:
        add(f"    BLOCKER  {issue.message}")
    for issue in warnings:
        add(f"    warning  {issue.message}")
    if not blockers and not warnings:
        add("    (no issues among the checks that could run)")
    if unchecked:
        add(f"    Not checked yet ({len(unchecked)} rules — source not gathered):")
        for rule in unchecked:
            tier = "blocker" if rule.severity is Severity.BLOCKER else "warning"
            add(f"      · {rule.label:<38} needs {_SOURCE_LABELS[rule.source]}  [{tier}]")


def _sb_pairs(dossier: CaveDossier) -> list[tuple[str, str]]:
    georeference = dossier.georeference
    pairs: list[tuple[str, str]] = [
        ("SUE broj", dossier.sue_number or "—"),
        ("Broj pločice", dossier.plaque_number or "—"),
        ("Lokalitet", dossier.locality or "—"),
        ("Najbliže mjesto", dossier.nearest_place or "—"),
        (
            "Koordinate (HTRS96)",
            f"X {_num(georeference.x_htrs)}  Y {_num(georeference.y_htrs)}  "
            f"Z {_num(georeference.z_m)}" if georeference else "—",
        ),
        ("Duljina / Dubina", f"{_num(dossier.length_m)} / {_num(dossier.depth_m)} m"),
        ("Razdoblje istraž.", dossier.exploration_period or "—"),
        ("Autori nacrta", _authors(dossier) or "—"),
    ]
    if dossier.synonyms:
        pairs.append(("Sinonimi", ", ".join(dossier.synonyms)))
    flags = [
        f"{name} {value}"
        for name, value in (
            ("foto ulaza:", dossier.entrance_photo_flag),
            ("zagađenost:", dossier.pollution_flag),
            ("ledenica:", dossier.ice_cave_flag),
            ("dopunski zapisnik:", dossier.supplementary_record_flag),
        )
        if value
    ]
    if flags:
        pairs.append(("SB oznake", "  ".join(flags)))
    if dossier.note:
        pairs.append(("Napomena", dossier.note))
    return pairs


def _authors(dossier: CaveDossier) -> str:
    """Author names, each with its outside-society flag restored for display."""
    parts = []
    for author in dossier.drawing_authors:
        society = dossier.drawing_author_societies.get(author)
        parts.append(f"{author} [{society}]" if society else author)
    return ", ".join(parts)


def _file_lines(dossier: CaveDossier) -> list[str]:
    lines: list[str] = []
    if dossier.osz_document:
        lines.append(f"zapisnik   {dossier.osz_document.path}")
    for archive_file in dossier.nacrt_pdfs:
        lines.append(f"nacrt      {archive_file.path}")
    for archive_file in dossier.entrance_photos:
        lines.append(f"foto ulaza {archive_file.path}")
    for archive_file in dossier.statement_files:
        lines.append(f"izjava     {archive_file.path}")
    if dossier.map_excerpt:
        lines.append(f"isječak    {dossier.map_excerpt.path}")
    return lines


def people_entries(dossier: CaveDossier) -> list[dict]:
    """People named in the dossier, merged per person (roles collected).

    Each entry: ``name`` (canonical when resolved), ``roles``, ``status`` and
    ``files`` (izjava file names). Status: ``ok`` an izjava covers this cave ·
    ``scope`` izjave exist but none covers it (scope names another
    locality/cave) · ``missing`` none on file · ``unknown`` not in the people
    registry. Shared by the text report and :func:`to_view`.
    """
    merged: dict[str, dict] = {}
    for entry in dossier.person_statements:
        key = (entry.canonical or entry.name).casefold()
        slot = merged.setdefault(
            key,
            {"display": entry.canonical or entry.name, "roles": [], "entry": entry},
        )
        if entry.role.value not in slot["roles"]:
            slot["roles"].append(entry.role.value)
    people = []
    for slot in merged.values():
        entry = slot["entry"]
        if entry.in_registry is False:
            status = "unknown"
        elif entry.covering:
            status = "ok"
        elif entry.statements:
            status = "scope"
        else:
            status = "missing"
        people.append(
            {
                "name": slot["display"],
                "roles": list(slot["roles"]),
                "status": status,
                "files": [path.name for path in entry.statements],
            }
        )
    return people


#: Report mark per person status — see :func:`people_entries`.
PERSON_MARKS: dict[str, str] = {"ok": "✓", "scope": "~", "missing": "✗", "unknown": "?"}


def _people_lines(dossier: CaveDossier) -> list[str]:
    """One line per person named in the dossier: izjava status + roles + files.

    ``✓`` an izjava covers this cave · ``~`` izjave exist but none covers it
    (scope names another locality/cave) · ``✗`` none on file · ``?`` not in
    the people registry.
    """
    return [person_line(person) for person in people_entries(dossier)]


def person_line(person: dict) -> str:
    """One ``people_entries`` item as the report prints it."""
    files = ", ".join(person["files"]) or "(nema izjave)"
    return (f"{PERSON_MARKS[person['status']]} {person['name']:<24} "
            f"{', '.join(person['roles']):<20} {files}")


# ── JSON view (the dashboard) ─────────────────────────────────────────


def to_view(dossier: CaveDossier) -> dict:
    """The same content :func:`render` prints, as a JSON-serialisable dict.

    The local dashboard renders this; the key set is a contract with its
    front end. ``dossier`` must already be evaluated (``readiness`` set).
    Gate 2 lists only what it adds on top of gate 1, exactly like the text.
    """
    survey = dossier.survey
    return {
        "name": dossier.display_name,
        "serial": dossier.serial_number,
        "working_id": dossier.working_id,
        "sue": dossier.sue_number,
        "excel_row": dossier.sb_row_number,
        "lifecycle": dossier.lifecycle.value,
        "lifecycle_hint": _LIFECYCLE_HINT[dossier.lifecycle],
        "sources": [
            {"key": source.value, "label": _SOURCE_LABELS[source], "gathered": dossier.has(source)}
            for source in Source
        ],
        "sb": [[label, value] for label, value in _sb_pairs(dossier)]
        if dossier.has(Source.SB)
        else [],
        "survey": {
            "length_m": survey.length_m,
            "depth_m": survey.depth_m,
            "horizontal_length_m": survey.horizontal_length_m,
            "vertical_difference_m": survey.vertical_difference_m,
        }
        if survey
        else None,
        "files": _file_lines(dossier),
        "people": people_entries(dossier),
        "gates": [_gate_view(dossier, gate) for gate in (GateLevel.SUE, GateLevel.CROSPELEO)],
    }


def _gate_view(dossier: CaveDossier, gate: GateLevel) -> dict:
    report = dossier.readiness
    blockers = report.blockers_for(gate)
    warnings = report.warnings_for(gate)
    unchecked = report.unchecked_for(gate)
    if gate is GateLevel.CROSPELEO:
        blockers = [i for i in blockers if i.level is GateLevel.CROSPELEO]
        warnings = [i for i in warnings if i.level is GateLevel.CROSPELEO]
        unchecked = [u for u in unchecked if u.level is GateLevel.CROSPELEO]
    return {
        "gate": "sue" if gate is GateLevel.SUE else "crospeleo",
        "ordinal": 1 if gate is GateLevel.SUE else 2,
        "label": GATE_LABELS[gate],
        "ready": report.ready_for(gate),
        "blockers": [issue.message for issue in blockers],
        "warnings": [issue.message for issue in warnings],
        "unchecked": [
            {
                "label": rule.label,
                "source_label": _SOURCE_LABELS[rule.source],
                "severity": "blocker" if rule.severity is Severity.BLOCKER else "warning",
            }
            for rule in unchecked
        ],
    }


def _num(value: float | None) -> str:
    """Numbers as a human writes them — no scientific notation.

    Plain ``:g`` turns the 7-digit HTRS96 northing 5050004 into "5.05e+06",
    which is unreadable as a coordinate; integral values print as integers and
    fractional ones keep up to two decimals.
    """
    if value is None:
        return "—"
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.2f}".rstrip("0").rstrip(".")
