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
# Keep Git's NUL-delimited output intact, and check Git's status before reading.
changed_file="$(mktemp)"
trap 'rm -f "$changed_file"' EXIT
if [[ -z "$base_sha" || "$base_sha" =~ ^0+$ ]]; then
  git ls-tree -r --name-only -z "$head_sha" > "$changed_file" || error "Cannot enumerate source tree."
else
  git cat-file -e "${base_sha}^{commit}" || error "BASE_SHA does not resolve to a commit."
  if [[ "${GH_EVENT:-}" == pull_request ]]; then
    base_sha="$(git merge-base "$base_sha" "$head_sha")" || error "Cannot determine PR merge base."
  fi
  # Include both sides of renames: moving application code into docs must not skip gates.
  git diff --no-renames --name-only -z "$base_sha" "$head_sha" > "$changed_file" || error "Cannot determine changed paths."
fi

[[ -s "$changed_file" ]] || { report "No changed files; branch naming checked."; exit 0; }
report "Changed paths:"

node=false
python=false
tauri=false
security=false
contract=false

while IFS= read -r -d '' path; do
  printf '  %q\n' "$path"
  # Dispatcher regression tests validate CI itself in the required workflow job.
  [[ "$path" == .github/scripts/tests/* ]] && continue
  # Prefixing a slash allows the same segment rules at root and at any depth.
  scoped="/$path"
  matched=false

  # Independent checks deliberately allow frontend or security files to need two suites.
  case "$scoped" in
    */pipeline/*|*.mjs|*.cjs|*.js|*.jsx|*.ts|*.tsx|*.mts|*.cts|*.html|*.css|*.scss|*/package.json|*/package-lock.json|*/npm-shrinkwrap.json|*/pnpm-lock.yaml|*/pnpm-workspace.yaml|*/yarn.lock|*/bun.lock|*/bun.lockb)
      node=true; matched=true ;;
  esac
  case "$scoped" in
    */python/*|*/packages/python-infer-leads/*|/original-spark-infer-leads/*|/monorepo-scaffold/services/*|*.py|*.pyi|*/pyproject.toml|*/requirements*.txt|*/poetry.lock|*/uv.lock|*/Pipfile|*/Pipfile.lock)
      python=true; matched=true ;;
  esac
  # Python adapters are not Node adapters merely because of their directory name.
  case "$scoped" in
    /original-spark-infer-leads/*|/monorepo-scaffold/services/*) ;;
    */adapters/*) node=true; matched=true ;;
  esac
  case "$scoped" in
    */apps/tauri/*|*/field-operator/*|*/src-tauri/*|*.rs|*/Cargo.toml|*/Cargo.lock)
      tauri=true; matched=true ;;
  esac
  case "$scoped" in
    */field-operator/*) node=true ;;
  esac
  case "$scoped" in
    */security/*|*/prober/*|*ssrf*|*scrubber.rs|*quarantine.ts)
      security=true; matched=true ;;
  esac
  case "$scoped" in
    */contracts/*|*ants-to-bees.schema.json|*/kiro/*)
      contract=true; matched=true ;;
  esac
  # New file types under recovered application roots must never silently pass.
  if [[ "$matched" == false ]]; then
    case "$scoped" in
      /monorepo-scaffold/*|/recovered/*)
        node=true; python=true; tauri=true; security=true ;;
    esac
  fi
done < "$changed_file"

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
