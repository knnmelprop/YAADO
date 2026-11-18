# XFOIL Section Polar

* **Method class**: `XFOILAnalysis` in [`xfoil_runner.py`](xfoil_runner.py)
* **Fidelity**: Level 1 (panel method coupled with an integral boundary layer)
* **Status**: Repaired and verified.

This module runs [XFOIL](https://web.mit.edu/drela/Public/web/xfoil/) (Drela, 1989) in batch mode on the section of **one** lifting surface that you pick from the vehicle: a wing (`Wings`) or a fin set (`Fins`). A plane or a rocket usually has several surfaces, so you choose one with `surface`. In the Flight Deck the parameter is a list of the vehicle's surfaces, with the ones that have an airfoil first.

XFOIL solves the viscous flow around the 2-D section: lift, drag (friction and pressure), quarter-chord moment and the transition point at each angle of attack. It uses $`e^n`$ transition with the exponent `n_crit`, and the Karman-Tsien correction for compressibility.

* **Section:** a wing uses `airfoil_root`. A fin set uses its optional `airfoil` field. The `airfoil` setting overrides both. It is a NACA 4- or 5-digit designation (`NACA2412`, `NACA23012`), or the path of a Selig or Lednicer coordinate file, for example from the [UIUC database](https://m-selig.ae.illinois.edu/ads/coord_database.html). A relative path is resolved from the folder you run YAADO in.
* **Chord:** the mean aerodynamic chord of the surface. For a wing it comes from `span`, `aspect_ratio` and `taper_ratio`; for a fin set from `chord_root` and `chord_tip`.
* **Reynolds number:** $`Re = \rho V \bar{c} / \mu`$, with $`V = M a`$ and $`\rho`$, $`a`$, $`\mu`$ from the ISA atmosphere at `altitude_m`. Set `reynolds` to compare with wind tunnel data. `mach` then only sets the compressibility correction, and 0 is incompressible.

| Input | Setting | From the TOML | Default |
| :--- | :--- | :--- | :--- |
| Surface | `surface` | `[aero_surfaces.<name>]` | The only one, else required |
| Flight Mach | `mach` | - | 0.15 (at most 0.7) |
| Altitude [m] | `altitude_m` | - | 0 |
| Angles of attack [deg] | `alpha_start_deg`, `alpha_end_deg`, `alpha_step_deg` | - | -5 to 15 by 0.5 |
| Transition exponent | `n_crit` | - | 9 (average wind tunnel); 11-13 for clean free flight, 4-8 for turbulent air |
| Airfoil | `airfoil` | `airfoil_root` or `airfoil` | Required for fins |
| Chord [m] | `chord` | Planform | Mean aerodynamic chord |
| Reynolds number | `reynolds` | - | From the flight condition |

The sweep starts at the angle nearest zero and goes up to the last angle. It then restarts from a fresh boundary layer and goes down to the first. An angle that does not converge is retried once, approached from 0.1° nearer zero after a fresh start. Angles that still fail are left out of the polar, and the run lists them. The upward sweep, the downward sweep and the retries are separate XFOIL calls of at most 20 s each. Near stall at higher Mach numbers XFOIL can diverge and slow down; such a call is stopped, keeps the angles it solved, and the run says so.

**Outputs:** $`C_{L,max}`$ and its angle, $`(L/D)_{max}`$ and its angle, $`C_{D,min}`$, the lift slope fitted from 2° below to 6° above the zero-lift angle, the zero-lift angle and the moment at zero lift. The run warns if the lift still rises at the last angle, because then stall lies beyond the sweep.

A logged run saves:
* `polar.png` and `polar.csv`: the section shape, the lift curve, the drag polar, $`C_L/C_D`$ and $`C_m`$;
* `polar_vs_reynolds.png` and `polar_vs_reynolds.csv`: the same section at 0.25, 0.5, 2 and 4 times the run's Reynolds number, which shows how sensitive it is to speed and size;
* `xfoil_input.txt`, `xfoil_output.log` and `xfoil_polar.txt`: the raw XFOIL input and output.

**Limits:**
* A 2-D section. A finite surface has a lower lift slope and an earlier stall, and it adds induced drag. Use a vortex-lattice method for the whole surface.
* Below a Reynolds number of about 50 000, laminar separation bubbles dominate and XFOIL is less reliable; the run warns.
* Only attached and lightly separated flow is credible. $`C_{L,max}`$ is usually somewhat optimistic.
* The Karman-Tsien correction is valid only below the critical Mach number of the section.

## Installing XFOIL

The `xfoil` executable must be on your `PATH`.

* **Windows:** download `XFOIL6.99.zip` from the [XFOIL page](https://web.mit.edu/drela/Public/web/xfoil/) and put the folder with `xfoil.exe` on your `PATH`.
* **Ubuntu and Debian:** `sudo apt install xfoil` installs a build that stops with a floating-point exception (SIGFPE) at its first angle of attack. Its Fortran runtime is set to stop on harmless floating-point exceptions, and YAADO reports this. Put a wrapper earlier on your `PATH` that switches the traps off:

  ```bash
  sudo apt install xfoil gcc
  mkdir -p ~/.local/lib ~/.local/bin
  echo 'void _gfortran_set_fpe(int v) { (void)v; }' | gcc -shared -fPIC -x c - -o ~/.local/lib/xfoil_nofpe.so
  printf '#!/bin/sh\nLD_PRELOAD="$HOME/.local/lib/xfoil_nofpe.so" exec /usr/bin/xfoil "$@"\n' > ~/.local/bin/xfoil
  chmod +x ~/.local/bin/xfoil
  ```

  Check with `which xfoil` that `~/.local/bin/xfoil` comes first. The XFOIL tests in `uv run pytest` skip themselves while no working XFOIL is found.

**Reference:** Drela, M., "XFOIL: An Analysis and Design System for Low Reynolds Number Airfoils", *Low Reynolds Number Aerodynamics*, Lecture Notes in Engineering 54, Springer, 1989.
