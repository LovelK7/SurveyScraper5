---
name: wrap-up
description: End-of-session ritual — update STATUS.md, append the session block, capture ideas, then commit everything on main. Invoke at the end of every working session.
---

# /wrap-up [session_label]

End-of-session ritual for SurveyScraper5. Unlike crospeleo-automation's wrap-up
(reflection only, never commits), this one **owns the commit** — the user is the
sole developer, works on a single `main` branch, and wants automated commits with
a single clean history.

## Guards (check before anything else)

- Working directory must be `C:\Users\Lovel.IZRK-LK-NB\Programming\SurveyScraper5`
  and `git rev-parse --show-toplevel` must resolve to it. **Never** run git in
  `../cSurvey` or `../crospeleo-automation` (read-only reference repos).
- Branch must be `main`. If not, stop and ask the user.
- If the session was conversational-only (no file changes, `git status` clean),
  write a one-line note that nothing shipped and stop — no empty commits.

## Steps

### 1 — Recall this session's scope

From the conversation (not a mechanical tree audit): files created/modified, bugs
fixed, decisions made, things investigated but deliberately not changed (and why).

### 2 — Update STATUS.md

- Bump the `Updated:` date.
- Part-status table: adjust any part whose state changed.
- Current-milestone checklist: tick finished items; when a milestone completes,
  replace the checklist with the next milestone's.
- **Waiting on user**: add anything new the session got blocked on; remove resolved items.
- Recent sessions: prepend this session's one-liner (keep last 3).

### 3 — Append the session block

To the touched feature's `sessions/SESSIONS.md` (newest on top), in the
established format:

```
### YYYY-MM-DD — <short title> (agent) ✅|◐|✗

- **Did:** <what was done, concrete: files, functions, before/after>
- **Result:** <how it went; honest limits>
- **Learned:** <non-obvious findings only — data quirks, external-system
  constraints, design decisions and their why. Skip anything obvious from the diff.>
- **Next:** <the natural next step>
```

If the session touched multiple features, one block per touched feature (scoped
to what happened there). Root-level-only sessions (docs, skills) go into the
feature most affected, or the closest one.

### 4 — Capture ideas

New ideas / "we should also" items that surfaced → append to the feature's
`backlog/ideas.md` (one line each, dated). This is the implementation log for
finding new ideas — don't lose them in chat history.

### 4b — Pipeline doctor (pre-commit gate)

```powershell
python tools/pipeline_doctor.py
```

Fix every FAIL before committing (broken doc links, CLI commands missing from
the README, `_INDEX` drift); triage WARNs (fix cheap ones, backlog the rest);
re-confirm the STALE? status claims — this session's work may have just
invalidated one. If `/feature-dev` was followed, this is already clean.

### 5 — Commit

```powershell
git add -A
git commit -m "<one-line summary of the session>" -m "<2-4 line body: key changes, milestone progress>"
git push origin main
```

- One commit per wrap-up (no splitting), message in imperative mood, mention the
  milestone (e.g. "M1:") when applicable.
- End the message body with: `Co-Authored-By: Claude <noreply@anthropic.com>` when
  an agent did the work.
- Push to `origin` (GitHub) — it is the off-machine backup. Never amend previous
  commits.

**Relationship to the auto-commit hook.** `.claude/hooks/auto-commit.sh` also
commits and pushes — on a throttled checkpoint during long sessions and again at
session end (see [../../hooks/README.md](../../hooks/README.md)). That hook is the
safety net; this wrap-up commit is the curated, narrative one. Doing the wrap-up
commit here means the session-end hook finds a clean tree and does nothing, which
is the intended outcome. If `chore(auto):` commits from this session already exist,
leave them — do not squash or rewrite history to absorb them.

### 6 — Report

Short output to the user: What shipped / What we learned / Worth following up
(bullets, concrete). Skip empty sections.
