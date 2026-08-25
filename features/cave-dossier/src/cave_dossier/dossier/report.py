"""Render a dossier for a human — what is present, what is missing, what blocks.

Deliberately plain text on stdout (no GUI yet, function over form).  The layout
follows crospeleo-automation's ``cli/dossier_report.py``: identity first, then
the data by source, then the verdict last so it reads as the conclusion.
"""

from __future__ import annotations

from cave_dossier.dossier.model import CaveDossier, Severity, Source

_WIDTH = 74

_SOURCE_LABELS: dict[Source, str] = {
    Source.SB: "SB (2.2)",
    Source.ARCHIVE: "arhiva na Driveu (2.1)",
    Source.SURVEY: "survey (2.1a)",
    Source.OSZ: "zapisnik (2.1b)",
    Source.MAP: "isječak karte (2.1c)",
}


def render(dossier: CaveDossier) -> str:
    lines: list[str] = []
    add = lines.append

    add("─" * _WIDTH)
    add(f"  {dossier.display_name}")
    add("─" * _WIDTH)

    add("")
    add("  Sources gathered")
    for source in Source:
        gathered = dossier.has(source)
        mark = "✓" if gathered else "·"
        state = "" if gathered else "(not gathered yet)"
        add(f"    {mark} {_SOURCE_LABELS[source]:<24} {state}".rstrip())

    if dossier.has(Source.SB):
        add("")
        add(f"  SB row {dossier.sb_row_number}")
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

    report = dossier.readiness
    status = "READY" if report.ready else "NOT READY"
    add("")
    add(f"  Readiness — {status}")
    for issue in report.blockers:
        add(f"    BLOCKER  {issue.message}")
    for issue in report.warnings:
        add(f"    warning  {issue.message}")
    if not report.issues:
        add("    (no issues among the checks that could run)")
    if report.unchecked:
        add("")
        add(f"    Not checked yet ({len(report.unchecked)} rules — source not gathered):")
        for rule in report.unchecked:
            tier = "blocker" if rule.severity is Severity.BLOCKER else "warning"
            add(f"      · {rule.label:<38} needs {_SOURCE_LABELS[rule.source]}  [{tier}]")

    add("")
    return "\n".join(lines)


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
        ("Autori nacrta", ", ".join(dossier.drawing_authors) or "—"),
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
