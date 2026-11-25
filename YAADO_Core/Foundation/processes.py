"""Run external solvers as subprocesses that a cancelled run can kill."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

from YAADO_Core.Foundation.cancellation import CancelToken


def kill_process(process: subprocess.Popen[str]) -> None:
    """Kill a process started by :func:`run_process` and everything it started."""
    if process.poll() is not None:
        return
    try:
        if sys.platform == "win32":
            process.kill()
        else:
            os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def run_process(
    args: list[str],
    *,
    input: str = "",
    cwd: Path | None = None,
    timeout: float | None = None,
    cancel_token: CancelToken | None = None,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Like ``subprocess.run``, but the process is also killed when the run is cancelled.

    The process runs in its own process group, so a wrapper script's child dies with it.

    Args:
        args: Command and its arguments.
        input: Text sent to the process.
        cwd: Working directory. Defaults to the current one.
        timeout: Wall-clock limit [s]. Defaults to none.
        cancel_token: Kills the process when cancelled.
        env: Environment of the process. Defaults to the current one.

    Returns:
        The finished process with its output.

    Raises:
        subprocess.TimeoutExpired: At the time limit, with the output so far.
        RunCancelledError: If the run was cancelled.
    """
    token = cancel_token or CancelToken()
    token.raise_if_cancelled()
    process = subprocess.Popen(
        args,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=cwd,
        env=env,
        start_new_session=sys.platform != "win32",
    )
    try:
        with token.on_cancel(lambda: kill_process(process)):
            try:
                stdout, stderr = process.communicate(input, timeout=timeout)
            except subprocess.TimeoutExpired:
                kill_process(process)
                stdout, stderr = process.communicate()
                raise subprocess.TimeoutExpired(
                    args, timeout or 0.0, stdout, stderr
                ) from None
    except BaseException:
        kill_process(process)
        process.wait()
        raise
    token.raise_if_cancelled()
    return subprocess.CompletedProcess(args, process.returncode, stdout, stderr)
