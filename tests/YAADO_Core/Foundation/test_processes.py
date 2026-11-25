"""Tests for the cancellable subprocess runner."""

from __future__ import annotations

import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from YAADO_Core.Foundation.cancellation import CancelToken, RunCancelledError
from YAADO_Core.Foundation.processes import run_process

SLEEP = "import sys, time; print('started', flush=True); time.sleep(30)"


def test_output_input_and_working_directory(tmp_path: Path) -> None:
    code = "import os, sys; print(os.getcwd()); print(sys.stdin.read()); sys.exit(3)"
    done = run_process([sys.executable, "-c", code], input="hello", cwd=tmp_path, timeout=20.0)
    assert done.returncode == 3
    assert done.stdout.split() == [str(tmp_path.resolve()), "hello"]


def test_the_timeout_keeps_the_output_so_far() -> None:
    with pytest.raises(subprocess.TimeoutExpired) as caught:
        run_process([sys.executable, "-c", SLEEP], timeout=1.5)
    assert "started" in str(caught.value.stdout)


def test_cancelling_kills_the_process() -> None:
    token = CancelToken()
    threading.Timer(0.5, token.cancel).start()
    start = time.monotonic()
    with pytest.raises(RunCancelledError):
        run_process([sys.executable, "-c", SLEEP], cancel_token=token)
    assert time.monotonic() - start < 10.0


def test_a_cancelled_token_starts_nothing(tmp_path: Path) -> None:
    token = CancelToken()
    token.cancel()
    marker = tmp_path / "ran"
    with pytest.raises(RunCancelledError):
        run_process(
            [sys.executable, "-c", f"open({str(marker)!r}, 'w')"], cancel_token=token
        )
    assert not marker.exists()
