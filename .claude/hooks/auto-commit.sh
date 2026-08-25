#!/usr/bin/env bash
# Automatic commit + push for SurveyScraper5.
#
# Invoked by the hooks in .claude/settings.json:
#   auto-commit.sh checkpoint    <- Stop hook, throttled (see THROTTLE_MINUTES)
#   auto-commit.sh session-end   <- SessionEnd hook, always runs
#
# The user is the sole developer on a single `main` branch and wants a version
# history + GitHub backup without hand-picking what to commit. So: stage
# everything .gitignore allows, commit, push. /wrap-up still owns the curated,
# narrative commits; this is the safety net that catches whatever it misses.
#
# Safe by construction: it operates on the repo that contains THIS script (never
# ../cSurvey or ../crospeleo-automation), refuses any branch but main, and skips
# repos in a mid-merge/rebase state.

set -uo pipefail

THROTTLE_MINUTES=30     # minimum gap between checkpoint commits
MAX_FILE_MB=50          # files larger than this are left unstaged (GitHub hard-caps at 100MB)
PUSH=1                  # 0 disables pushing (commits still happen)

MODE="${1:-checkpoint}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG="$REPO/.claude/auto-commit.log"
STAMP="$REPO/.git/claude-autocommit-stamp"
LOCK="$REPO/.git/claude-autocommit.lock"

g() { git -C "$REPO" "$@"; }
log() { printf '%s  [%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$MODE" "$*" >>"$LOG"; }

# Emit a one-line notice into the Claude Code UI, then exit.
say() {
  local m="$1"
  m="${m//\\/\\\\}"   # escape backslashes first, then quotes, for JSON
  m="${m//\"/\\\"}"
  printf '{"systemMessage":"%s","suppressOutput":true}\n' "$m"
  exit 0
}
quiet() { exit 0; }

# Deliver commits an earlier run made but failed to push (e.g. machine was
# offline). Runs on every path that exits without committing, so a failed push
# is always retried on the next hook rather than waiting for the next commit.
push_backlog() {
  [ "$PUSH" = "1" ] || return 0
  [ -n "$(g log --oneline @{u}..HEAD 2>/dev/null)" ] || return 0
  log "retrying push of unpushed commit backlog"
  ( GIT_TERMINAL_PROMPT=0 g push --quiet origin main >>"$LOG" 2>&1     && log "backlog pushed" || log "backlog push FAILED" ) &
}

# --- guards ------------------------------------------------------------------
[ -d "$REPO/.git" ] || quiet
# Compare by identity, not by string: on Windows `rev-parse --show-toplevel`
# prints C:/... where bash pwd prints /c/..., and either side may be 8.3-shortened.
top="$(g rev-parse --show-toplevel 2>/dev/null)"
[ -n "$top" ] && [ "$REPO" -ef "$top" ] || quiet
[ "$(basename "$REPO")" = "SurveyScraper5" ] || quiet

branch="$(g rev-parse --abbrev-ref HEAD 2>/dev/null)"
if [ "$branch" != "main" ]; then
  log "skipped: on branch '$branch', not main"
  say "auto-commit skipped — on branch '$branch', not main."
fi

for f in MERGE_HEAD CHERRY_PICK_HEAD REVERT_HEAD rebase-merge rebase-apply; do
  if [ -e "$REPO/.git/$f" ]; then
    log "skipped: repo mid-operation ($f present)"
    say "auto-commit skipped — repo is mid-merge/rebase. Finish it, then commit."
  fi
done

# --- throttle (checkpoints only) ---------------------------------------------
now=$(date +%s)
if [ "$MODE" = "checkpoint" ] && [ -f "$STAMP" ]; then
  last=$(cat "$STAMP" 2>/dev/null || echo 0)
  case "$last" in ''|*[!0-9]*) last=0 ;; esac
  if [ $(( now - last )) -lt $(( THROTTLE_MINUTES * 60 )) ]; then quiet; fi
fi

# --- single-writer lock ------------------------------------------------------
mkdir "$LOCK" 2>/dev/null || quiet
trap 'rmdir "$LOCK" 2>/dev/null' EXIT

