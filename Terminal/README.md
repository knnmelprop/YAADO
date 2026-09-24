# Interactive Terminal User Interface (TUI)

The YAADO terminal interface is built on [`Textual`](https://textual.textualize.io/) as a keyboard- and mouse-accessible cockpit for aerospace vehicle design, assembly, solver chaining, and telemetry inspection. It enables researchers and engineers to interact with declarative vehicle models and computational physics engines without writing boilerplate code.

---

## Launching

The TUI is the primary user-facing entry point for YAADO:

```bash
yaado
```

### Global Navigation Hotkeys
* `m` — Jump to **Main Cockpit**
* `h` — Jump to **Hangar Workshop**
* `f` — Jump to **Flight Deck**
* `d` — Toggle Dark / Light theme
* `q` — Quit YAADO

## 1. Tab 1: Main View (Cockpit & Telemetry Landing)

The Main View serves as the landing dashboard. It provides an immediate overview of available vehicle configurations, quick access to template wizards, and live telemetry previews.

* **FlightLogs Quick Launch:**
  * Quick links to trigger standard analyses and review recent simulation activity.
* **Telemetry Preview:**
  * High-density, scrollable inspection window displaying subsystem specs in canonical SI units and status advisories.

## 2. Tab 2: Hangar (Vehicle Workshop)

The Hangar unifies component discovery, spatial vehicle layout, and schema-driven parameter inspection into an interactive assembly environment.

* **Component Store:**
  * Catalog of available aerospace components (bodies, propulsion systems, aerodynamic surfaces, mass properties).
  * Add components directly to the active vehicle workspace.
* **Vehicle Workspace:**
  * Displays the longitudinal arrangement and component tree of the vehicle from nose to tail.
  * Re-order, stage, and remove components along the longitudinal axis.
* **Hangar Library & Reference Protection:**
  * Switch between active projects and reference examples.
  * Configurations in `Hangar/examples/` are strictly read-only; editing an example prompts to fork it into a writable user project (`Hangar/<name>/`).
* **Component Parameter Inspector:**
  * Dynamic form fields with real-time schema validation.
  * Canonical SI unit badges on all numerical inputs.
  * One-click baseline prefill from physical schema defaults.

## 3. Tab 3: Flight Deck (Solvers, Pipelines & FlightLogs)

The Flight Deck coordinates physics solvers, multi-stage computational pipelines, parameter sweeps, and simulation log inspection.

* **Available Solvers:**
  * Lists verified and available physics solvers (Point Mass 3-DOF, empirical aerodynamics, pyCycle engine maps, high-fidelity CFD).
* **Analysis Pipeline & Chaining:**
  * Sequence computational modules so that output metrics or aerodynamic polars from stage $N$ pipe directly into initial conditions or lookup tables for stage $N+1$.
* **Inspect Results:**
  * Real-time telemetry, scalar metrics, CSV/Parquet tables, and convergence status indicators. For CSV tables, there should be an "open in excel" button.
* **FlightLogs History:**
  * Run history tree organized by vehicle and timestamp (`FlightLogs/<vehicle>/<timestamp>/`).
  * Direct inspection of execution logs, summary metrics, and generated plots.

## 4. UI Design Directives

* **The 5% Amber Rule:** Propulsion Amber is strictly reserved for high-contrast highlights (active tab titles, card headers, key shortcuts, and primary call-to-actions). It is never used for large container backgrounds.
* **Transparent Terminal Passthrough:** Seamless integration with host terminal palettes using ANSI defaults rather than hardcoded background blocks.
* **Strict SI Units:** All displayed parameters, telemetry fields, and input badges use canonical SI units without conversion ambiguities.