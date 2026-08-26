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
    Source.SB: "SB (2.2)",
    Source.ARCHIVE: "arhiva na Driveu (2.1)",
    Source.SURVEY: "survey (2.1a)",
    Source.OSZ: "zapisnik (2.1b)",
    Source.MAP: "isječak karte (2.1c)",
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
