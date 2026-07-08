# MELprop-IADE — Active Assumptions Register

Every active working assumption, including all [TBD] items from the nightly-run
prompt, with confirmation status. Update whenever an assumption is confirmed,
refuted, or superseded. Companion files: `docs/decision-log.md` (decisions),
`agents/memory.md` (lessons/failure modes).

Status legend: **ACTIVE** (in use, unconfirmed) · **CONFIRMED** · **REFUTED**
· **TBD-HUMAN** (needs a human decision/data — agent must not guess).

| # | Assumption | Status | Notes / evidence |
|---|------------|--------|------------------|
| A1 | Python 3.9 + one pinned SUAVE version for the team environment | TBD-HUMAN | Container runs Python 3.11.15; `.devcontainer/` pins 3.9. Exact SUAVE tag not found in repo env files (2026-07-08). Confirm tag with the team. |
| A2 | WSL2/Ubuntu preferred team environment; Docker/Codespaces deferred | TBD-HUMAN | No evidence in repo either way; needs human confirmation. |
| A3 | Grzywka MATLAB 2D model is the DEFAULT thrust baseline; CFD studies (Dałek, Teltik) show exit velocity/Mach 20–30% higher — open unresolved discrepancy | ACTIVE | Never quote a single thrust/exit number without both values (MATLAB baseline + CFD delta). |
| A4 | Combustor risk baseline: liquid fuel does not vaporize sufficiently before the flame holders; flame-holder cavity temperature ~2400 K exceeds the melting point of the currently specified aluminium | ACTIVE | Every combustor task is blocked-by-design until a redesign (flame-holder relocation and/or injector atomization change) is logged in the decision log. |
| A5 | CAD + signed reports live in OneDrive; code/configs/parametric CSV/decision logs live in Git | TBD-HUMAN | Exact boundary to be confirmed with the team. |
| A6 | No defined Project Lead/reviewer exists; "assign reviewer"/"approve gate" are always human actions | CONFIRMED | Nothing in the repo defines such a role; agent never invents one. |
| A7 | Nightly-run prompt WIP (+528/+159 lines multi-cone inlet) exists in working tree | REFUTED | 2026-07-08: working tree clean (fresh container). Phase 1 executed from scratch. See decision-log entry. |
| A8 | Phase-3 dangling commits b2cc871d/65631dad need rebasing onto origin/develop | REFUTED | 2026-07-08: objects absent; equivalent work already merged via PR #11. Adapted Phase 3 = push designated branch + new draft PR. |
| A9 | 2 and 3 cones cannot meet MIL-E-5007 at Mach 2.5; 4 cones give a thin margin (~0.872–0.874), 5 cones comfortable (~0.888–0.897) | ACTIVE | Given as a confirmed prior result (Seddon & Goldsmith 1999, Sec 4.3 context). To be re-verified numerically in Phase 1 before use; update status after verification. |
| A10 | `nozzle_area_ratio: 4.0` in YAML matches Fusion CAD geometry | REFUTED (pending re-check) | AGENT_CONTEXT.md §7.4: nozzle in Fusion is cylindrical (area ratio 1.0). Phase 4 must log this discrepancy explicitly. |
| A11 | Design cruise: Mach 2.5 @ 10 km ISA, diffuser eta 0.92 (placeholder) | ACTIVE | eta_diffuser=0.92 is an assumed placeholder pending duct-loss/CFD data. |
| A12 | Stage-1 motor data (Isp, propellant mass, burn time), GTM-140 mass/sfc, wing.aspect_ratio, Ixx/Iyy/Izz | TBD-HUMAN | TODO_PHYSICAL_PARAM — never guessed or approximated by agents; require datasheets / Fusion GUI / team decision. |
