# How to join the IADE team

Welcome! To join the development team, pick an issue you want to work on, complete the onboarding steps below, and open a Pull Request (PR). Once your first PR is merged, you can pick a subteam and officially join the development!

---

## 1. Prerequisites

Before downloading the code, ensure your system is ready:

1. **Install uv:** We use `uv` for lightning-fast Python dependency management. [Install it here](https://docs.astral.sh/uv/getting-started/installation/).
2. **Install OpenGL (Linux only):** The `gmsh` CAD mesh generation tool requires a system-level graphics library. On Ubuntu/Debian, run:
   ```bash
   sudo apt-get update
   sudo apt-get install libglu1-mesa
   ```
> If not on Linux, you can get OpenGL [here](https://gmsh.info/#Download)

## 2. The Contributor Pipeline

Follow these exact steps to set up your environment and make your first contribution:

### Step 1: Fork the repository
Navigate to the [IADE GitHub page](https://github.com/knnmelprop/iade) and click the **"Fork"** button at the top right of the screen. This creates a personal copy of the repository on your GitHub account.

### Step 2: Clone your fork locally
Navigate to your newly created fork on GitHub (it will be under `your_username/iade`). Click the green **"Code"** button, copy the provided HTTPS or SSH URL, and run this in your terminal:
```bash
git clone <PASTE_YOUR_COPIED_LINK_HERE>
cd iade
```

### Step 3: Initialize the project
IADE relies on heavily integrated physics engines (like SUAVE and SU2). You must pull these submodules and install the Python environment:
```bash
# Pull all required external submodules
git submodule update --init --recursive

# Create a virtual environment and install all dependencies using uv
uv sync
```
> **Science Club Members:** You must copy the internal `.agents/` and `.claude/` folders (containing the proprietary Ramjet and GTM-140 data) from the shared network drive directly into the root directory of this repository. These folders are ignored by Git to prevent sensitive data from leaking into the open-source repository. If you get any project specific results, make sure to upload them to the shared network drive.

### Step 4: Verify your installation
Ensure everything installed correctly by running the test suite. 
```bash
uv run pytest IADE_Core/tests/ --tb=short
```
> **Warning:** Always explicitly target the `IADE_Core/tests/` directory! Do not run a bare `pytest` from the repository root, as it will attempt to collect tests from the external submodules and crash.

### Step 5: Branch and Develop
Create a new branch for the issue you want to work on:
```bash
git switch -c feature/my-awesome-feature
```
Make your code changes, write tests, and ensure the test suite still passes!

Ensure your code follows the guidelines outlined in [`CONTRIBUTING.md`](CONTRIBUTING.md).

### Step 6: Push and open a PR
Push your branch back up to your fork on GitHub:
```bash
git push origin feature/my-awesome-feature
```
Go to your fork on GitHub, and you will see a green button to **"Compare & pull request"**. Click it to submit your code to the main repository!

---

## 3. Repository Architecture

When developing, it is crucial to know where things belong. The repository is strictly divided between the generic execution framework (`IADE_Core`) and user-defined workspaces (`Hangar` and `FlightLogs`).

```text
├── IADE_Core/               # Foundation — extend via inheritance, DO NOT rewrite
│   ├── Foundation/          # Base abstractions (BaseComponent, BaseAnalysis, FidelityLevels)
│   ├── FlightDeck/          # OpenMDAO Problems and mission evaluation logic
│   ├── Inspectors/          # Pydantic v2 schemas (strict type validation)
│   ├── modules/             # Swappable physics solvers (wind_tunnel, powerplant, etc.)
│   └── tests/               # Pytest unit suite perfectly mirroring the modules
│
├── Hangar/                  # User workspace: Declarative vehicle YAML configs
├── FlightLogs/              # User workspace: Output data, logs, and custom study scripts
├── external/                # Git submodules (SUAVE, pyCycle, SU2, OpenVSP)
```
