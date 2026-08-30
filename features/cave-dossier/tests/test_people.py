"""People registry + statement linkage + the two statement gates.

The registry design is the crospeleo port (docs/PORTING.md): aliases derived
at load with collision detection, curated overrides win, resolution is exact
key lookup only. The gates: gate 1 blocks per AUTHOR (scope-aware), gate 2
warns per PERSON (registry-wide view of who is missing an izjava).
"""

from __future__ import annotations

import json
from pathlib import Path

from cave_dossier.dossier import (
    ArchiveFile,
    CaveDossier,
    FileRole,
    GateLevel,
    IssueCode,
    PersonRole,
    Severity,
    Source,
    evaluate,
)
from cave_dossier.people.name_resolver import matches_token, name_keys
from cave_dossier.people.registry import Person, PersonRegistry
from cave_dossier.people.statements import (
    StatementIndex,
    link_person_statements,
    scan_izjave,
)


# ── Name resolver (crospeleo port) ────────────────────────────────────


def test_name_keys_bridge_every_spelling_of_a_two_token_name() -> None:
    keys = name_keys("Lovel Kukuljan")
    # Full, izjava token / SB shorthand, and surname alone all key identically.
    assert name_keys("LKukuljan") & keys
    assert name_keys("L.Kukuljan") & keys
    assert "kukuljan" in keys


def test_name_keys_handle_three_token_and_hyphenated_names() -> None:
    # 3+ tokens: initials come from every token but the last — a shape
    # `variants_for` refuses entirely.
    assert "amhorvat" in name_keys("Ana Marija Horvat")
    # The hyphenated double surname collapses to one key with the hyphen folded.
    assert matches_token("Sanja Kapidžić-Antolič", "SKapidžić-Antolič")


def test_dj_is_folded_even_though_nfkd_will_not() -> None:
    assert matches_token("Đuro Đaković", "DDaković")


def test_is_author_shorthand_is_the_author_vs_finder_criterion() -> None:
    from cave_dossier.core.people import is_author_shorthand

    # Survey authors — the N.Surname convention (double surnames included).
    for author in ("L.Kukuljan", "D. Reš", "S.Kapidžić-Antolič", "A.Lipovac"):
        assert is_author_shorthand(author), author
    # Finders/sources — every other way the cell writes people.
    for finder in ("Tin", "Denis Medica", "vedran", "SOV", ".Dujmović",
                   "Malez M. (1960)", "", None):
        assert not is_author_shorthand(finder), finder


# ── Registry ──────────────────────────────────────────────────────────


def _registry(*people: Person) -> PersonRegistry:
    return PersonRegistry.from_people(list(people))


def test_full_name_resolves_from_all_conventions() -> None:
    registry = _registry(Person(name="Lovel Kukuljan"))
    for spelling in ("Lovel Kukuljan", "L.Kukuljan", "L. Kukuljan", "LKukuljan", "Lovel K."):
        assert registry.resolve(spelling).name == "Lovel Kukuljan", spelling


def test_token_entry_resolves_token_and_sb_shorthand_but_not_full_name() -> None:
    """An entry still in izjava-token form works until the full name is learned."""
    registry = _registry(Person(name="ABahović"))
    assert registry.resolve("ABahović") is not None
    assert registry.resolve("A.Bahović") is not None
    assert registry.resolve("Ana Bahović") is None  # needs the full-name upgrade


def test_trailing_society_bracket_is_stripped_on_retry() -> None:
    registry = _registry(Person(name="Marko Rakovac"))
    assert registry.resolve("M.Rakovac (SOV)").name == "Marko Rakovac"


def test_colliding_derived_keys_resolve_nobody() -> None:
    """Two-letter initials clash (crospeleo object 723): drop, never guess."""
    registry = _registry(Person(name="Lovel Kukuljan"), Person(name="Luka Kovač"))
    assert "lk" in registry.stats.collisions
    assert registry.resolve("LK") is None
    # The unambiguous keys survive for both people.
    assert registry.resolve("L.Kukuljan").name == "Lovel Kukuljan"
    assert registry.resolve("L.Kovač").name == "Luka Kovač"


def test_curated_alias_wins_over_derived_keys() -> None:
    registry = _registry(
        Person(name="Sara Mikičić", aliases=("SM",)),
        Person(name="Sara Medica"),
    )
    # "SM" would be an initials collision; the curated alias settles it.
    assert registry.resolve("SM").name == "Sara Mikičić"


