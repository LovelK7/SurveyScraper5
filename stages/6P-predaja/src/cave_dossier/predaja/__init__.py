"""6P predaja — the last gate and delivery (`cavedossier deliver <Redni broj>`).

``plan`` is the read-only gate + plan the archivist reviews, ``stamp`` writes
the katastarski broj into the Nacrt PDF and the OSZ, ``apply`` executes an
approved plan (SB through Excel COM, then the archive dirs, then the leaf
into Arhiva). Design: ``stages/6P-predaja/docs/m6-delivery-design.md``.
"""
