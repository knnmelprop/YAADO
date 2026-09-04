# Contributing to YAADO

## Branch naming and PRs

You have three options when it comes to branch pre-fix

| Branch Prefix | Description |
|---|---|
| `feature/*` | Adding a new feature or capability. |
| `fix/*` | Focused bug fixes. |
| `docs/*` | Documentation-only work. |

For example, your branch could be named `feature/some-cool-feature` if you are adding "some cool feature"

## Commit messages

You have four options when it comes to commit prefixes

| Commit Prefix | Description |
|---|---|
| `feat:` | Adding a new feature or capability. |
| `fix:` | Fixing a bug or resolving an issue. |
| `docs:` | Documentation-only changes. |
| `chore:` | Maintenance, refactoring, or updating dependencies. |

The prefix should be followed by a topic in brackets. And this is followed by a more detailed description.

For example, your commit message could be `feat(ramjet-cycle-analysis): make graphing automatic` if you are adding that feature.

## Coding Standards & Documentation

To keep the codebase clean and maintainable, please adhere to the following documentation practices:

1. **Function Docstrings:** All functions, methods, and classes must contain clear docstrings (we use the Google-style format). Please describe what the function does, what arguments it takes, and what it returns.
2. **Folder READMEs:** Whenever a directory contains a distinct module, subsystem, or architectural concept (i.e., whenever there is something to be described at the system level), it should contain its own `README.md`. This helps new contributors understand the high-level purpose of the folder without having to read the raw code.
3. **Architecture Mirroring:** The `YAADO_Core/tests/` directory must perfectly mirror the directory structure of the main codebase. If you create a new module at `YAADO_Core/modules/powerplant/valves.py`, its tests must live at `YAADO_Core/tests/modules/powerplant/test_valves.py`.