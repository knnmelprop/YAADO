"""Unit tests for the SolverRegistry and SolverInfo foundation abstractions."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from YAADO_Core.Foundation.solver_registry import (
    DEFAULT_REGISTRY,
    SolverInfo,
    SolverRegistry,
)


def test_solver_info_is_frozen():
    """Verify SolverInfo is immutable."""
    info = SolverInfo(name="test_tool", executable="test_bin", description="Test description")
    assert info.name == "test_tool"
    assert info.executable == "test_bin"
    assert info.description == "Test description"

    with pytest.raises(FrozenInstanceError):
        info.name = "new_name"  # type: ignore[misc]


def test_solver_info_availability(monkeypatch: pytest.MonkeyPatch):
    """Verify is_available handles pure-Python solvers and PATH lookups."""
    # Pure-Python solver (no executable required)
    python_solver = SolverInfo(name="pure_python")
    assert python_solver.is_available() is True

    # External executable found
    monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/mock_tool" if cmd == "mock_tool" else None)
    found_tool = SolverInfo(name="found", executable="mock_tool")
    assert found_tool.is_available() is True

    # External executable not found
    missing_tool = SolverInfo(name="missing", executable="nonexistent_tool")
    assert missing_tool.is_available() is False


def test_solver_registry_register_and_get():
    """Verify registering and retrieving solvers."""
    registry = SolverRegistry()
    info = SolverInfo(name="my_solver", description="Initial description")
    registry.register(info)

    assert registry.is_registered("my_solver") is True
    assert registry.get("my_solver") == info

    # Overwrite
    updated_info = SolverInfo(name="my_solver", description="Updated description")
    registry.register(updated_info)
    assert registry.get("my_solver").description == "Updated description"


def test_solver_registry_get_unregistered_raises_key_error():
    """Verify get on unregistered solver raises KeyError with available solvers."""
    registry = SolverRegistry()
    registry.register(SolverInfo(name="alpha"))
    registry.register(SolverInfo(name="beta"))

    with pytest.raises(KeyError, match="Solver 'gamma' not registered; available: \\['alpha', 'beta'\\]"):
        registry.get("gamma")


def test_solver_registry_query_methods(monkeypatch: pytest.MonkeyPatch):
    """Verify is_registered, all_solvers, and available query methods."""
    registry = SolverRegistry()
    registry.register(SolverInfo(name="tool_b", executable="bin_b"))
    registry.register(SolverInfo(name="tool_a", executable=""))

    assert registry.is_registered("tool_a") is True
    assert registry.is_registered("tool_b") is True
    assert registry.is_registered("tool_c") is False

    # all_solvers returns sorted list
    assert registry.all_solvers() == ["tool_a", "tool_b"]

    # available filters by executable existence
    monkeypatch.setattr("shutil.which", lambda cmd: None)
    assert registry.available() == ["tool_a"]

    monkeypatch.setattr("shutil.which", lambda cmd: "/bin/bin_b" if cmd == "bin_b" else None)
    assert registry.available() == ["tool_a", "tool_b"]


def test_default_registry_initially_empty():
    """Verify DEFAULT_REGISTRY is initialized empty until methods are verified."""
    assert DEFAULT_REGISTRY.all_solvers() == []
    assert DEFAULT_REGISTRY.available() == []
