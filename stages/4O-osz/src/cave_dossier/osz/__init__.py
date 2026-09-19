"""Part 2.1b — the OSZ document side.

``writer`` fills the v10 template (lxml on word/document.xml — content
controls are invisible to python-docx), ``addresses`` maps fields to table
coordinates per template version, ``prefill`` orchestrates SB + karta +
geo finders into a delivered ``SB_<padded>_OSZ.docx``.

Needs the ``[osz]`` extra (lxml); the geo finders degrade gracefully
without ``[geo]``.
"""

from cave_dossier.osz.models import FieldValue, PrefillResult, SBUpdate

__all__ = ["FieldValue", "PrefillResult", "SBUpdate"]
