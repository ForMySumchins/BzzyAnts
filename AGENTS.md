# Agent Instructions — BzzyAnts

These instructions apply to this repository when present on the task's checked-out branch. They do not imply any missing source code has been recovered.

## Verified project state
Observed 2026-10-26: main and develop are README-only; chore/kiro-governance has CI/governance files, but no verified React site or monorepo application. Existing HTML prototype and complete A02 cinematic asset suite are in Google Drive, not committed website source. Employment-first Ant recruitment and sales enablement are the product identity; geospatial inference is supporting infrastructure. Do not assert a functioning React app or deployed site without repository and build evidence. See docs/WEBSITE_SOURCE_HANDOFF.md on this recovery branch.

## Mandatory source-first workflow
1. Inventory the actual checkout: `git status --short`, `git branch -avv`, `git log -5 --oneline`, root directories, existing `AGENTS.md`, and CI. Do not assume an earlier chat or a branch label guarantees files exist.
2. Look for previously completed work in accessible branches, PRs, attached source archives, and explicitly authorized cloud/local workspaces. Treat inaccessible sources as **unverified** and report the precise blocker. Preserve existing files and history.
3. Before implementing a feature, identify its exact target paths, scope, tests, secrets risks, and acceptance criteria. Work on a task-specific feature branch; never work directly on protected/stable branches.
4. If implementation is authorized, **actually write the code and assets**, run appropriate feasible checks, and commit the result to the feature branch. Don't stop at a textual plan, chat-only snippets, or a patch kit presented as committed work.
5. When pushing is available and authorized, push the branch and open a reviewable PR. Provide branch, commit SHA, changed paths, checks with pass/fail evidence, and actual PR or artifact link. Do not claim a successful push, PR, deployment, or build without verifying it.
6. When credentials or the workspace prevent a push, explicitly mark the status **UNCOMMITTED / NOT IN GITHUB**, give the local branch or artifact path, and describe the exact action needed to transfer it. Never silently call that work complete.

## Boundaries
- No secret files, live credentials, private client/applicant data, or unapproved generated bulk assets in Git.
- No destructive source replacement, speculative migration, paid provider usage, customer contact, or deployment without explicit task authorization.
- Separate `planned`, `local only`, `committed`, `PR open`, `merged`, and `deployed` states.
- Read project-specific rules when present. Preserve existing tests and behavior unless requested changes require them.
- Use Git LFS or documented external storage for suitable large approved assets; do not embed raw videos directly without repo policy.

## Required final handoff
```text
REPO:
SOURCE_BRANCH:
WORKTREE_PATH:
STATUS: PLANNED | LOCAL_ONLY | COMMITTED | PR_OPEN | MERGED | DEPLOYED | BLOCKED
COMMIT_SHA: (or NONE)
PR_URL: (or NONE)
CHANGED_PATHS:
BUILD_AND_TEST_RESULTS:
ASSET_PROVENANCE:
REMAINING_BLOCKERS:
```

This guidance establishes truthful delivery discipline. It is not a substitute for locating and committing missing code.
