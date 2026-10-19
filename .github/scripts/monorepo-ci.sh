#!/usr/bin/env bash
# Fail-closed, path-aware CI dispatcher. No hook is permitted to silently pass.
set -Eeuo pipefail

error() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
report() { printf '%s\n' "$*"; }

if [[ "${GH_EVENT:-}" == "pull_request" ]]; then
  if [[ "${PR_BASE:-}" == "main" ]]; then
    # Integration promotion and documented emergency fixes are the only routes to main.
    [[ "${PR_HEAD:-}" == "develop" || "${PR_HEAD:-}" =~ ^hotfix/[a-z0-9][a-z0-9._-]*$ ]] ||
      error "PRs into main must come from develop or a hotfix/* branch."
  elif [[ "${PR_BASE:-}" == "develop" ]]; then
    [[ "${PR_HEAD:-}" =~ ^(feat|fix|sec|chore|docs|test|refactor|perf|ci|build|release|hotfix)/[a-z0-9][a-z0-9._-]*$ ]] ||
      error "PR branch '${PR_HEAD:-}' must use a supported domain/type prefix and lowercase slug."
  else
    error "PR base '${PR_BASE:-}' must be develop or main."
  fi
fi

head_sha="${HEAD_SHA:-HEAD}"
base_sha="${BASE_SHA:-}"
git cat-file -e "${head_sha}^{commit}" || error "HEAD_SHA does not resolve to a commit."
if [[ -z "$base_sha" || "$base_sha" =~ ^0+$ ]]; then
  changed="$(git ls-tree -r --name-only "$head_sha")"
else
  git cat-file -e "${base_sha}^{commit}" || error "BASE_SHA does not resolve to a commit."
  changed="$(git diff --name-only "$base_sha" "$head_sha")" || error "Cannot determine changed paths."
fi

[[ -n "$changed" ]] || { report "No changed files; branch naming checked."; exit 0; }
report "Changed paths:"
printf '%s\n' "$changed"

node=false
python=false
tauri=false
security=false
contract=false

while IFS= read -r path; do
  [[ -n "$path" ]] || continue

  # Independent checks allow one change to require multiple suites.
  if [[ "$path" == pipeline/* || "$path" == adapters/* || "$path" == packages/pipeline/* || "$path" == packages/adapters/* || "$path" == *.mjs || "$path" == *.cjs || "$path" == *.js || "$path" == *.ts || "$path" == *.tsx || "$path" == package.json || "$path" == package-lock.json ]]; then
    node=true
  fi
  if [[ "$path" == python/* || "$path" == packages/python/* || "$path" == packages/python-infer-leads/* || "$path" == *.py || "$path" == pyproject.toml || "$path" == requirements.txt || "$path" == poetry.lock ]]; then
    python=true
  fi
  if [[ "$path" == apps/tauri/* || "$path" == apps/field-operator/* || "$path" == src-tauri/* || "$path" == *.rs || "$path" == Cargo.toml || "$path" == Cargo.lock ]]; then
    tauri=true
  fi
  if [[ "$path" == security/* || "$path" == packages/security/* || "$path" == *scrubber.rs || "$path" == *quarantine.ts ]]; then
    security=true
  fi
  if [[ "$path" == contracts/* || "$path" == *ants-to-bees.schema.json || "$path" == kiro/* ]]; then
    contract=true
  fi
done <<< "$changed"

run_hook() {
  local name="$1"
  local path=".github/ci/check-$name.sh"
  [[ -f "$path" ]] || error "Required test hook '$path' is missing. Add a real test before merging this domain."
  report "Running $path"
  bash "$path" || error "$path failed"
}

if [[ "$node" == true || "$python" == true || "$tauri" == true || "$security" == true || "$contract" == true ]]; then
  [[ -f contracts/ants-to-bees.schema.json ]] ||
    error "contracts/ants-to-bees.schema.json is missing; application integration is not yet validated."
  run_hook ants-to-bees
  run_hook kiro-d001
fi

[[ "$node" == true ]] && run_hook node
[[ "$python" == true ]] && run_hook python
[[ "$tauri" == true ]] && run_hook tauri
[[ "$security" == true ]] && run_hook security

report "Monorepo CI finished. Unchanged domain suites were skipped."
