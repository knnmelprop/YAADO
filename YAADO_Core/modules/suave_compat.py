"""Compatibility layer for importing SUAVE on modern Python/SciPy stacks.

SUAVE 2.5.2 was written for ~2021-era Python environments and relies on several
standard library and SciPy functions that have since been removed. Because SUAVE
is included as a pinned git submodule, we cannot edit its source code directly.

This module applies runtime monkeypatches to inject the deleted functions back
into memory *before* SUAVE is imported.
"""

import collections
import collections.abc
import sys

try:
    import scipy.integrate
    import scipy.misc
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False


def apply_shims() -> None:
    """Apply monkeypatches required to successfully `import SUAVE`."""
    
    # 1. Fix SUAVE's vendored `pint` library
    # In Python 3.10, the abstract base classes were removed from `collections`
    # and strictly moved to `collections.abc`.
    collections.MutableMapping = collections.abc.MutableMapping
    collections.Mapping = collections.abc.Mapping
    collections.Iterable = collections.abc.Iterable
    collections.Callable = collections.abc.Callable

    if not SCIPY_AVAILABLE:
        return

    # 2. Fix SUAVE's Battery networks
    # scipy.integrate.cumtrapz was renamed to cumulative_trapezoid in SciPy 1.14
    if not hasattr(scipy.integrate, "cumtrapz"):
        scipy.integrate.cumtrapz = scipy.integrate.cumulative_trapezoid

    # 3. Fix SUAVE's Cryogenic_Lead distributors
    # scipy.misc.derivative was completely removed in SciPy 1.12.
    # We inject a minimal central-difference stand-in to unblock the import.
    # WARNING: This shim is sufficient to satisfy the import, but has not been
    # validated for numerical correctness against the original SciPy implementation!
    if not hasattr(scipy.misc, "derivative"):
        def _derivative(func, x0, dx=1.0, n=1, args=(), order=3):
            return (func(x0 + dx, *args) - func(x0 - dx, *args)) / (2.0 * dx)
        scipy.misc.derivative = _derivative


# Automatically apply the shims when this module is imported
apply_shims()
