"""Locality finder: županija / grad-općina / najbliže mjesto / lokalitet.

Restructured from crospeleo-automation ``locality/locality_enricher.py``
(docs/PORTING.md). That enricher CORRECTS fields parsed out of a filled OSZ;
this finder SYNTHESIZES values for a possibly empty SB row, under the 2.1b
precedence rule (user, 2026-08-30): **SB wins** — an SB value is never
replaced, only annotated when the geographic evidence disagrees; an empty
one is filled from DGU/RGI.

The battle-tested heuristics are ported verbatim: the settlement screening
radius (Veli Brgud case), the locality append radius, the asymmetric fuzzy
cutoffs, and the ``vrstaobiljezja`` exclusion list (object 525's chapel).
"""

from __future__ import annotations

import logging

from cave_dossier.core.config import Settings
from cave_dossier.geo.admin_lookup import AdminLookup
from cave_dossier.geo.models import LocalityFinding, NamedPlaceHit
from cave_dossier.geo.rgi_client import RGIClient, RGIClientConfig
from cave_dossier.geo.toponym_matcher import fuzzy_best_match, normalize_for_matching

# Wider radius to catch a nearby settlement whose polygon edge sits just
# beyond the RGI query (Veli Brgud, 2026-05-12: its naselje polygon is ~3 km
# from cave 843's entrance, outside the 2 km RGI hits, yet its name had been
# smuggled into the OSZ as "lokalitet").
_NASELJE_SCREEN_RADIUS_M = 5_000.0

# Closest non-settlement RGI hit within this radius fills an empty Lokalitet.
_LOCALITY_APPEND_RADIUS_M = 1_500.0

# Fuzzy-match cutoffs.  nearest_place uses 75 because recorded values often
# carry case / spelling drift from the formal naselje name; locality tokens
# use 85 because only a confident settlement match should be flagged.
_NEAREST_PLACE_MATCH_CUTOFF = 75.0
_LOCALITY_SETTLEMENT_CUTOFF = 85.0

# vrstaobiljezja values that are NOT suitable as a "Lokalitet" hint.
# RGI uses freeform Croatian for this field, so we match by substring on
# the accent-folded lowercase text.  Stems are deliberately short so a
# single keyword covers all inflections / diminutives — e.g. ``kapel``
# matches both ``kapela`` and ``kapelica``.
#
# Three exclusion categories:
#   1. Infrastructure (roads, transit, hospitality) — not landform.
#   2. Populated places — those belong on "Najbliže mjesto" instead.
#   3. Religious / commemorative point features — chapels, churches,
#      monuments etc. are precise man-made points, not the surrounding
#      terrain a cave belongs to.  Object 525 ("Bunker iznad Trinajstići
#      1", 2026-05-24) surfaced this gap: a 420-m-away chapel "Majke
#      Božje od Zdravlja" was appended as the cave's Lokalitet.
_NON_LOCALITY_VRSTA_KEYWORDS = (
    # 1. Infrastructure
    "cesta",
    "autocesta",
    "postaja",
    "crpka",
    "odmoriste",
    "prijelaz",
    "hotel",
    "restoran",
    "motel",
    "kamp",
    "kolodvor",
    "parkiraliste",
    # 2. Populated places (go to Najbliže mjesto)
    "naselje",
    # 3. Religious / commemorative point features
    "kapel",      # kapela / kapelica
    "crkv",       # crkva / crkvica
    "samostan",
    "manastir",
    "katedral",
    "bazilik",
    "svetis",     # svetište
    "zvonik",
    "spomenik",
)

logger = logging.getLogger(__name__)


def is_topographic_locality_feature(vrsta: str | None) -> bool:
    """True when an RGI ``vrstaobiljezja`` belongs in "Lokalitet".

    Returns ``True`` for an unknown / empty classification (conservative —
    keep candidates we can't classify); ``False`` only on a substring match
    against ``_NON_LOCALITY_VRSTA_KEYWORDS`` (road, settlement, chapel, …).
    """
    if not vrsta:
        return True
    normalised = normalize_for_matching(vrsta)
    return not any(kw in normalised for kw in _NON_LOCALITY_VRSTA_KEYWORDS)


def build_finder(settings: Settings) -> "LocalityFinder":
    """A LocalityFinder wired to the configured data dir and RGI radius."""
    return LocalityFinder(
        rgi_client=RGIClient(
            RGIClientConfig(
                radius_m=settings.geo_rgi_radius_m,
                offline_dir=settings.geo_data_dir,
            )
        ),
        admin_lookup=AdminLookup(settings.geo_data_dir),
    )


