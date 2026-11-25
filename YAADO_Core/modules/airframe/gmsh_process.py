"""Run Gmsh work in a child process.

Gmsh holds one global model per process, writes OpenCASCADE messages straight to stdout,
and cannot be interrupted. A child process keeps that output off the cockpit, can be
killed when a run is cancelled, and takes a Gmsh crash with it.
"""

from __future__ import annotations

import functools
import os
import pickle
import sys
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Generic, TypeVar

from YAADO_Core.Foundation.cancellation import CancelToken
from YAADO_Core.Foundation.processes import run_process

TArgument = TypeVar("TArgument")
TResult = TypeVar("TResult")

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CHILD_COMMAND = "from YAADO_Core.modules.airframe.gmsh_process import _child; _child()"
_LOG_TAIL_LINES = 8


class GmshError(RuntimeError):
    """Gmsh failed to build, slice or mesh the geometry."""


@dataclass(frozen=True)
class GmshOutcome(Generic[TResult]):
    """Return value of a function run by :func:`run_gmsh`.

    Attributes:
        value: What the function returned.
        log: Gmsh and OpenCASCADE console output.
    """

    value: TResult
    log: str


@functools.lru_cache(maxsize=1)
def gmsh_problem() -> str | None:
    """Why Gmsh cannot be used here, or None if it works."""
    try:
        import gmsh  # noqa: F401
    except ImportError:
        return "The gmsh Python package is not installed (run 'uv sync')."
    except OSError as exc:
        return (
            f"Gmsh does not load: {exc}. On Ubuntu and Debian run 'sudo apt install libglu1-mesa'."
        )
    return None


@contextmanager
def gmsh_session(model_name: str) -> Iterator[ModuleType]:
    """Open a Gmsh model in meters, ignoring the user's Gmsh configuration files.

    Args:
        model_name: Name of the Gmsh model.

    Yields:
        The ``gmsh`` module with the model as the current one.
    """
    import gmsh

    gmsh.initialize(readConfigFiles=False, interruptible=False)
    try:
        gmsh.option.setNumber("General.Terminal", 1)
        gmsh.option.setNumber("General.Verbosity", 3)
        gmsh.option.setString("Geometry.OCCTargetUnit", "M")
        gmsh.option.setNumber("Geometry.OCCBoundsUseStl", 1)
        gmsh.model.add(model_name)
        yield gmsh
    finally:
        gmsh.finalize()


def run_gmsh(
    function: Callable[[TArgument], TResult],
    argument: TArgument,
    *,
    cancel_token: CancelToken | None = None,
    timeout: float | None = None,
) -> GmshOutcome[TResult]:
    """Call ``function(argument)`` in a child process.

    Args:
        function: Module-level function of this package.
        argument: Picklable argument.
        cancel_token: Kills the child when cancelled.
        timeout: Wall-clock limit [s]. Defaults to none.

    Returns:
        The return value and the console output.

    Raises:
        GmshError: If the function raises or the child crashes.
        subprocess.TimeoutExpired: At the time limit.
        RunCancelledError: If the run was cancelled.
    """
    with tempfile.TemporaryDirectory(prefix="yaado_gmsh_") as tmp:
        job, outcome = Path(tmp) / "job.pickle", Path(tmp) / "outcome.pickle"
        job.write_bytes(pickle.dumps((function, argument)))
        path = os.pathsep.join(filter(None, [str(_REPO_ROOT), os.environ.get("PYTHONPATH")]))
        completed = run_process(
            [sys.executable, "-c", _CHILD_COMMAND, str(job), str(outcome)],
            timeout=timeout,
            cancel_token=cancel_token,
            env={**os.environ, "PYTHONPATH": path},
        )
        log = completed.stdout + completed.stderr
        if not outcome.is_file():
            tail = "\n".join(log.strip().splitlines()[-_LOG_TAIL_LINES:])
            raise GmshError(f"Gmsh stopped with status {completed.returncode}:\n{tail}")
        error, value = pickle.loads(outcome.read_bytes())
    if error is not None:
        raise GmshError(error)
    return GmshOutcome(value=value, log=log)


def _child() -> None:
    """Entry point of the child process: run the pickled job and save its outcome."""
    function, argument = pickle.loads(Path(sys.argv[1]).read_bytes())
    error: str | None = None
    value = None
    try:
        value = function(argument)
    except Exception as exc:  # noqa: BLE001 - reported to the parent, whatever Gmsh raises
        error = str(exc) or type(exc).__name__
    Path(sys.argv[2]).write_bytes(pickle.dumps((error, value)))
