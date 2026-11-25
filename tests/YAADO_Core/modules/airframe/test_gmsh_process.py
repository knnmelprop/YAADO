"""Tests for running Gmsh work in a child process."""

from __future__ import annotations

import math
import os
import threading
import time

import pytest

from YAADO_Core.Foundation.cancellation import CancelToken, RunCancelledError
from YAADO_Core.modules.airframe import gmsh_process
from YAADO_Core.modules.airframe.gmsh_process import GmshError, run_gmsh


def test_the_return_value_comes_back() -> None:
    assert run_gmsh(math.sqrt, 2.0).value == math.sqrt(2.0)


def test_an_exception_becomes_a_gmsh_error_with_its_message() -> None:
    with pytest.raises(GmshError, match="math domain error|nonnegative"):
        run_gmsh(math.sqrt, -1.0)


def test_console_output_is_captured() -> None:
    assert run_gmsh(os.system, "echo from the child").log.strip() == "from the child"


def test_a_crash_reports_the_status() -> None:
    with pytest.raises(GmshError, match="status"):
        run_gmsh(os._exit, 7)


def test_cancelling_kills_the_child() -> None:
    token = CancelToken()
    threading.Timer(1.0, token.cancel).start()
    start = time.monotonic()
    with pytest.raises(RunCancelledError):
        run_gmsh(time.sleep, 60.0, cancel_token=token)
    assert time.monotonic() - start < 20.0


def test_a_missing_library_names_the_package(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    real_import = builtins.__import__

    def fail(name: str, *args: object, **kwargs: object) -> object:
        if name == "gmsh":
            raise OSError("libGLU.so.1: cannot open shared object file")
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    gmsh_process.gmsh_problem.cache_clear()
    monkeypatch.setattr(builtins, "__import__", fail)
    try:
        problem = gmsh_process.gmsh_problem()
    finally:
        monkeypatch.undo()
        gmsh_process.gmsh_problem.cache_clear()
    assert problem is not None and "libglu1-mesa" in problem
