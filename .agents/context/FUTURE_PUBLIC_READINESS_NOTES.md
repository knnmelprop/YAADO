# Future Public-Readiness Notes

**This repo stays internal for now.** This is an informational note for a
future session/decision, not a checklist to action today. Nothing here
should be treated as authorization to flip repo visibility or finalize
any license change — both remain explicit human/team decisions.

## License

- Current `LICENSE` is SUAVE's own LGPL-2.1 text, left as-is (a
  deliberate, logged decision — see `docs/ADR/ADR-001-repo-separation.md`
  and `docs/decision-log.md`).
- A target license for MELprop-IADE itself, **PolyForm Noncommercial
  1.0.0**, is recorded in `docs/ADR/ADR-001-repo-separation.md` as
  forward-looking intent only — **not applied**. That ADR is explicit that
  it does not authorize a license change on its own.
- Blocker: `external/suave/` (LGPL-2.1) is a real dependency, vendored as
  a submodule. Before any license swap, someone needs to work out
  whether/how a PolyForm Noncommercial license on MELprop-IADE's own code
  can coexist with an LGPL-2.1 dependency it links against — this is a
  real legal question, not something to resolve by just editing the
  `LICENSE` file.

## Partner / sensitivity review

- A text-content search of this repo (code, markdown, YAML) for
  institutional/partner acronyms someone might expect (e.g. NCBJ, ITWL,
  military/MON-adjacent references) found **no matches** as of this
  writing.
- **Caveat, stated plainly so it isn't lost**: that search only covered
  greppable text. `docs/ramPdocs/` contains a large volume of archived
  Office documents (`.docx`, `.xlsx`, `.dxf`, a `.rar` archive) that were
  **not opened or read for content** during this pass — a real
  sensitivity review before public release would need to actually open
  those, not just grep the repo. Don't treat "no matches found" as "this
  repo has been cleared for sensitive content" — it hasn't.

## GitHub admin / branch protection

- No branch protection is currently configured on `main` (see
  `docs/BRANCHING.md`'s Open Items) — this is a GitHub admin action, not
  something any agent session in this repo can set.
- `.github/CODEOWNERS` still has `@TBD-HUMAN` placeholders throughout —
  real GitHub handles are needed before CODEOWNERS-enforced review could
  mean anything, and enabling that enforcement is itself an admin action.
- Repo visibility (private → public) is a single GitHub admin toggle, but
  should not happen before the license and partner-content questions
  above are actually resolved, not just noted.

## What this note is NOT

Not a timeline, not a checklist with checkboxes to start ticking, not an
implication that public release is imminent or decided. It exists so that
whenever this question does come up for real, whoever picks it up doesn't
have to rediscover these three items from scratch.
