# CFD Pipeline — Repo Hygiene & Test Tiering

**Stage 1 of the CFD pipeline scaffolding (2026-07-11).** How mesh/result data is
kept out of git, and how CFD tests are tiered so the heavy jobs never bloat the
fast suite. Reference: `docs/references/ramp_cfd_pipeline_plan_2026-07-11.md` (RQ6).

## Git vs DVC split

**In git:** configs, scripts, pydantic schemas, docs, small synthetic test
fixtures, and **DVC pointer files** (`*.dvc`).

**Never in git (tracked by DVC):** meshes and solver results —
`*.su2 *.cfg *.vtu *.vtk *.cgns *.msh *.cas *.dat *.szplt *.plt` and Fluent
`*.trn`/`*.h5` outputs. These are in `.gitignore`; the real data lives on the
team store and is referenced by `*.dvc` pointers.

### DVC status — hand-scaffolded, tool not installable in the cloud sandbox

`dvc init` could **not** be run here: `dvc` failed to install (its
`antlr4-python3-runtime` build dep is blocked by the sandbox network allowlist).
Rather than fabricate, the files `dvc init` would have produced were **authored
by hand** so no re-init is needed locally:

- `.dvc/config` — core + a default remote `melpropnas` whose `url = TBD-HUMAN`.
- `.dvc/.gitignore`, `.dvcignore` — standard ignore sets.

**TODO(local) — the ONE thing a human must supply:** the real DVC remote target.
Nothing in this repo documents it (the store is referred to informally as
"melpropnas"/"melpropserver" only). Fill `url` in `.dvc/config` with exactly one
of:

- an **SMB share mounted locally** → `url = /mnt/melpropnas/iade-dvc` (local remote), or
- an **S3-compatible endpoint** (e.g. MinIO) → `url = s3://iade-dvc` plus
  `endpointurl` and credentials via `dvc remote modify --local` (secrets stay in
  the git-ignored `.dvc/config.local`, never committed).

Then: `pip install dvc` (with `dvc-s3` if S3), `dvc pull`. No `dvc init` needed.

## Test tiering

Configured in `pytest.ini` (markers + `testpaths = tests`):

| Tier | Marker | When it runs | What it uses |
|---|---|---|---|
| Fast | *(none)* / `fast` | every push (CI), local default | pure unit tests (config gen, schema, math) |
| CFD smoke | `cfd_smoke` | every push (CI) | **fake `SU2_CFD` stub + synthetic toy meshes** — no real solver/mesh |
| CFD nightly | `cfd_nightly` | **manual dispatch only** | real SU2 build + real mesh (self-hosted runner) |

- Default `pytest` runs **fast + cfd_smoke** (`addopts = -m "not cfd_nightly"`).
- `pytest -m cfd_nightly` runs only the production tier (empty until real cases
  exist).
- CI (`.github/workflows/ci.yml`): `fast-and-smoke` job on every push;
  `cfd-nightly` job gated behind `workflow_dispatch` + a self-hosted runner
  (TODO(local): set the runner label and add the SU2-build / `dvc pull` steps).

## Why this shape

CFD solves are far too heavy for the ~240-test fast suite, but pipeline *plumbing*
(config generation, output parsing, GCI math) must be caught on every commit. The
smoke tier exercises that plumbing against stubs/synthetic data cheaply; the
nightly tier is where real solves live, isolated so a slow or failing solve never
blocks ordinary development.
