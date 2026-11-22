"""Cooperative cancellation of solver runs.

A caller hands a :class:`CancelToken` to the solver and calls :meth:`CancelToken.cancel`
from another thread. The solver checks the token between steps, and stops blocking
work such as a subprocess through a callback registered with :meth:`CancelToken.on_cancel`.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager


class RunCancelledError(Exception):
    """The run was cancelled through its :class:`CancelToken`.

    It does not derive from RuntimeError, so that code catching solver failures does not
    swallow a cancellation.
    """


class CancelToken:
    """Thread-safe cancellation flag shared by a caller and a running solver."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cancelled = False
        self._callbacks: list[Callable[[], None]] = []

    @property
    def cancelled(self) -> bool:
        """Whether :meth:`cancel` has been called."""
        return self._cancelled

    def cancel(self) -> None:
        """Request cancellation and run the registered callbacks once, in this thread."""
        with self._lock:
            if self._cancelled:
                return
            self._cancelled = True
            callbacks = list(self._callbacks)
        for callback in callbacks:
            callback()

    def raise_if_cancelled(self) -> None:
        """Stop the run if cancellation was requested.

        Raises:
            RunCancelledError: If :meth:`cancel` has been called.
        """
        if self._cancelled:
            raise RunCancelledError("Run cancelled")

    @contextmanager
    def on_cancel(self, callback: Callable[[], None]) -> Iterator[None]:
        """Call ``callback`` if the run is cancelled while the block runs.

        The callback runs at once if the token is already cancelled.

        Args:
            callback: Stops the blocking work, e.g. kills a subprocess. It must be
                quick and safe to call from another thread.
        """
        with self._lock:
            run_now = self._cancelled
            if not run_now:
                self._callbacks.append(callback)
        if run_now:
            callback()
        try:
            yield
        finally:
            with self._lock:
                if callback in self._callbacks:
                    self._callbacks.remove(callback)
