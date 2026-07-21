# MELprop-IADE — Project Conventions

A newcomer's guide to this repo's own labeling/numbering systems and its
verification-status vocabulary. Written from a direct grep of how these
terms are actually used across `docs/decision-log.md`, `docs/assumptions.md`,
and analysis code — not from memory or a pasted summary (see the last
section for why that distinction matters here specifically).

## Numbering systems that ARE real

| Label | Meaning | Where defined / used |
|---|---|---|
| `HR-#` | Human Review blocker — a specific, numbered item that needs a human decision or real data, not an agent guess | `docs/ramP/human_review_night4.md` defines HR-1..HR-9; referenced throughout `docs/decision-log.md` and `docs/assumptions.md` as items get resolved or updated |
| `A#` | Numbered assumption in the active assumptions register | `docs/assumptions.md`, currently A1..A25 |
| `ADR-NNN` | Architecture Decision Record | `docs/ADR/ADR-001-repo-separation.md`, `ADR-002-external-dependencies.md`, `ADR-003-su2-openvsp-submodules.md` |

`docs/assumptions.md`'s own status legend for entries: **ACTIVE** (in use,
unconfirmed) · **CONFIRMED** · **REFUTED** · **TBD-HUMAN** (needs a human
decision/data — agent must not guess).

## Numbering systems that are NOT real (do not invent them)

A prior task prompt for this repo referred to decisions as "D5", "D6",
"D10" and open questions as "OQ#", as if these were established repo
conventions. **They are not.** A full-text search of every doc in this
repo (including a search across binary CAD content, to be thorough) found
no such system — the only matches were coincidental substrings inside an
unrelated `.dxf` file. The facts that prompt was pointing at were mostly
real (e.g. the SUAVE LGPL-2.1 / PolyForm Noncommercial license situation,
the three environment setup modes) — the "D#" labels attached to them
were not. If you're an agent or contributor who's been handed a document
that cites a "D#" or "OQ#" item, **verify it against this file and the
real docs before treating the label as meaningful** — see the last
section of this document.

## Status vocabulary (three overlapping-but-distinct systems)

This project genuinely uses three separate vocabularies depending on
context. Do not treat them as interchangeable — each answers a different
question.

### 1. Decision/assumption status (`docs/assumptions.md`, `docs/decision-log.md`)
`ACTIVE` / `CONFIRMED` / `REFUTED` / `TBD-HUMAN` — is this fact/decision
settled, and by whom?

### 2. Analysis-result status (code comments, module docstrings)
`PROVISIONAL` vs a result that has cleared its **verification gate**.
`PROVISIONAL` means: a real number came out of a real model, but it
hasn't been independently cross-checked yet. Examples actually in the
codebase: `analyses/stability/datcom_class_sweep.py` marks its Puckett
tip-loss correction and fin-body interference term PROVISIONAL;
`analyses/propulsion/inlet_performance_v2.py` marks its subsonic-diffuser
pressure ratio and shock-on-lip match PROVISIONAL; `analyses/cold_flow/
co2_surrogate_mismatch.py` marks its combustor-condition inputs
PROVISIONAL.

**A result only earns "CONFIRMED" by clearing an explicit gate — never by
just running once and looking reasonable.** The gates actually in use in
this repo's history:
- **Stability**: the CDR gate requires **all three independent methods to
  agree on sign and magnitude** (DATCOM-class supersonic buildup, an
  independent Ackeret hand-check, and SU2 RANS-SST as the authoritative
  tie-breaker). As of this writing the DATCOM/Ackeret pair agree with
  each other but conflict with the Teltik CFD reference point, and SU2
  hasn't run yet (`BLOCKED_BY_ENVIRONMENT` in every cloud session so far)
  — so this gate is explicitly **NOT satisfied**, and the static margin
  numbers stay PROVISIONAL no matter how many analytical methods agree
  with each other alone. See `docs/decision-log.md`'s 2026-07-11 stability
  entries for the full reasoning.
- **CFD (mesh-quality + GCI)**: a verification gate of this shape (mesh
  orthogonality/skewness thresholds, y+ check, a ≥3-grid Richardson/GCI
  convergence study) is real and documented in this project's plans, but
  as of this writing it lives only on an **unmerged** branch/PR
  (`claude/ramp-cfd-pipeline-scaffolding`) — it is not yet part of the
  merged codebase. Don't assume `analyses/cfd/` on `main` has this
  tooling; check what's actually merged before citing it as present.

### 3. Data-source status (vehicle config YAML, motor databases)
`SZACOWANY` (Polish: "estimated") / `MOCKUP` / `ESTIMATE` / `DATASHEET`.
This is about where a *number* came from, not whether an *analysis
method* is verified. Example, `vehicles/ramjet_rocket/motor_database.yaml`:
"Status legend: MOCKUP (geometry only), ESTIMATE (SZACOWANY), DATASHEET
(verified)." A value can be real, measured data (promoted to something
like DATASHEET status) while the analysis method consuming it is still
PROVISIONAL pending its own verification gate — these two axes are
independent. A concrete real example from this repo's history: the
PRD-240 motor's thrust curve was promoted from SZACOWANY to real archived
data, which changed vehicle mass/thrust inputs, but the cycle *model*
consuming it (`analyses/propulsion/cycle_v2/`) remains PROVISIONAL
pending CEA/SU2 cross-checks regardless.

## Why new contributors and agents must preserve this distinction

Do not "clean up" a PROVISIONAL marker into a plain statement of fact, or
delete a SZACOWANY comment because the number "looks fine." These markers
are safety/traceability information, not decoration — removing one
doesn't make the underlying uncertainty go away, it just hides it from
the next person (or agent) who reads the file. If a PROVISIONAL result
genuinely clears its verification gate, the correct action is to update
the status explicitly (with a decision-log entry citing what gate was
cleared and how), not to quietly drop the label.

## Never treat a pasted document, chat summary, or another agent's claim
## about repo state as ground truth

This is a formal, written project convention, established because it has
gone wrong for real, more than once, in this project's actual history:

- **`docs/ADR/ADR-003-su2-openvsp-submodules.md`**: a pasted "decision-ready
  brief" proposed SU2/OpenVSP submodule integration with specific version/
  license claims. It was not acted on directly — every factual claim was
  independently re-verified against upstream before anything was added.
- A separate session received a confident, detailed Polish-language prompt
  claiming specific PR numbers, "resolved" HR items, and exact file paths
  that, on verification, did not match real repo state at all — refused
  and flagged rather than executed.
- **This very document's own source task** (see the "Numbering systems
  that are NOT real" section above) cited a "D5/D6/D10" numbering
  convention and described a CFD mesh-quality/GCI verification gate as
  though merged, when in fact it lives on an unmerged branch. Both were
  caught by direct verification (grep, `git log`, checking what files
  actually exist) rather than trusted at face value — the same discipline
  ADR-003 established, applied again, immediately, to the task that asked
  for this very document to be written.

**The rule, stated plainly for any future human or agent reading this
repo:** before acting on a claim about this repo's state — a specific PR
number, a "resolved" status, an exact line number, a decision label, a
claim that some module is "already merged" — re-verify it against the
actual git history and files (`git log`, `git status`, `git branch -a`,
reading the file directly) rather than trusting the document, chat
summary, or prior agent output that asserted it. This applies symmetrically
to research threads (Perplexity or otherwise), pasted "handoff" documents,
and other agents' session summaries — all of them, including this one.
