# Task brief: Field app — photos + voice memos from the entrance to the leaf, transcribed by 4O

- **ID:** 0001-field-app
- **Status:** `idea` — explored 2026-11-09, stored for later; nothing built, no decision taken
- **Owner:** both
- **Opened:** 2026-11-09
- **Read first:** [the superapp CLAUDE.md](../../../../CLAUDE.md), [1T README](../../README.md), [prod/drive-layout.md](../../../../prod/drive-layout.md) (the intake-leaf contract this extends), [ARCHITECTURE.md §1T](../../../../ARCHITECTURE.md#part-1)

> Self-contained: a fresh session can pick this up from cold. It is a wide-brush exploration, not a
> design — every choice below is a recommendation to confirm, not a settled decision.

## Contents

1. [Problem](#1-problem)
2. [Data flow](#2-data-flow)
3. [Where uploads land](#3-where-uploads-land)
4. [Transcription](#4-transcription)
5. [Stack: Kotlin, not React](#5-stack-kotlin-not-react)
6. [Phasing](#6-phasing)
7. [Further ideas](#7-further-ideas)
8. [Open questions](#8-open-questions)

---

## 1. Problem

At the entrance the team takes photos and knows the most about the cave; by the time 4O is filled
in, that knowledge is a memory. The wish: shuttle entrance photos straight to the right place, record
a voice description that is **kept on the phone while there is no signal and sent when there is**,
and have it **transcribed by a local model** (Whisper) at leisure — hours are fine. The only outcome
that matters is a transcript waiting when 4O is done.

The 1T field app has been PARKED since the manual workflow sufficed; its one live interface is the
intake-leaf contract (`SB_<broj>_…` under `!Za digitalizirat`). This brief keeps that contract.

## 2. Data flow

```
 PHONE (offline-first)                  DRIVE (prod)                   WORKER (Windows + Drive Desktop)
 "posjet" = one visit:                  !!!Digitalizacija/             cavedossier teren sweep
   uuid, GPS fix (60 s avg + accuracy),   !Teren inbox/<uuid>/          1. match visit → SB row (broj if
   time, author (registar osoba),   ──►     manifest.json        ──►       picked, else GPS nearest +
   SB broj or "novi objekt",                foto_*.jpg                     core/matching)
   photos[], memos[] (.opus)                memo_*.opus                 2. move into SB_<broj>_…/_teren/
 local outbox; upload when online                                       3. photos → leaf (4F picks up)
                                                                        4. memo → faster-whisper → memo.txt/.json
                                                                        5. (opt.) LLM → OSZ field proposals
                                                                        dashboard 4O: transcript beside the OSZ
```

Fits the standing rules:
- the **leaf stays the unit of work** — 4F, 4O, 6P need no new concept;
- the **worker reads only the synced Drive** — the "no Google API" rule holds on the processing side;
- **transcripts are proposals**, never silent writes (either a marked draft in *Osnovni opis* via the
  `osz prefill` writer, or display-only on the dashboard — a decision-record entry to make).

The hard problem is **identity, not the app**: a new cave has no SB broj at the entrance. An offline
SB list on the phone (phase 2) plus GPS fallback matching makes the sweep reliable; a "novi objekt"
visit feeds the existing ★ *Novi objekt* recipe.

## 3. Where uploads land

Ranked:
1. **Google Apps Script web app as a relay** — deployed once, "execute as" the archivist; the phone
   POSTs file + shared token; the script writes into `!Teren inbox`. No per-user OAuth. Memos ≈ 1 MB
   (3 min Opus), photos 3–6 MB. *Verify payload/quota limits before relying on them.*
2. **Drive REST from the phone, per-user OAuth** — writing into an existing shared folder needs the
   restricted `drive` scope; unverified "testing" apps (<100 users) get tokens that expire every 7 days.
3. **Own endpoint** (tus resumable upload behind Tailscale / Cloudflare Tunnel) — most control, an
   always-on public machine to maintain.

**Drive Desktop does not run on Linux** — a Pi/Linux worker would need rclone (= the Drive API). Use a
small Windows box, or let the dashboard machine run the sweep as a background job while it is open.

## 4. Transcription

- `faster-whisper`, large-v3, CPU int8 — roughly real time to a few × real time on a laptop; no GPU.
- Try CLASSLA's Croatian Whisper fine-tunes on Hugging Face against stock large-v3 on ~10 real memos
  (a literary/dialect fine-tune may help or hurt on field speech).
- **`initial_prompt` vocabulary** — the cave's SB name + synonyms, the team from the registar osoba,
  terms from `shared/glossary.md` (*ponor, jama, sige, suženje…*). Cheapest fix for proper nouns.
- Local transcription keeps members' voices and cave locations off third-party services.

## 5. Stack: Kotlin, not React

| | **Kotlin + Jetpack Compose** ✅ | React Native / Expo | PWA |
|---|---|---|---|
| Upload when signal returns | WorkManager, `CONNECTED` constraint, survives reboots, backoff | possible, weaker background | ❌ weak Background Sync, evictable storage |
| Audio / GPS / camera | native | plugins | mic dies on screen lock |
| Reuse of the dashboard | — | none (dashboard is vanilla JS on a stdlib server) | some |
| iOS | no | yes | yes |

React Native only if iOS members are a hard requirement. Pieces: Room (outbox), MediaRecorder (Opus),
FusedLocation, the system camera intent, WorkManager. ~5 screens. ARCHITECTURE notes a prior Android
app to start from.

## 6. Phasing

- **Phase 0 — no app (1–2 sessions).** Any recorder app → share to the Google Drive app (which queues
  offline itself) into `!Teren inbox`, named `SB_<broj>_…`. Build `cavedossier teren sweep` + the
  Whisper worker + a *Transkript* panel on the dashboard's 4O page. If the transcripts are not useful
  at 4O, the app is saved.
- **Phase 1** — Kotlin MVP: visit, GPS, photos, memo, outbox, upload.
- **Phase 2** — offline SB cave list (dashboard exports a slim JSON to the Drive; the app caches it).
- **Phase 3** — LLM structuring: transcript → OSZ field proposals.

New pieces this would touch: a `config.yaml` `archive:` key for `!Teren inbox`, a 1T subpackage
(`pyproject.toml` + `pipeline.yaml`), `prod/drive-layout.md`, the 4O dashboard page.

## 7. Further ideas

Each tied to a bottleneck that exists today:

1. **Duplicate warning at the entrance** — SB + Katastar RH (4595 rows, still untouched) cached
   offline: *"30 m from SB 1220 – the same cave?"* (cf. the SB 1458 clash).
2. **Structured field zapisnik on the phone** — CroSpeleo vocabularies as taps, voice only for the
   narratives; retires the "still unstructured, heuristic-fed" backlog list and the Word-vs-Docs dual
   reader M4 waits on.
3. **Izjava check before leaving the field** — the app knows the team and warns *"Ivan nema izjavu"*;
   stretch: on-phone izjava (drawn signature → PDF in `!!Izjave`), if legally acceptable. Hits the
   5D/5O izjava blocker at the source.
4. **Pločica OCR + GPS quality stamp** — half of 6P's §5.1 gate checked in the field; *Izvor
   koordinata = GPS* becomes a fact, not a default.
5. **Photo QA on site** — blur/exposure check, tag ulaz vs okolina, author from the login (4F no longer
   needs the OSZ's *Autor fotografije* cell; the waiting-photo queue stops growing).
6. **TopoDroid bridge** — ship `.tdx`/`.csx` in the same visit so 3N KORAK 1 starts with no copying;
   stretch: in-cave voice notes matched to stations by timestamp → survey notes for the drafter.
7. **"Za istražit" field map** — the queue + LiDAR candidates on offline tiles; found / not found /
   something else → dopune proposals. Trip planning from SB.
8. **Per-cave status for the team** — the dashboard's dependency graph published read-only
   (*"SB 1328 čeka: izjavu, fotografiju ulaza"*), optional weekly digest.
9. **Search across the archive** — transcripts + OSZ narratives indexed ("ponori s propuhom kod Gospića").
10. **Close the loop downstream** — 6P delivery triggers the crospeleo-automation submission.

Suggested first pick when the time comes: **phase 0 + ideas 1 and 3** — cheap, built on data already
held (SB, Katastar RH, the registar osoba), each removing a pain felt today.

## 8. Open questions

- Transport: Apps Script relay vs per-user OAuth vs own endpoint (§3).
- Transcript into the OSZ as a marked draft, or dashboard-only?
- Which machine is the worker — a dedicated Windows box or the dashboard machine on demand?
- Do any members need iOS?
- Is a phone-signed izjava acceptable to the registry?
