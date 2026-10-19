# BzzyAnts monorepo: branching and release policy

Status: proposed governance baseline. This repository is not yet proven to contain the consolidated application code.

## Integration and release branches

- `main`: stable, releasable code only. Changes arrive by reviewed pull request from `develop`; no direct pushes.
- `develop`: integration base for reviewed feature and security work. The normal PR sequence is feature -> develop -> main.
- Short-lived work branches start from `develop`, receive review, then are deleted after merge. A branch name is a scope indicator, not an ownership lock; conflicts are prevented by small PRs, shared contracts, and review.
- Emergency fixes use `hotfix/<ticket>-<slug>` from `main`, and must be backported to `develop`.

## Scoped branches created for initial work

| Branch | Intended scope |
| --- | --- |
| `feat/pipeline-core` | Node pipeline: `collect.mjs`, `snapshot.mjs`, `h3.mjs` |
| `feat/adapters-county` | San Bernardino ArcGIS parcel and county land-use adapters |
| `feat/adapters-city` | Eight municipal adapters, with per-city fixtures |
| `feat/python-infer-leads` | Python lead inference, Apify and CA SOS adapters |
| `feat/tauri-offline-outbox` | Rust/Tauri, MapLibre, and offline IndexedDB outbox |
| `sec/media-quarantine` | EXIF scrubber, MantisEye OCR/media quarantine |
| `chore/kiro-governance` | Requirements, design, tasks, and Ants-to-Bees contract reviews |

Future branch names use `feat/`, `fix/`, `sec/`, `chore/`, `docs/`, `test/`, `refactor/`, `perf/`, `ci/`, `build/`, `release/`, or `hotfix/` followed by a lowercase hyphenated scope. Legacy branches are preserved; rename only when their owners coordinate it.

## Review and quality gates

1. Pull requests must target `develop`, except reviewed promotion PRs from `develop` to `main` and carefully documented hotfixes.
2. A single always-reported `monorepo-ci` check validates branch naming and calls domain hooks only for changed files. Python-only work should not run the Node or Tauri test hooks.
3. Any application, schema, or spatial change must pass *real*, non-placeholder Ants-to-Bees schema compatibility and KIRO D-001 spatial validation. These validators and their fixtures must be implemented before such changes merge.
4. Security-critical `sec/` changes must receive an explicit security review, with EXIF and quarantined-content adversarial fixtures. PR template declarations do **not** enforce a reviewer assignment by themselves.
5. Changes to `requirements.md`, `design.md`, `tasks.md`, or `ants-to-bees.schema.json` must describe compatibility/migration impact and be reviewed independently from feature code wherever practical.
6. Never weaken/skip required checks to green-light a PR. Required GitHub rulesets/branch protections must be separately enabled in repository settings.
7. Only merge to `main` when the complete schema, D-001, security, and applicable domain test evidence is present. Use squash merges for most feature branches; document releases in PRs.

## Expected CI hook contract

The workflow invokes these repository-owned executable Bash scripts *if their domain is touched*:

- `.github/ci/check-node.sh`
- `.github/ci/check-python.sh`
- `.github/ci/check-tauri.sh`
- `.github/ci/check-security.sh`

For changes affecting application code or the shared contract, it additionally **requires**:
- `contracts/ants-to-bees.schema.json`
- `.github/ci/check-ants-to-bees.sh`
- `.github/ci/check-kiro-d001.sh`

Missing required hooks cause a red CI result, not a false success. Migrate actual code, lockfiles, tests, fixtures, and D-001 acceptance criteria first. For a docs-only PR, these unavailable application gates are not claimed to have run.

## Required repository settings (administrator action)

For **both** `main` and `develop`: require pull requests, at least one approving review (prefer two for `sec/`), dismiss stale approvals, require successful `monorepo-ci`, prevent force-pushes and deletions, and restrict bypass permissions. Set `main` to accept integration/promotion PRs rather than direct feature commits. Verify protections after configuration. The current GitHub integration cannot modify these settings.

## Scope separation

`BzzyAnts` is the proposed Ants application monorepo. `BzzyBees`, `Bzzy`, `BzzySolutions`, and unrelated game/bot repositories remain untouched until a reviewed migration explicitly changes their scope.
