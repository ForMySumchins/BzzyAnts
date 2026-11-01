# CI routing repair and verification

Inspected PR #3 at `5b2620dabebd71f953a40c63a2173f1902dbc6a4`
and recovered main at `6a7b5ca3acdb3e3f1d8a8e509c8397e88553cfcf`.
The task branch has only governance/CI files and shares the identical README
with main. This repair updates that branch without importing, editing, or
deleting recovered source. Its base remains `develop`.

## Recovered application inventory

| Paths on main | Content / required domain hooks |
| --- | --- |
| `monorepo-scaffold/apps/field-operator/` | HTML frontend; Node + Tauri |
| `recovered/field-operator/src/components/geoint/`, `src/lib/observations/` | TS/TSX components, storage, hooks and tests; Node + Tauri |
| `recovered/legacy-poway/pipeline/` | MJS h3, normalization and publishing; Node |
| `monorepo-scaffold/services/ants_api/` | Python API and routes; Python |
| `monorepo-scaffold/services/ingestor_core/adapters/` | Python adapter; Python |
| `monorepo-scaffold/services/ingestor_core/prober/` | Python SSRF probe; Python + security |
| `monorepo-scaffold/packages/contracts/` | Python models and initialization; Python + shared contract |
| `monorepo-scaffold/tests/` | Python acceptance tests; Python |
| `original-spark-infer-leads/src/lead_intelligence/` | Python models, adapters, export, identity and inference; Python |
| `original-spark-infer-leads/src/lead_intelligence/security/` | Python SSRF checks; Python + security |
| `original-spark-infer-leads/tests/` | Python tests; Python |
| `monorepo-scaffold/package.json`, `pnpm-workspace.yaml` | Node workspace configuration; Node |
| Both recovered `pyproject.toml` files | Python configuration; Python |

The inventory includes empty Python `__init__.py` files. README files and
`EXPORT_MANIFEST.json` describe recovery/provenance; they are not executable
application code. No Rust/Cargo application exists in this main snapshot.

Rules also cover root and nested legacy pipeline, adapter, Python, Tauri,
security, contracts and KIRO directories. JS/JSX/MJS/CJS/TS/TSX/MTS/CTS,
HTML/CSS/SCSS, PY/PYI and RS files and nested ecosystem manifests/lockfiles
route regardless of depth. Unknown file types inside `monorepo-scaffold/`
or `recovered/` conservatively require every domain. The original Python
project routes all its paths to Python. Domain selection is additive.

Any application or contract selection still requires the real root
`contracts/ants-to-bees.schema.json`, `check-ants-to-bees.sh`, and
`check-kiro-d001.sh`, followed by applicable domain hooks. None are supplied
as placeholders by this repair. Missing or failing checks remain fatal.

PRs compare the merge base to the head; pushes compare before to head;
initial pushes scan the whole tree. Git failures are fatal. NUL-delimited
paths preserve spaces, quotes and newlines; disabling rename detection
keeps deletions of source visible even when renamed into documentation.
Branch policy still runs for empty diffs. Dispatcher tests under
`.github/scripts/tests/` validate CI infrastructure as the first validation step
in the required `monorepo-ci` job. A test failure fails that same required job.
They do not invoke application hooks for their own test code.

## Actual local verification (2026-11-01)

- Before repair: 8 unittest methods, 23 failing assertions/subtests against
  the old dispatcher. Failures included HTML, nested manifests, renamed
  source and unusual filenames.
- After repair: `python -m unittest discover -s .github/scripts/tests -v`
  passes all 10 methods (routing table, branch policy, missing/failing gates,
  invalid revisions, initial push, deletion, rename, mixed domains, unusual
  filenames and divergent PR base).
- `bash -n .github/scripts/monorepo-ci.sh` and `git diff --check`: pass.
- Against unmodified recovered main source:
  `PYTHONPATH=original-spark-infer-leads/src python -m unittest discover -s original-spark-infer-leads/tests -v`:
  12 passed.
- `PYTHONPATH=monorepo-scaffold python -m unittest discover -s monorepo-scaffold/tests -v`:
  11 passed; existing Pydantic/datetime.utcnow deprecation warning.
- `node --experimental-strip-types recovered/field-operator/src/lib/observations/storage.test.ts`:
  11 passed, one suite (Node 24.19.0).

The temporary Git repositories in dispatcher tests contain invocation-recording
hooks and an empty schema fixture. These are isolated test doubles, never
production validators or evidence of application integration acceptance.
No dependencies were installed or paid services used.

## Remaining blockers

`develop` remains README-only and must be reconciled with recovered main
before promotion. Real Ants-to-Bees schema/compatibility validation,
KIRO D-001 fixtures/validation and domain hooks are absent. Existing recovered
acceptance tests are not substitutes for those gates. A source-changing run
must remain red until real validators exist. Branch protections need separate
administrator verification. No merge or deployment is authorized.

Historical Actions run `39276705257` failed; its job logs return 404
BlobNotFound, so that run's cause remains unverified. New Actions results are
reported in PR #3 after publication; local test success is not an Actions result.
