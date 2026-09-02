# How to join the YAADO team

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
Navigate to the [YAADO GitHub page](https://github.com/knnmelprop/YAADO) and click the **"Fork"** button at the top right of the screen. This creates a personal copy of the repository on your GitHub account.

### Step 2: Clone your fork locally
Navigate to your newly created fork on GitHub (it will be under `your_username/YAADO`). Click the green **"Code"** button, copy the provided HTTPS or SSH URL (if you do not know what SSH is, just use HTTPS), and run this in your terminal:
```bash
git clone <PASTE_YOUR_COPIED_LINK_HERE>
cd YAADO
```

### Step 3: Initialize the project
YAADO relies on heavily integrated physics engines (like SUAVE and SU2). You must pull these submodules and install the Python environment:
```bash
# Create a virtual environment and install all core dependencies using uv
uv sync

# Initialize submodules and install legacy physics engines (e.g., SUAVE)
./external/bootstrap_submodules.sh
```
> **MELProp Members:** If needed, you can copy the internal folders (containing the Science-Club-specific data) from the shared network drive directly into this repository. If you get any project specific results, make sure to upload them to the shared network drive and NEVER upload them to GitHub.

### Step 4: Verify your installation
Ensure everything installed correctly by running the test suite. 
```bash
uv run pytest
```

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

When developing, it is crucial to know where things belong. The repository is strictly divided between the generic execution framework (`YAADO_Core`) and user-defined workspaces (`Hangar` and `FlightLogs`).

```text
├── YAADO_Core/               # Foundation — extend via inheritance, DO NOT rewrite
│   ├── Foundation/          # Base abstractions (BaseComponent, BaseAnalysis, FidelityLevels)
│   ├── FlightDeck/          # OpenMDAO Problems and mission evaluation logic
│   ├── ComponentStore/          # Pydantic v2 schemas (strict type validation)
│   ├── modules/             # Swappable physics solvers (wind_tunnel, powerplant, etc.)
│   └── tests/               # Pytest unit suite perfectly mirroring the modules
│
├── Hangar/                  # User workspace: Declarative vehicle TOML configs
├── FlightLogs/              # User workspace: Output data, logs, and custom study scripts
├── external/                # Git submodules (SUAVE, pyCycle, SU2, OpenVSP)
```
