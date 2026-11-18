"""Tests for the cooperative cancel token shared by the cockpit and the solvers."""

from __future__ import annotations

import threading

import pytest

from YAADO_Core.Foundation.cancellation import CancelToken, RunCancelledError


def test_cancel_runs_registered_callbacks_once() -> None:
    token = CancelToken()
    calls: list[str] = []
    token.raise_if_cancelled()
    with token.on_cancel(lambda: calls.append("kill")):
        assert not token.cancelled
        token.cancel()
        token.cancel()
    assert token.cancelled
    assert calls == ["kill"]
    with pytest.raises(RunCancelledError):
        token.raise_if_cancelled()


def test_callback_runs_at_once_on_a_cancelled_token() -> None:
    token = CancelToken()
    token.cancel()
    calls: list[str] = []
    with token.on_cancel(lambda: calls.append("kill")):
        assert calls == ["kill"]


def test_callback_is_dropped_after_its_block() -> None:
    token = CancelToken()
    calls: list[str] = []
    with token.on_cancel(lambda: calls.append("kill")):
        pass
    token.cancel()
    assert calls == []


def test_cancel_from_another_thread_wakes_a_waiting_solver() -> None:
    token = CancelToken()
    woken = threading.Event()
    with token.on_cancel(woken.set):
        threading.Timer(0.05, token.cancel).start()
        assert woken.wait(5.0)
    assert token.cancelled


def test_cancellation_is_not_a_solver_failure() -> None:
    """Code that turns RuntimeError into a failed run must not swallow a cancel."""
    assert not issubclass(RunCancelledError, RuntimeError)
