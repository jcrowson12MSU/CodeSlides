#!/usr/bin/env bash
# Rebuild the frontend and stage the compiled static bundle so CSS/JS
# source edits (e.g. frontend/src/fonts.css) actually take effect.
#
# The server serves the committed src/codeslides/static/ bundle, not the
# frontend source -- see README.md "Frontend development". A source-only
# change won't show up until this build step runs and the result is
# committed alongside it.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
frontend_dir="$repo_root/frontend"
static_dir="$repo_root/src/codeslides/static"

if [ ! -d "$frontend_dir" ]; then
  echo "error: frontend directory not found at $frontend_dir" >&2
  exit 1
fi

cd "$frontend_dir"

if [ ! -d node_modules ]; then
  echo "==> Installing frontend dependencies (node_modules missing)"
  npm install
fi

echo "==> Building frontend (tsc -b && vite build)"
npm run build

cd "$repo_root"

echo "==> Staging rebuilt static assets"
git add "$static_dir"

if git diff --cached --quiet -- "$static_dir"; then
  echo "==> No changes in $static_dir after build (nothing to stage)"
else
  echo "==> Staged changes in $static_dir"
  git status --short -- "$static_dir"
fi

echo "==> Done. Review with 'git status' / 'git diff --cached', then commit."
