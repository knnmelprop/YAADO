---
name: Analysis request
about: Request a new engineering analysis, mission run, or model extension
title: "[ANALYSIS] "
labels: analysis-request
---

**What analysis/result do you need?**
Describe the physical question (e.g. "required combustor Tt4 for steady cruise at a different altitude").

**Which vehicle / config?**
Project A (GTM-140 drone) or Project B (ramP), and which `vehicle_config*.yaml`.

**What real data does this need, if any?**
If this touches a currently SZACOWANY/PROVISIONAL/TBD_PHYSICAL_PARAM value
(see `docs/CONVENTIONS.md`), say what real data would resolve it and
whether you already have it (archive file, datasheet, test result) or
it still needs to be sourced.

**Related HR-#/A#/ADR, if any**
Reference the relevant item in `docs/assumptions.md` or
`docs/decision-log.md` if this follows up on something already logged.