# --- anything to do? ---------------------------------------------------------
dirty="$(g status --porcelain 2>/dev/null)"
if [ -z "$dirty" ]; then
  # Deliberately no stamp write: the throttle clocks time since the last
  # auto-commit, so idle turns can never starve the next checkpoint.
  # Nothing new, but earlier commits may still be unpushed (offline last time).
  if [ "$PUSH" = "1" ] && [ -n "$(g log --oneline @{u}..HEAD 2>/dev/null)" ]; then
    log "clean tree, pushing backlog of unpushed commits"
    ( GIT_TERMINAL_PROMPT=0 g push --quiet origin main >>"$LOG" 2>&1 \
      && log "backlog pushed" || log "backlog push FAILED" ) &
  fi
  quiet
fi

# --- stage -------------------------------------------------------------------
g add -A >>"$LOG" 2>&1

# Leave oversized files out rather than wedging the repo with an unpushable blob.
oversized=""
while IFS= read -r f; do
  [ -n "$f" ] || continue
  [ -f "$REPO/$f" ] || continue
  size=$(stat -c %s "$REPO/$f" 2>/dev/null || echo 0)
  if [ "$size" -gt $(( MAX_FILE_MB * 1024 * 1024 )) ]; then
    g reset -q -- "$f" >>"$LOG" 2>&1
    oversized="$oversized $f"
  fi
done < <(g diff --cached --name-only --diff-filter=ACM 2>/dev/null)

staged_count=$(g diff --cached --name-only 2>/dev/null | wc -l | tr -d ' ')
[ "$staged_count" = "1" ] && noun="file" || noun="files"
if [ "$staged_count" -eq 0 ]; then
  push_backlog
  [ -n "$oversized" ] && { log "nothing staged; oversized skipped:$oversized"; say "auto-commit skipped oversized file(s):$oversized — commit them deliberately or gitignore them."; }
  quiet
fi

# --- commit ------------------------------------------------------------------
# Scope = the two most-touched top-level areas, so the log stays scannable.
scope="$(g diff --cached --name-only \
  | awk -F/ '{ print (NF>2 ? $1"/"$2 : (NF>1 ? $1 : "(root)")) }' \
  | sort | uniq -c | sort -rn | head -2 | awk '{ print $2 }' | paste -sd',' - | sed 's/,/, /g')"
[ -n "$scope" ] || scope="repo"

if [ "$MODE" = "session-end" ]; then
  subject="chore(auto): session end — $scope ($staged_count $noun)"
else
  subject="chore(auto): checkpoint — $scope ($staged_count $noun)"
fi

body="Automatic commit by the $MODE hook (.claude/hooks/auto-commit.sh).
Not a curated commit — see /wrap-up commits for session narrative."
[ -n "$oversized" ] && body="$body

Skipped (over ${MAX_FILE_MB}MB, left uncommitted):$oversized"

g commit -q -m "$subject" -m "$body" -m "Co-Authored-By: Claude <noreply@anthropic.com>" >>"$LOG" 2>&1
rc=$?
echo "$now" >"$STAMP"

if [ $rc -ne 0 ]; then
  log "commit FAILED (rc=$rc): $subject"
  say "auto-commit FAILED — see .claude/auto-commit.log"
fi
sha="$(g rev-parse --short HEAD)"
log "committed $sha: $subject"

# --- push --------------------------------------------------------------------
if [ "$PUSH" != "1" ]; then say "auto-commit $sha ($staged_count $noun) — push disabled."; fi

if [ "$MODE" = "session-end" ]; then
  # Session is ending; push synchronously so the result is known before exit.
  if GIT_TERMINAL_PROMPT=0 g push --quiet origin main >>"$LOG" 2>&1; then
    log "pushed $sha to origin/main"
    say "auto-commit $sha ($staged_count $noun) pushed to GitHub."
  else
    log "push FAILED for $sha"
    say "auto-commit $sha ($staged_count $noun) committed, but push FAILED — see .claude/auto-commit.log"
  fi
else
  # Mid-session: never make the user wait on the network.
  ( GIT_TERMINAL_PROMPT=0 g push --quiet origin main >>"$LOG" 2>&1 \
    && log "pushed $sha to origin/main" || log "push FAILED for $sha (will retry next hook)" ) &
  say "Checkpoint $sha ($staged_count $noun) committed, pushing to GitHub."
fi
