#!/usr/bin/env bash
# MELprop-IADE | external/bootstrap_submodules.sh | v0.1.0
#
# Initializes and pins external/ submodules (SUAVE, pyCycle, SU2,
# OpenVSP). Safe to re-run. Does NOT install Python packages or build
# anything — see docs/environment-native.md, environment-conda.yml, or
# .devcontainer/ for that.
#
# Verified 2026-07-10: `git submodule update --init --recursive` was run
# as part of adding these submodules in this session and all four landed
# at their pinned commits correctly. The idempotent re-run behavior below
# (running this script a second time) was NOT separately re-tested.
#
# external/su2 (257 MB recursive) and external/openvsp (412 MB) checked out add real
# weight to a full recursive clone — see docs/EXTERNAL_TOOLS.md.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "MELprop-IADE: initializing submodules..."
git submodule update --init --recursive

EXPECTED_SUAVE="6554d2b3d1e7c2f1d4ba572aec99e1fd69d34a93"
EXPECTED_PYCYCLE="5a6fe40059211312f4b6d86d1a2bb1d913073ce8"
EXPECTED_SU2="12eb826f049ef7f67df974dfcb44cf36ee07c0f8"
EXPECTED_OPENVSP="458d26ad88cf0167dcb3d7c70846e771cbf0e841"

actual_suave="$(git -C external/suave rev-parse HEAD)"
actual_pycycle="$(git -C external/pycycle rev-parse HEAD)"
actual_su2="$(git -C external/su2 rev-parse HEAD)"
actual_openvsp="$(git -C external/openvsp rev-parse HEAD)"

status=0
check() {
  local name="$1" actual="$2" expected="$3" ref_label="$4"
  if [ "$actual" != "$expected" ]; then
    echo "WARNING: external/$name is at $actual, expected $expected ($ref_label). See docs/EXTERNAL_TOOLS.md." >&2
    status=1
  fi
}
check suave "$actual_suave" "$EXPECTED_SUAVE" "tag 2.5.2"
check pycycle "$actual_pycycle" "$EXPECTED_PYCYCLE" "tag 4.1.2"
check su2 "$actual_su2" "$EXPECTED_SU2" "tag v8.5.0"
check openvsp "$actual_openvsp" "$EXPECTED_OPENVSP" "tag OpenVSP_3.51.0"

if [ "$status" -eq 0 ]; then
  echo "Submodules OK: external/suave @ 2.5.2, external/pycycle @ 4.1.2, external/su2 @ v8.5.0, external/openvsp @ 3.51.0"
else
  echo "One or more submodules are NOT at their pinned ref — do not proceed without human review." >&2
fi

exit "$status"
