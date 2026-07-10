#!/usr/bin/env bash
# MELprop-IADE | scripts/bootstrap_submodules.sh | v0.1.0
#
# Initializes and pins external/ submodules (SUAVE, pyCycle). Safe to
# re-run. Does NOT install Python packages — see docs/environment-native.md,
# environment-conda.yml, or .devcontainer/ for that.
#
# Verified 2026-07-10: `git submodule update --init --recursive` was run
# as part of adding these submodules in this session and both landed at
# their pinned commits correctly. The idempotent re-run behavior below
# (running this script a second time) was NOT separately re-tested.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "MELprop-IADE: initializing submodules..."
git submodule update --init --recursive

EXPECTED_SUAVE="6554d2b3d1e7c2f1d4ba572aec99e1fd69d34a93"
EXPECTED_PYCYCLE="5a6fe40059211312f4b6d86d1a2bb1d913073ce8"

actual_suave="$(git -C external/suave rev-parse HEAD)"
actual_pycycle="$(git -C external/pycycle rev-parse HEAD)"

status=0
if [ "$actual_suave" != "$EXPECTED_SUAVE" ]; then
  echo "WARNING: external/suave is at $actual_suave, expected $EXPECTED_SUAVE (tag 2.5.2). See docs/EXTERNAL_TOOLS.md." >&2
  status=1
fi
if [ "$actual_pycycle" != "$EXPECTED_PYCYCLE" ]; then
  echo "WARNING: external/pycycle is at $actual_pycycle, expected $EXPECTED_PYCYCLE (tag 4.1.2). See docs/EXTERNAL_TOOLS.md." >&2
  status=1
fi

if [ "$status" -eq 0 ]; then
  echo "Submodules OK: external/suave @ 2.5.2, external/pycycle @ 4.1.2"
else
  echo "One or more submodules are NOT at their pinned ref — do not proceed without human review." >&2
fi

exit "$status"
