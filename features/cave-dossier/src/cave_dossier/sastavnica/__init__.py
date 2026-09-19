"""Part 2.1e — the Nacrt's sastavnica (title block), prefilled from SB.

The Illustrator drafting route's one touchpoint with the pipeline: a drafter
places `SB_<broj>_sastavnica.pdf` into their document instead of typing the
fifteen values SB and the zapisnik already know. See
``docs/sastavnica-design.md`` for the measured template geometry and the rules
this package implements.
"""

from cave_dossier.sastavnica.prefill import (
    SastavnicaError,
    SastavnicaOutcome,
    run_prefill,
)

__all__ = ["SastavnicaError", "SastavnicaOutcome", "run_prefill"]
