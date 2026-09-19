# 4I — Isječak karte

**The map excerpt for a cave**, fetched from georef.hr and filed on the Drive.

## What it does

Takes a cave's HTRS96 coordinates from its SB row, drives georef.hr in a real
browser, and delivers a **marker-centred 5:4 PNG** into the shared
`!!Isječci karte` Drive folder as `SB_<padded broj>.png`, plus a row in
`!georef_zapisi.csv` recording what was fetched and when.

## Commands

```powershell
cavedossier karta 1220           # fetch the excerpt for one cave
cavedossier karta 1220 --force   # refresh one that already exists (default: skip)
cavedossier karta 1220 --debug   # headed browser + step screenshots
```

The Redni broj is the only input — coordinates come from the SB row.
**4O-osz calls this for you** when a prefill needs an excerpt that is missing or
stale, so you rarely run it by hand.

## How it works

A headed/headless Playwright flow: log in, navigate, enter the coordinates in
the coordinate tool, switch to the right base map, save server-side, then crop
the screenshot around the marker to a 5:4 frame within a PNG size budget.
Artifacts of every run — the screenshot, the result JSON, the Playwright trace
and log — land in `runs/georef/<broj>/` at the workspace root for debugging.

**The collection self-heals.** The Drive folder is hand-managed by
non-technical people, so files get renamed, deleted and re-added. Each run
re-derives what should be there rather than assuming the last run's state, and a
failed delivery degrades to the local `runs/` copy instead of erroring out.
No workflow here requires a manual cleanup ritual.

## Where things are

- Code: [`src/cave_dossier/georef/`](src/cave_dossier/georef/) — `worker.py` orchestrates,
  `flows.py` is the page flow, `client.py` the browser, `selectors.py` the DOM map
- `selectors.yaml` lives **inside the package**, beside the client that parses it:
  it is a runtime input, not per-machine config, so it travels with its code
- Credentials: `GEOREF_*` in `.env`, never in committed config
- Tests: [`tests/`](tests/)
- Why: [`docs/design-decisions.md`](../../docs/design-decisions.md)

## Status

Operational (M3). The 5:4 format and the self-healing collection both landed
2026-08-30.
