---
name: Bug report
about: Something in the code/analysis pipeline is broken or gives a wrong result
title: "[BUG] "
labels: bug
---

**What's broken**
A clear description of the incorrect behavior.

**Where**
File/module (e.g. `analyses/propulsion/cycle_v2/hp_stream_thrust_cycle.py`) and, if applicable, which test or script.

**Steps to reproduce**
```bash
python -m pytest tests/unit/test_XXX.py -v
# or: python analyses/.../script.py
```

**Expected vs. actual**
What you expected, what actually happened (paste the error/output).

**Environment**
Which setup mode (devcontainer / native venv / conda — see `CONTRIBUTING.md`), Python version.

**Does this touch a PROVISIONAL/CONFIRMED/SZACOWANY marker?**
If this bug report involves a value or result carrying one of these
status markers, say so explicitly — see `docs/CONVENTIONS.md`. Do not
propose silently removing the marker as the fix.
