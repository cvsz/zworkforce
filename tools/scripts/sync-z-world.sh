#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

REPO="cvsz/z-world"
BRANCH="main"
TARGET_DIR="${HOME}/z-world"
PUSH_AFTER_SYNC=false

usage() {
  cat <<'USAGE'
Usage:
  ./sync-z-world.sh [options]

Options:
  --dir PATH       Local repository directory (default: ~/z-world)
  --branch NAME    Branch to synchronize (default: main)
  --push           Push local commits to origin after synchronizing
  -h, --help       Show this help

Examples:
  ./sync-z-world.sh
  ./sync-z-world.sh --dir /home/cvsz/z-world
  ./sync-z-world.sh --push
USAGE
}

log() {
  printf '[z-world-sync] %s\n' "$*"
}

fail() {
  printf '[z-world-sync] ERROR: %s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "Required command not found: $1"
}

while (($# > 0)); do
  case "$1" in
    --dir)
      (($# >= 2)) || fail "--dir requires a path"
      TARGET_DIR="$2"
      shift 2
      ;;
    --branch)
      (($# >= 2)) || fail "--branch requires a branch name"
      BRANCH="$2"
      shift 2
      ;;
    --push)
      PUSH_AFTER_SYNC=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      fail "Unknown option: $1"
      ;;
  esac
done

require_command git
require_command gh

log "Checking GitHub authentication"
gh auth status -h github.com >/dev/null 2>&1 || {
  fail "GitHub CLI is not authenticated. Run: gh auth login -h github.com"
}

# Configure Git to use the GitHub CLI credential helper for HTTPS remotes.
gh auth setup-git >/dev/null 2>&1 || fail "Unable to configure GitHub credentials"

if [[ ! -e "$TARGET_DIR" ]]; then
  log "Cloning $REPO into $TARGET_DIR"
  mkdir -p "$(dirname "$TARGET_DIR")"
  gh repo clone "$REPO" "$TARGET_DIR" -- --branch "$BRANCH" --single-branch
elif [[ ! -d "$TARGET_DIR/.git" ]]; then
  fail "Target exists but is not a Git repository: $TARGET_DIR"
fi

cd "$TARGET_DIR"

EXPECTED_HTTPS="https://github.com/${REPO}.git"
EXPECTED_SSH="git@github.com:${REPO}.git"
ORIGIN_URL="$(git remote get-url origin 2>/dev/null || true)"

case "$ORIGIN_URL" in
  "$EXPECTED_HTTPS"|"$EXPECTED_SSH"|"https://github.com/${REPO}"|"git@github.com:${REPO}")
    ;;
  "")
    log "Adding origin remote"
    git remote add origin "$EXPECTED_HTTPS"
    ;;
  *)
    fail "Unexpected origin remote: $ORIGIN_URL"
    ;;
esac

log "Fetching origin, tags, and deleted branches"
git fetch origin --prune --tags

if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
  git switch "$BRANCH"
else
  git switch --create "$BRANCH" --track "origin/$BRANCH"
fi

STASH_CREATED=false
STASH_MESSAGE="z-world-sync-$(date -u +%Y%m%dT%H%M%SZ)"

if [[ -n "$(git status --porcelain=v1)" ]]; then
  log "Saving uncommitted local changes temporarily"
  git stash push --include-untracked --message "$STASH_MESSAGE" >/dev/null
  STASH_CREATED=true
fi

restore_stash() {
  if [[ "$STASH_CREATED" == true ]]; then
    local stash_ref
    stash_ref="$(git stash list --format='%gd %s' | awk -v marker="$STASH_MESSAGE" '$0 ~ marker {print $1; exit}')"

    if [[ -n "$stash_ref" ]]; then
      log "Restoring local changes from $stash_ref"
      if git stash apply "$stash_ref"; then
        git stash drop "$stash_ref" >/dev/null
      else
        printf '\n[z-world-sync] Local changes could not be applied cleanly.\n' >&2
        printf '[z-world-sync] Resolve conflicts manually; the stash was preserved as %s.\n' "$stash_ref" >&2
        return 1
      fi
    fi
  fi
}

trap 'restore_stash || true' ERR INT TERM

log "Fast-forwarding $BRANCH from origin/$BRANCH"
if ! git merge --ff-only "origin/$BRANCH"; then
  restore_stash || true
  trap - ERR INT TERM
  fail "Local branch has diverged from origin/$BRANCH. Review with: git log --oneline --graph --decorate --all"
fi

restore_stash
trap - ERR INT TERM

if [[ "$PUSH_AFTER_SYNC" == true ]]; then
  if [[ -n "$(git status --porcelain=v1)" ]]; then
    fail "Working tree contains uncommitted changes. Commit them before using --push."
  fi

  log "Pushing local commits to origin/$BRANCH"
  git push origin "$BRANCH"
fi

printf '\n'
log "Synchronization completed"
git status --short --branch
printf '\nRepository: %s\nDirectory:  %s\nBranch:     %s\n' "$REPO" "$TARGET_DIR" "$BRANCH"
