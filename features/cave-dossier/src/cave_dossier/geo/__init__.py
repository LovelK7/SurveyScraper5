"""Part 2.1b — where a point is, administratively and vertically.

Locality finder (županija / grad-općina / najbliže mjesto / lokalitet from
HTRS96 coordinates) and elevation finder (Kota ulaza from DGU's open INSPIRE
EL-COV grid). Everything is fail-soft: missing data files, missing optional
dependencies or network trouble degrade to "unavailable", never to a crash —
the prefill that consumes these findings must always produce its document.

Ported from crospeleo-automation's ``locality/`` package (docs/PORTING.md);
the elevation module is new. All inputs are HTRS96/TM (EPSG:3765), SB-native.
"""

from cave_dossier.geo.models import (
    AdminPlacement,
    ElevationFinding,
    LocalityFinding,
    NamedPlaceHit,
)

__all__ = [
    "AdminPlacement",
    "ElevationFinding",
    "LocalityFinding",
    "NamedPlaceHit",
]