def test_deceased_people_are_exempt_from_the_izjava_requirement() -> None:
    """A statement cannot be obtained from a deceased author (user, 2026-08-30):
    no gate-1 blocker, no gate-2 warning, never listed as missing a statement."""
    registry = _registry(Person(name="V.Malnar", deceased=True), Person(name="I.Ivić"))
    dossier = _dossier(drawing_authors=["V.Malnar", "I.Ivić"])
    dossier.person_statements = link_person_statements(dossier, registry=registry)
    assert [entry.name for entry in dossier.person_statements] == ["I.Ivić"]

    report = evaluate(dossier)
    blockers = [i for i in report.issues if i.code is IssueCode.MISSING_STATEMENT]
    assert len(blockers) == 1 and "I.Ivić" in blockers[0].message

    index = StatementIndex([], registry)
    assert [p.name for p in index.missing_statement_people()] == ["I.Ivić"]


def test_surname_alone_never_resolves_globally() -> None:
    """Singleton keys collide across a real registry — per-row matching only."""
    registry = _registry(Person(name="Lovel Kukuljan"))
    assert registry.resolve("Kukuljan") is None


def test_missing_registry_file_is_an_empty_registry(tmp_path: Path) -> None:
    registry = PersonRegistry.load(tmp_path / "nema.json")
    assert len(registry) == 0
    assert registry.resolve("Bilo Tko") is None


def test_load_accepts_bare_strings_and_dicts(tmp_path: Path) -> None:
    path = tmp_path / "registry.json"
    path.write_text(
        json.dumps({"people": ["Ivo Ivić", {"name": "Ana Anić", "society": "SOV"}]}),
        encoding="utf-8",
    )
    registry = PersonRegistry.load(path)
    assert registry.resolve("I.Ivić").name == "Ivo Ivić"
    assert registry.resolve("Ana Anić").society == "SOV"


# ── Statement index ───────────────────────────────────────────────────


def _touch(directory: Path, *names: str) -> None:
    for name in names:
        (directory / name).write_bytes(b"x")


def test_scan_skips_templates_notes_and_folders(tmp_path: Path) -> None:
    _touch(
        tmp_path,
        "Izjava_LKukuljan.pdf",
        "!!Izjava_SUE_član_2021_prazna.pdf",
        "!!!Fale_Brane.txt",
        "desktop.ini",
    )
    (tmp_path / "Prazne").mkdir()
    izjave = scan_izjave(tmp_path)
    assert [izjava.person for izjava in izjave] == ["LKukuljan"]


def test_index_links_statements_through_the_registry(tmp_path: Path) -> None:
    """SB shorthand ↔ registry canonical ↔ izjava token: one person."""
    _touch(tmp_path, "Izjava_LKukuljan.pdf", "Izjava_MRakovac_Šverda.pdf")
    registry = _registry(Person(name="Lovel Kukuljan"), Person(name="Marko Rakovac"))
    index = StatementIndex(scan_izjave(tmp_path), registry)

    assert [i.path.name for i in index.statements_for("L.Kukuljan")] == ["Izjava_LKukuljan.pdf"]
    # Scope does not matter for LINKING — only for coverage.
    assert [i.path.name for i in index.statements_for("Marko Rakovac")] == [
        "Izjava_MRakovac_Šverda.pdf"
    ]
    assert index.orphan_izjave() == []
    assert index.missing_statement_people() == []


def test_index_reports_orphans_and_people_without_statements(tmp_path: Path) -> None:
    _touch(tmp_path, "Izjava_NNepoznat.pdf")
    registry = _registry(Person(name="Lovel Kukuljan"))
    index = StatementIndex(scan_izjave(tmp_path), registry)
    assert [i.person for i in index.orphan_izjave()] == ["NNepoznat"]
    assert [p.name for p in index.missing_statement_people()] == ["Lovel Kukuljan"]


# ── Per-person linkage on the dossier ─────────────────────────────────


def _statement_file(name: str) -> ArchiveFile:
    return ArchiveFile(path=Path("C:/tmp/izjave") / name, role=FileRole.STATEMENT)


def _dossier(**kwargs) -> CaveDossier:
    base = dict(
        gathered={Source.SB, Source.STATEMENTS},
        object_name="Konglomeratača",
        locality="Šverda",
    )
    base.update(kwargs)
    return CaveDossier(**base)


