# MELprop-IADE — Agent Memory

Lessons learned, recurring failure modes, and subagent task outcomes.
Append-only; maintained by the orchestrator.

---

## 2026-07-08 — Nightly run (RamP-Fable)

### Lessons carried in from prior sessions (from run prompt / AGENT_CONTEXT.md)
- Never commit subagent work while the test suite is red (prior incident).
- Never hard-reset onto origin/develop when local commits hold real work.
- `docs/ramP/preliminary_analysis_report.md` is STALE — cite
  `docs/ramP/analysis_status.md` instead.
- Single-cone inlet failing MIL-E-5007 at M2.5 is physics, not a bug; do not
  fake inlet physics to make tests pass with too few cones.

### This-run observations
- Fresh-container drift: handoff docs and run prompts can describe WIP/commits
  that do not exist in the current clone. Always run STEP-0 verification
  (`git status`, `git cat-file -t <sha>`, pytest baseline) before acting on a
  described state; log divergences in docs/decision-log.md before Phase 1.
- Test counts in handoff docs go stale quickly (prompt said 62/66, AGENT_CONTEXT
  said 25, actual 36). Trust only a freshly run pytest.

### Nightly-run lessons (2026-07-08/09)
- **Subagent artifact recovery:** Subagent runs killed by user interrupts leave
  no artifacts — always verify expected output files exist before assuming a
  launched agent completed. Git status + pytest count are the ground truth.
- **Sonnet delegation model:** Delegating physics phases (inlet, cycle, mission)
  to sonnet-tier with tightly specified spec + orchestrator-side pytest
  verification worked reliably (75/75, 80/80 first pass). Document physics
  intent clearly; let subagents implement numerics.
- **Doc phase batching:** Combine small doc phases (e.g., tracker update +
  assumptions confirmation + memory log) into one subagent call to save
  cold-start overhead. Markdown files have low parsing cost; parallel edits
  safe if non-overlapping.

### Night-2 lessons (2026-07-09)

- **Stopping early beats stopping mid-write:** the budget guard stop worked
  cleanly this run because the opus agent (Phase 2b) was still in read-only
  exploration when it fired — no partial files, no dangling state to clean
  up. Whenever possible, prefer checking budget headroom *before* a subagent
  starts writing rather than mid-write.
- **blocked_by_budget vs merytoryczne blocked must be distinguished in
  trackers.** A resource-exhaustion stop (resume as-is next session, no
  re-diagnosis) is a fundamentally different signal than a physics/data
  blocker (needs human input or design decision). Conflating the two in
  `analysis_status.md` would cause the next session to waste time
  re-diagnosing a phase that was simply cut short.

## Night-3 STEP-0 (2026-07-09)
- Baseline: 80/80 green (after installing missing runtime deps in fresh
  container: `pytest`, `pydantic`, `pyyaml`, `scipy`, `numpy` — none were
  preinstalled; `analyses/propulsion/inlet_performance.py` imports
  `scipy.optimize`, so scipy is a hard runtime dep despite not being listed
  in CLAUDE.md's "dev deps" note).
- Blocked phases to resume: 2b (combustor_nozzle_cycle.py), 3b (staged
  mission cruise wiring), 4b (movable inlet actuation).
- Active assumptions: A1-A16 tracked in docs/assumptions.md.
- Known urgent items: fin span sign flip (SM +8.99 cal Barrowman vs
  -2.75 cal Teltik CFD at Ma 2.5 — HUMAN_REVIEW, do not resolve
  unilaterally), Grzywka combustor/nozzle model (2b), actuator params (4b).
- Working branch for this session: `claude/dazzling-turing-d91coa` (harness
  -assigned; did not create a separate night3-suffix branch per harness
  branch policy).
- **A checkpoint is a tracker section with the full resume spec, not just a
  status flag.** "BLOCKED_BY_BUDGET" alone tells the next session nothing
  about what to do; the checkpoint must carry the complete task spec (files
  to create, model equations, coefficients, fidelity requirements, tier
  requirement) so the next session can resume Phase 2b directly instead of
  re-deriving it from the original run prompt.

## Night-4 STEP-0 (2026-07-09)
- Pytest baseline: 118 passed, 0 failed (up from 80 at Night-2 start; Night-3
  delivered phases 2b/3b/4b/5/6).
- Working branch: `claude/fervent-albattani-f18spc` (harness-assigned), clean
  tree, at merge tip of PR #13.
- PRs merged since Night-3: PR #13 (combustor_nozzle_cycle Grzywka model,
  staged-mission cruise wiring, movable-spike inlet actuation, stability
  reconciliation, SU2 config generator) and PR #14 (backlog wave 1: dead-link
  audit + test docstrings).
- Stale tracker note: `docs/ramP/analysis_status.md` rows 16–18 still say
  BLOCKED_BY_BUDGET although PR #13 merged that work — refresh scheduled in
  Night-4 KROK 8.
- BLOCKED_BY_HUMAN_REVIEW items: HR-1 fin span 0.6685 m vs Fusion v6
  (3.4–4.8x reduction), HR-2 Teltik CFD geometry version, HR-3 nozzle
  area_ratio 4.0 vs CAD 1.0, HR-4 stage-1 motor datasheet (R-13), HR-5
  Ixx/Iyy/Izz from Fusion GUI, HR-6 max_rpm units decision, HR-7 V3=1474 m/s
  vs ~1047 m/s (+40.8% delta).
- Active assumptions: A1–A16 in `docs/assumptions.md` (A18–A20 planned).
- Night-4 plan: P1-A Barrowman extended sensitivity (sonnet), P1-B V3
  root-cause (opus), P1-C operational envelope (sonnet), P1-D persistent agent
  definitions (haiku), then P2-A/B/C/D.

