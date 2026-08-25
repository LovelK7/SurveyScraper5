# Automatic commit + push

`auto-commit.sh` gives the repo a version history and an off-machine GitHub
backup without anyone deciding what to commit. It stages everything `.gitignore`
allows, commits it, and pushes to `origin/main`.

Wired up in [../settings.json](../settings.json):

| Hook | Runs | Behaviour |
|---|---|---|
| `Stop` | after each response | **Checkpoint** — throttled to one commit per 30 min. Pushes in the background so you never wait on the network. |
| `SessionEnd` | on exit, `/clear`, logout | **Session end** — ignores the throttle. Pushes synchronously so the result is known before the session dies. |

Both are no-ops when the tree is clean, so idle turns cost nothing.

## Relationship to `/wrap-up`

`/wrap-up` still owns the curated commit: it updates `STATUS.md`, appends the
session block, then commits and pushes with a real message. The hook is the
safety net underneath it — it catches work when the session is killed, crashes,
or is simply closed without a wrap-up. After a wrap-up the tree is clean, so the
session-end hook does nothing.

Auto-commits are subject-tagged `chore(auto):` so they are easy to skip when
reading history:

```bash
git log --oneline --invert-grep --grep='^chore(auto)'   # only the curated commits
```

## Safety properties

- **Only this repo.** It resolves the repo from its own file location and
  verifies that against `git rev-parse --show-toplevel` by inode, so it can
  never act on the read-only `../cSurvey` or `../crospeleo-automation` clones.
- **Only `main`.** Any other branch, and it refuses and says so.
- **Never mid-operation.** Skips while a merge, rebase, cherry-pick, or revert
  is in progress.
- **Never wedges the repo.** Files over `MAX_FILE_MB` (50) are left unstaged
  rather than committed into an unpushable blob; the commit body records what
  was skipped.
- **Never loses a failed push.** A push that fails (offline, credentials) leaves
  the commit intact; every later hook run retries the backlog.
- **One writer.** A lock directory under `.git/` keeps concurrent sessions from
  colliding.

## Tuning

Edit the constants at the top of `auto-commit.sh`:

```sh
THROTTLE_MINUTES=30   # gap between checkpoint commits
MAX_FILE_MB=50        # larger files are left uncommitted
PUSH=1                # 0 = commit locally, never push
```

To turn the automation off entirely, remove the `Stop` / `SessionEnd` entries
from `../settings.json` (or review them via `/hooks`).

## Troubleshooting

Every run appends to `.claude/auto-commit.log` (gitignored) — commit SHAs, push
results, and the reason for any skip. Start there.

After editing `settings.json`, Claude Code may need `/hooks` opened once, or a
restart, before the change is picked up.
