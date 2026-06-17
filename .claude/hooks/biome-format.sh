#!/usr/bin/env bash
#
# PostToolUse hook: after an AI edits a frontend file, auto-fix it with Biome
# (formatting, safe lint fixes, import organization). Keeps the working tree in
# the state CI expects, so `npm run ci` stays green.
#
# Non-blocking: any problem here exits 0 so editing is never interrupted.

set -euo pipefail

# jq is required to read the tool payload; skip silently if unavailable.
command -v jq >/dev/null 2>&1 || exit 0

input=$(cat)
file=$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty')
[ -n "$file" ] || exit 0

# Only touch files inside the frontend that Biome handles (CSS is excluded in
# biome.json because Biome can't parse Tailwind v4 directives).
case "$file" in
  */frontend/*) ;;
  *) exit 0 ;;
esac
case "$file" in
  *.ts | *.tsx | *.js | *.jsx | *.mjs | *.cjs | *.json | *.jsonc) ;;
  *) exit 0 ;;
esac
[ -f "$file" ] || exit 0

frontend="${CLAUDE_PROJECT_DIR:-.}/frontend"
biome="$frontend/node_modules/.bin/biome"
[ -x "$biome" ] || exit 0

# Run from the frontend dir so Biome treats frontend/biome.json as the root
# config. --write applies only safe fixes (no behavior-changing rewrites).
(cd "$frontend" && "$biome" check --write "$file") >/dev/null 2>&1 || true