## Night-4 close-out (2026-07-09)
- All 8 blocks (P1-A/B/C/D, P2-A/B/C/D) + backlog BB1/BB2/BB4/BB5 done; no
  budget stop. Tests 118 → 157 green; every commit gated on a green suite.
- BB1 resolved by P2-A: bare `import SUAVE` succeeds via an empty
  namespace-package stub at repo root (SUAVE/version.py, no __init__.py)
  shadowing trunk/SUAVE — availability probes must deep-import a concrete
  submodule (see analyses/suave/ramp_suave_baseline.py _probe_suave_available).
- Repo convention discovered: *.png is gitignored repo-wide (.gitignore:73);
  plots are regenerable from scripts, only CSV/JSON results are committed.
- Run-prompt path drift: prompt said vehicle/ (actual vehicles/) and
  results/combustor_nozzle_results.json (actual
  analyses/propulsion/combustor_nozzle_cycle_results.json) — STEP-0
  verification caught both before delegation.

---

## 2026-07-09/10 — IADE repo-separation (Phases 1–5, `knnmelprop/droneEnv`
## → `knnmelprop/iade`)

- **New repo, same history depth, much smaller.** `git filter-repo` with
  an explicit owned-path allowlist took `droneEnv` from 793 commits /
  124 MB `.git` to 182 commits / 912 KB in the extracted `iade` history.
  Ran as a dry run against a disposable clone first, validated (pytest,
  path presence/absence, size/commit sanity), only then pushed — never
  ran filter-repo against the working repo or the backup mirror.
- **The owned/removed path lists given up front were incomplete — flag
  gaps, don't guess.** `student_competition/` (MELprop's own Droniada
  work) and `conftest.py` (makes `tests/` importable at all) weren't on
  the literal "owned paths" list but had to be added — dropping either
  would have destroyed real work or broken every test. `ide/`,
  `templates/`, `regression/` (311 MB), `appveyor.yml` weren't on the
  literal "removed" list either but were unambiguously upstream SUAVE
  baggage. Cross-referencing the actual repo tree against both lists
  caught this before running anything.
- **A path-consolidation (`doc/` → `docs/`) touches far more than the
  moved directory.** 18 external files referenced `doc/...` paths; fixing
  the move without grepping for cross-references would have left dead
  links. Also found internal cross-references *inside* the moved files
  themselves (e.g. `docs/ramP/stability_reconciliation.md` linking to
  sibling `doc/ramP/...` files) that weren't caught by a naive "files
  outside doc/ that reference doc/" search — worth grepping the moved
  tree's own content too, not just external references.
- **Submodule pins must be verified against real upstream tags, not
  taken on trust.** SUAVE's pin (tag `2.5.2`) and pyCycle's (tag `4.1.2`)
  were both confirmed via `git ls-remote --tags` against the actual
  upstream repos before writing them into ADR-002 — SUAVE's match was by
  version-string (matching `trunk/setup.py`'s `version = '2.5.2'`), not a
  full tree diff, and that caveat is recorded rather than glossed over.
- **A submodule's installable path isn't always the submodule root.**
  `suavecode/SUAVE` itself has its own internal `trunk/` layout (repo
  root → `trunk/setup.py` → `trunk/SUAVE/`), so the real path after
  `git submodule add ... external/suave` is `external/suave/trunk/`, not
  `external/suave/`. Got this wrong on the first pass (devcontainer,
  docs, `core/vehicle_factory.py` error message all said
  `external/suave`) — caught by actually `ls`-ing the submodule after
  adding it, not by assuming the layout. Fix before trusting any doc that
  says just `external/suave` for SUAVE's Python package path.
- **A repo-wide migration breaks operational docs, not just data paths.**
  `.devcontainer/devcontainer.json`'s `postCreateCommand` still did
  `cd trunk; python3.9 setup.py develop` after `trunk/` was removed from
  history — would have failed on next container build. `CLAUDE.md` and
  every `.claude/agents/*.md` still said "Never modify `trunk/SUAVE/`".
  These aren't data — they're instructions a future agent session reads
  and follows, so stale paths there are a live correctness bug, not
  cosmetic. Caught by an explicit grep-for-`trunk` pass in Phase 5, not
  by chance.
- **Untrusted content can arrive mid-task looking authoritative.** A
  pasted "decision-ready brief" mid-session proposed integrating
  SU2/OpenVSP immediately with specific version pins, directly
  contradicting an already-locked human decision to defer all four
  remaining external tools. Treated its claims as unverified rather than
  acting on them — the project's "never guess a pinned ref" rule applies
  just as much to refs arriving pre-packaged in confident-looking prose
  as to ones an agent would invent itself. Flagged to the human rather
  than silently executed or silently dropped. Similarly, a duplicate/
  stale replay of an already-completed Step B instruction arrived later
  — recognized via HEAD SHA / phase-state mismatch, not re-executed.
- **Auto-mode permission gates caught real scope creep twice**: adding a
  remote to a disposable clone before human confirmation, and repointing
  that remote to a different transport (local proxy → direct HTTPS)
  without a fresh confirmation for the new channel. Both were legitimate
  catches, not friction to route around — stopped and asked both times
  rather than finding a workaround.
- Every risky/irreversible action (filter-repo execution, the actual push
  to `knnmelprop/iade`, adding external submodules) got its own explicit
  confirmation, separate from general "continue" — a broad go-ahead
  covers sequencing, not each individually-flagged risky step.
