#!/usr/bin/env bash
#
# Codex PostToolUse hook: after apply_patch (or an Edit/Write tool) touches a
# frontend file, auto-fix it with Biome (formatting, safe lint fixes, import
# organization). Mirrors .claude/hooks/biome-format.sh for the Codex CLI.
#
# Codex's apply_patch payload lists changed files under `changes[].path`
# (repo-relative), unlike Claude's single `tool_input.file_path`. The jq below
# collects any `path`/`file_path` field anywhere in the payload, so it works for
# both shapes. Non-blocking: any problem exits 0 so editing is never interrupted.

set -euo pipefail

command -v jq >/dev/null 2>&1 || exit 0

input=$(cat)

# Every path-like field in the payload (apply_patch changes, or a file_path).
paths=$(printf '%s' "$input" | jq -r '
  [ .. | objects | (.path? // .file_path? // empty) ] | .[]? // empty
' 2>/dev/null | sort -u)
[ -n "$paths" ] || exit 0

# Codex runs hooks with the session cwd; resolve the repo root from git so the
# hook works regardless of which subdirectory Codex was launched from.
root=$(git -C "$PWD" rev-parse --show-toplevel 2>/dev/null || printf '%s' "$PWD")
frontend="$root/frontend"
biome="$frontend/node_modules/.bin/biome"
[ -x "$biome" ] || exit 0

while IFS= read -r p; do
  [ -n "$p" ] || continue
  case "$p" in
    /*) abs="$p" ;;
    *) abs="$root/$p" ;;
  esac
  # Only frontend files Biome handles (CSS is excluded in biome.json).
  case "$abs" in
    "$frontend"/*) ;;
    *) continue ;;
  esac
  case "$abs" in
    *.ts | *.tsx | *.js | *.jsx | *.mjs | *.cjs | *.json | *.jsonc) ;;
    *) continue ;;
  esac
  [ -f "$abs" ] || continue
  # Run from the frontend dir so Biome uses frontend/biome.json as root.
  # --write applies only safe fixes (no behavior-changing rewrites).
  (cd "$frontend" && "$biome" check --write "$abs") >/dev/null 2>&1 || true
done <<<"$paths"
