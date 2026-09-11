# Physics Modules

This directory contains the swappable physics solvers for the YAADO framework. Solvers derive from `BaseAnalysis` and return standard `AnalysisResults` containers.

## Repaired and Verified methods:

*(None yet)*

## Not Yet Repaired and/or verified methods:

| Submodule | Method / Tool | File | Fidelity | Description |
| :--- | :--- | :--- | :---: | :--- |
| **Airframe** | `OpenVSPExporter` | [`airframe/generator_methods/openvsp.py`](airframe/generator_methods/openvsp.py) | L1 | OpenVSP geometry generation |
| **Airframe** | Gmsh Slicer | [`airframe/slicer_methods/gmsh.py`](airframe/slicer_methods/gmsh.py) | - | STEP cross-section slicing utility |
| **Flight Dynamics** | `PointMass3DOFBoostAnalysis` | [`flight_dynamics/methods/point_mass_3dof.py`](flight_dynamics/methods/point_mass_3dof.py) | L0 | 3-DOF point-mass rocket boost trajectory simulation |
| **Powerplant** | `InletPerformanceAnalysis` | [`powerplant/inlet_methods/wedge.py`](powerplant/inlet_methods/wedge.py) | L0 | Supersonic spike/wedge inlet total pressure recovery |
| **Powerplant** | `MultiConeInletPerformanceAnalysis` | [`powerplant/inlet_methods/wedge.py`](powerplant/inlet_methods/wedge.py) | L0 | Multi-cone supersonic inlet compression |
| **Powerplant** | Taylor-Maccoll Solver | [`powerplant/inlet_methods/taylor_maccoll.py`](powerplant/inlet_methods/taylor_maccoll.py) | L0 | Conical shock ODE integration |
| **Powerplant** | `RamjetCycleAnalysis` | [`powerplant/cycle_methods/mattingly.py`](powerplant/cycle_methods/mattingly.py) | L2 | 1-D thermodynamic station ramjet cycle |
| **Powerplant** | `GrzywkaCombustorNozzleAnalysis` | [`powerplant/cycle_methods/grzywka.py`](powerplant/cycle_methods/grzywka.py) | L2 | 1-D ramjet combustor and nozzle expansion |
| **Powerplant** | Heiser & Pratt Cycle | [`powerplant/cycle_methods/heiser_pratt.py`](powerplant/cycle_methods/heiser_pratt.py) | L2 | Stream-thrust ramjet cycle routines |
| **Stability & Control** | `BarrowmanStabilityAnalysis` | [`stability_control/methods/barrowman/barrowman_stability.py`](stability_control/methods/barrowman/barrowman_stability.py) | L0 | Slender-body rocket static margin and CP |
| **Stability & Control** | `BarrowmanExtendedAnalysis` | [`stability_control/methods/barrowman/barrowman_extended.py`](stability_control/methods/barrowman/barrowman_extended.py) | L0 | Extended Barrowman with transonic corrections |
| **Stability & Control** | DATCOM Runner | [`stability_control/methods/datcom/datcom_class_sweep.py`](stability_control/methods/datcom/datcom_class_sweep.py) | L1 | USAF Digital DATCOM deck generator and wrapper |
| **Stability & Control** | Ackeret Fin Check | [`stability_control/methods/ackeret/ackeret_fin_check.py`](stability_control/methods/ackeret/ackeret_fin_check.py) | L0 | Supersonic fin lift-curve slope calculation |
| **Wind Tunnel** | `XFOILAnalysis` | [`wind_tunnel/methods/xfoil/xfoil_runner.py`](wind_tunnel/methods/xfoil/xfoil_runner.py) | L0 / L1 | Airfoil polar analysis with Ackeret supersonic fallback |
| **Wind Tunnel** | `AVLFinAnalysis` | [`wind_tunnel/methods/avl/avl_builder.py`](wind_tunnel/methods/avl/avl_builder.py) | L1 | Subsonic fin vortex lattice analysis (AVL) |
| **Wind Tunnel** | `AVLAnalysis` | [`wind_tunnel/methods/avl/avl_wrapper.py`](wind_tunnel/methods/avl/avl_wrapper.py) | L1 | Subsonic wing vortex lattice analysis (AVL) |
| **Wind Tunnel** | `SU2ConfigGeneration` | [`wind_tunnel/methods/su2/su2_config_template.py`](wind_tunnel/methods/su2/su2_config_template.py) | L2 / L3 | SU2 CFD configuration template generator |