class LocalityFinder:
    """Synthesize the four OSZ locality fields for one entrance point."""

    def __init__(self, rgi_client: RGIClient, admin_lookup: AdminLookup) -> None:
        self.rgi_client = rgi_client
        self.admin_lookup = admin_lookup

    def locate(
        self,
        x_htrs: float,
        y_htrs: float,
        sb_lokalitet: str | None = None,
        sb_najblize_mjesto: str | None = None,
    ) -> LocalityFinding:
        finding = LocalityFinding()

        admin = self.admin_lookup.lookup(x_htrs, y_htrs)
        finding.admin_available = admin.source != "unavailable"
        if not finding.admin_available:
            finding.notes.append(
                "DGU administrativne granice nisu dostupne — pokreni "
                "`cavedossier geo fetch-data` (Županija/Grad-općina ostaju prazni)."
            )
        finding.zupanija = admin.zupanija
        finding.grad_opcina = admin.opcina

        hits = self.rgi_client.query_nearby(x_htrs, y_htrs)
        finding.rgi_hits = hits
        finding.rgi_offline_fallback = self.rgi_client.used_offline_fallback
        if finding.rgi_offline_fallback:
            finding.notes.append(
                "RGI WFS nedostupan — korišten lokalni rgi_named_places.gpkg "
                "(podaci mogu kasniti za registrom)."
            )
        elif not hits:
            finding.rgi_available = False

        nearby_naselja = self._nearby_naselja(x_htrs, y_htrs, admin.naselje, hits)
        self._resolve_najblize_mjesto(finding, sb_najblize_mjesto, admin.naselje, nearby_naselja)
        self._resolve_lokalitet(finding, sb_lokalitet, hits, nearby_naselja)
        return finding

    # ── internals ────────────────────────────────────────────────────
    def _nearby_naselja(
        self,
        x: float,
        y: float,
        admin_naselje: str | None,
        hits: list[NamedPlaceHit],
    ) -> list[str]:
        """Names known to be settlements near the entrance: the widened DGU
        polygon set + the containing naselje + RGI hits typed 'naselje'
        (covers areas where the DGU set is sparse)."""
        names = self.admin_lookup.nearby_naselje_names(
            x, y, radius_m=_NASELJE_SCREEN_RADIUS_M
        )
        if admin_naselje and admin_naselje not in names:
            names.append(admin_naselje)
        for hit in hits:
            if (hit.vrstaobiljezja or "").strip().lower() == "naselje":
                if hit.geografskoime and hit.geografskoime not in names:
                    names.append(hit.geografskoime)
        return names

    def _resolve_najblize_mjesto(
        self,
        finding: LocalityFinding,
        sb_value: str | None,
        admin_naselje: str | None,
        nearby_naselja: list[str],
    ) -> None:
        if sb_value:
            finding.najblize_mjesto = sb_value
            finding.najblize_mjesto_source = "sb"
            if nearby_naselja and fuzzy_best_match(
                sb_value, nearby_naselja, score_cutoff=_NEAREST_PLACE_MATCH_CUTOFF
            ) is None:
                alternative = f"; DGU naselje ulazne točke: {admin_naselje!r}" if admin_naselje else ""
                finding.notes.append(
                    f"Najbliže mjesto (SB) {sb_value!r} ne odgovara nijednom naselju "
                    f"unutar {_NASELJE_SCREEN_RADIUS_M / 1000:.0f} km{alternative}. "
                    "SB vrijednost je zadržana."
                )
            return
        if admin_naselje:
            finding.najblize_mjesto = admin_naselje
            finding.najblize_mjesto_source = "geo-admin"

    def _resolve_lokalitet(
        self,
        finding: LocalityFinding,
        sb_value: str | None,
        hits: list[NamedPlaceHit],
        nearby_naselja: list[str],
    ) -> None:
        if sb_value:
            finding.lokalitet = sb_value
            finding.lokalitet_source = "sb"
            for token in _split_locality(sb_value):
                if nearby_naselja and fuzzy_best_match(
                    token, nearby_naselja, score_cutoff=_LOCALITY_SETTLEMENT_CUTOFF
                ) is not None:
                    finding.notes.append(
                        f"Lokalitet (SB) sadrži naselje {token!r} — naselja pripadaju "
                        "polju 'Najbliže mjesto'. SB vrijednost je zadržana."
                    )
            return
        for hit in hits:  # hits arrive distance-sorted
            if not hit.geografskoime:
                continue
            if not is_topographic_locality_feature(hit.vrstaobiljezja):
                continue
            if hit.distance_m is not None and hit.distance_m > _LOCALITY_APPEND_RADIUS_M:
                break
            finding.lokalitet = hit.geografskoime
            finding.lokalitet_source = "geo-rgi"
            finding.notes.append(
                f"Lokalitet iz RGI: {hit.geografskoime!r} "
                f"({hit.vrstaobiljezja or 'bez vrste'}, {hit.distance_m:.0f} m)."
                if hit.distance_m is not None
                else f"Lokalitet iz RGI: {hit.geografskoime!r}."
            )
            return


def _split_locality(text: str) -> list[str]:
    import re

    parts = re.split(r"[,;/]+", text)
    return [p.strip() for p in parts if p and p.strip()]