def test_link_covers_scoped_izjava_only_inside_its_locality() -> None:
    dossier = _dossier(
        drawing_authors=["A.Ciceran"],
        statement_files=[_statement_file("Izjava_ACiceran_Šverda.pdf")],
    )
    entry = link_person_statements(dossier)[0]
    assert entry.role is PersonRole.DRAWING_AUTHOR
    assert entry.statements and entry.covering  # Šverda cave → covered

    elsewhere = _dossier(
        locality="Učka",
        drawing_authors=["A.Ciceran"],
        statement_files=[_statement_file("Izjava_ACiceran_Šverda.pdf")],
    )
    entry = link_person_statements(elsewhere)[0]
    assert entry.statements and not entry.covering  # linked, but scope elsewhere


def test_link_marks_registry_membership_three_valued() -> None:
    dossier = _dossier(drawing_authors=["L.Kukuljan"])
    no_registry = link_person_statements(dossier)[0]
    assert no_registry.in_registry is None  # no registry consulted ≠ unknown

    registry = _registry(Person(name="Lovel Kukuljan"))
    resolved = link_person_statements(dossier, registry=registry)[0]
    assert resolved.in_registry is True
    assert resolved.canonical == "Lovel Kukuljan"

    unknown = link_person_statements(
        _dossier(team_members=["Netko Nov"]), registry=registry
    )[0]
    assert unknown.in_registry is False


def test_link_skips_finder_shaped_names_in_the_author_cell() -> None:
    """Only `N.Surname` marks a survey author (user, 2026-08-30); the finders
    that share the SB cell get no entry — and hence no gate, no warning."""
    dossier = _dossier(drawing_authors=["L.Kukuljan", "Tin", "Denis Medica", "vedran"])
    entries = link_person_statements(dossier)
    assert [entry.name for entry in entries] == ["L.Kukuljan"]


# ── The gates ─────────────────────────────────────────────────────────


def test_gate1_blocks_author_whose_izjava_covers_another_locality() -> None:
    dossier = _dossier(
        locality="Učka",
        drawing_authors=["A.Ciceran"],
        statement_files=[_statement_file("Izjava_ACiceran_Šverda.pdf")],
    )
    report = evaluate(dossier)
    scoped = [
        issue
        for issue in report.blockers_for(GateLevel.SUE)
        if issue.code is IssueCode.MISSING_STATEMENT
    ]
    assert len(scoped) == 1
    assert "scope" in scoped[0].message


def test_gate2_warns_per_person_missing_statement_but_never_blocks() -> None:
    """The user's G2 (2026-08-30): a named person with no izjava on file warns."""
    dossier = _dossier(
        recorder="L.Kukuljan",
        team_members=["L.Kukuljan", "Ivo Ivić"],
        statement_files=[_statement_file("Izjava_LKukuljan.pdf")],
    )
    report = evaluate(dossier)
    warnings = [
        issue
        for issue in report.warnings_for(GateLevel.CROSPELEO)
        if issue.code is IssueCode.MISSING_STATEMENT
    ]
    assert len(warnings) == 1
    assert "Ivo Ivić" in warnings[0].message
    assert warnings[0].level is GateLevel.CROSPELEO
    assert warnings[0].severity is Severity.WARNING
    # Gate 1 must not see it, and it must not block anything.
    assert not [
        issue
        for issue in report.issues_for(GateLevel.SUE)
        if issue.code is IssueCode.MISSING_STATEMENT
    ]


def test_gate2_does_not_repeat_an_author_already_blocked_at_gate1() -> None:
    dossier = _dossier(drawing_authors=["I.Ivić"], team_members=["I.Ivić"])
    report = evaluate(dossier)
    statement_issues = [i for i in report.issues if i.code is IssueCode.MISSING_STATEMENT]
    assert [issue.severity for issue in statement_issues] == [Severity.BLOCKER]


def test_gate2_warns_when_a_person_is_not_in_the_registry() -> None:
    registry = _registry(Person(name="Lovel Kukuljan"))
    dossier = _dossier(team_members=["Netko Nov"])
    dossier.person_statements = link_person_statements(dossier, registry=registry)
    report = evaluate(dossier)
    unknown = [i for i in report.issues if i.code is IssueCode.UNKNOWN_PERSON]
    assert len(unknown) == 1
    assert "Netko Nov" in unknown[0].message
    assert unknown[0].severity is Severity.WARNING


def test_statement_gates_stay_unchecked_until_the_dir_is_scanned() -> None:
    dossier = CaveDossier(gathered={Source.SB}, drawing_authors=["Ivo Ivić"])
    report = evaluate(dossier)
    labels = {rule.label for rule in report.unchecked if rule.source is Source.STATEMENTS}
    assert labels == {"Izjava za katastar (po autoru)", "Izjava po osobi (registar osoba)"}
