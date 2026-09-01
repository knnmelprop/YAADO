# YAADO — by MELprop
![Python](https://img.shields.io/badge/python-3.11+-blue.svg) ![License](https://img.shields.io/badge/license-Apache%202.0-green.svg) ![Tests](https://img.shields.io/badge/tests-passing-brightgreen.svg) [![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/knnmelprop/YAADO)

The project aims to be a user-friendly preliminary design and Multidisciplinary Design Optimization (MDO) environment for aerospace vehicles. YAADO's goal is to enable everybody to use variable-fidelity design analysis tools to move your designs from paper and laptop to the sky.

## Features
* **Declarative Design:** Build rockets and UAVs using simple TOML configurations — no Python programming required.
* **Variable-Fidelity Aerodynamics:** Seamlessly swap between empirical handbook formulas (DATCOM), Vortex Lattice Methods (AVL), 2D panel methods (XFOIL), and High-Fidelity CFD (SU2).
* **Propulsion Analysis:** Built-in 1-D thermodynamic engine cycle analysis and custom turbojet performance maps.

## Getting Started

> If you want to join the project please check [`ONBOARDING.md`](ONBOARDING.md). README is for end-users.

### 1. Installation
To use YAADO, clone the repository and install the environment. Because YAADO relies on heavily integrated physics engines, you must initialize the submodules:

```bash
git clone https://github.com/knnmelprop/YAADO.git
cd YAADO
uv sync
./external/bootstrap_submodules.sh
```

### 2. Workspace Layout
To make everything work, you only need to interact with two main directories:
```text
├── Hangar/                  # User workspace: Declarative vehicle TOML configs
└── FlightLogs/              # User workspace: Output data, logs, and custom study scripts
```

> You will also be able to pick fidelity levels and more, but this is in development as of now

### 3. Running an Analysis
> Note: Execution scripts are currently being finalized by the development team. Check back soon for exact CLI commands!

---

## Acknowledgments

This framework builds upon and interfaces with several major open-source aerospace tools, included as submodules in `external/`:
* **[SUAVE](http://suave.stanford.edu/)**: Core multi-fidelity computational physics engine.
* **[pyCycle](https://github.com/OpenMDAO/pyCycle)**: 1-D thermodynamic engine cycle analysis.
* **[SU2](https://github.com/su2code/SU2)**: High-fidelity Computational Fluid Dynamics (CFD) simulation suite.
* **[OpenVSP](https://openvsp.org/)**: Parametric aircraft geometry tool.

Each tool remains unmodified in its respective folder and is governed by its own open-source license.
