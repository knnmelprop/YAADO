# Interactive Terminal Interface (TUI) Specification

The YAADO interactive terminal user interface is built on [`textual`](https://textual.textualize.io/) as a modern, high-contrast, keyboard- and mouse-accessible terminal interface. It serves as the primary cockpit for vehicle assembly, solver workflow chaining, and interactive results analysis.

## 1. Design Principles & Architecture

* **Modern TUI Aesthetic:** Clean layouts using crisp terminal borders (`round` or `heavy`), distinct semantic coloring (`$yaado-primary`, `$yaado-accent`, `$yaado-success`, `$yaado-error`), and complete support for dark and light terminal themes. Modern UI design principles must be applied (such as rounded edges).
* **Decoupled & Data-Driven:** The TUI dynamically reflects Pydantic schemas from [`ComponentStore`](../YAADO_Core/ComponentStore) and solver discovery from [`SolverRegistry`](../YAADO_Core/Foundation/solver_registry.py). It does not hardcode vehicle models or leaf classes.
* **Non-Blocking Async Execution:** All solver routines run in background worker threads (`textual.worker.Worker`), streaming live logs and progress to the UI without freezing user interaction.
* **Three-Tab Stage Structure:**
  1. **Main View (Cockpit & Dashboard):** Default landing overview displaying system readiness, active vehicle summary, recent simulation telemetry, and quick launchpad actions.
  2. **Hangar (Vehicle Workshop):** Unified vehicle management workspace—browse and inspect existing vehicles/examples, and interactively assemble or edit vehicles using the spatial layout canvas and schema-driven parameter forms.
  3. **Flight Deck (Analyses & FlightLogs):** Configure physics solvers, chain computational pipelines, run batch parameter sweeps, and inspect historical runs in `FlightLogs`.

Tabs are displayed at the top beneath the header chrome, with the active tab clearly highlighted. Tabs are fully clickable and also accessible via keyboard shortcuts (`1`, `2`, `3`).

---

## 2. Tab 1: Main View (Cockpit & Dashboard)

The Main View serves as the default landing screen and operational summary cockpit upon launching `yaado`.

* **System Readiness & Telemetry:**
  * Displays discovered and verified solvers from `SolverRegistry` (e.g. `PointMass3DOFBoostAnalysis`).
  * ISA atmosphere model status and environment sanity checks.
* **Active Vehicle Card:**
  * Shows the currently loaded or active vehicle configuration, basic mass properties ($m_\text{total}$, CG location), and major subsystem tags.
* **Recent Flight Activity:**
  * Summary cards of recent simulation runs located in `FlightLogs/` with quick-glance convergence indicators (`$yaado-success` for converged/valid, `$yaado-error` for failure/divergence).
* **Quick Launchpad:**
  * Primary navigation shortcuts and clickable buttons:
    * `[H] Hangar Workshop`: Jump to vehicle library and builder.
    * `[N] New Vehicle`: Directly initiate assembly for a new vehicle.
    * `[F] Flight Deck`: Jump to solver execution and analysis deck.

---

## 3. Tab 2: Hangar (Vehicle Workshop)

The Hangar unifies vehicle inspection, template cloning, and interactive vehicle assembly into a single cohesive workspace.

### 3.1 Vehicle Library & Inspection
* **Browser View:**
  * Displays user configurations (`Hangar/<name>/`) and pre-built reference vehicles (`Hangar/examples/`).
  * Shows comprehensive vehicle specs: name, description, overall mass properties, and subsystem breakdown (bodies, aero surfaces, propulsion).
* **Reference Protection (Forking):**
  * Vehicles in `Hangar/examples/` (such as ALVRJ or AGM-84 Harpoon) are strictly **read-only** templates.
  * Attempting to modify an example opens a **"Fork Vehicle"** prompt, cloning the configuration into a new writable user directory (`Hangar/<new_name>/`).
* **Actions:**
  * `[N] New Vehicle`: Opens the Assembly Mode with a blank or baseline template.
  * `[E] Edit Vehicle`: Loads the selected configuration into Assembly Mode.
  * `[C] Fork / Clone`: Clones any selected vehicle to a new target name.
  * `[D] Delete / Archive`: Safely removes user configurations.
  * Actions are available via both keyboard hotkeys and clickable buttons.

### 3.2 Integrated Assembly Mode
Activating "New" or "Edit" switches the Hangar view into Assembly Mode:
* **Spatial Orientation & Layout Canvas:**
  * An interactive track or schematic diagram representing the vehicle from nose to tail with positional snap zones along the longitudinal ($x$) axis (Nose, Forward, Mid, Aft, Base).
  * Components can be dragged from the side palette and dropped into spatial zones, or re-ordered along the longitudinal axis via drag or keyboard shortcuts.
* **Component Palette:**
  * Categorized drawer dynamically populated from `ComponentStore` (`bodies`, `aero_surfaces`, `propulsion`, `mass_properties`).
* **Unique Component Naming:**
  * Auto-generates unique, descriptive tags (e.g. `main_body`, `aft_fins`, `solid_booster_1`) to satisfy `BaseVehicleConfig` namespace validation, with user-editable names in the inspector.
* **Dynamic Parameter Inspector:**
  * Fields, types, constraints, and tooltips are generated directly from Pydantic `model_fields`.
  * **SI Unit Badges:** Every field displays its canonical SI unit (retrieved from `UNITS: ClassVar[dict[str, str]]`).
  * **Reactive Validation:** Outline turns green (`border: tall $yaado-success`) on valid input and red (`border: tall $yaado-error`) on schema constraint violation.
  * **Baseline Prefill:** Shortcuts for per-field schema example fallbacks (`field_info.examples[0]`) and one-click component baseline generation (`VehicleTemplateGenerator.prefill_component_values`).
* **Draft Persistence vs. Canonical TOML:**
  * In-progress modifications auto-save to `Hangar/<name>/.draft.toml`.
  * Canonical `Hangar/<name>/<name>.toml` is generated only when the user clicks **"Finalize / Save Vehicle"**, executing strict validation through `BaseVehicleConfig.model_validate()`.

---

## 4. Tab 3: Flight Deck (Analyses, Pipelines & FlightLogs)

The Flight Deck coordinates physics solver runs and serves as an interactive viewer for simulation outputs.

### 4.1 Solver Execution & Discovery
* **Dynamic Solver Registry:** Queries `SolverRegistry` to display verified and usable physics modules (e.g. `PointMass3DOFBoostAnalysis`).
* **Execution Parameters Form:** Dynamically renders required solver inputs, initial conditions, and options with SI unit badges.
* **Non-Blocking Execution Console:** Runs execute in asynchronous worker threads. A drawer/modal displays an active progress indicator and a `RichLog` widget streaming live stdout and `FlightLogger` events.

### 4.2 Solver Pipelines & Batch Sweeps
* **Solver Chaining (Pipelines):**
  * Enables chaining computational modules sequentially: output metrics or aero polars from stage $N$ (e.g. aerodynamic coefficients from Barrowman or AVL) pipe directly into initial conditions or lookup tables for stage $N+1$ (e.g. 3DOF trajectory integration).
* **Batch Parameter Sweeps:**
  * Dedicated sweep mode allows selecting an independent variable (e.g. launch angle $\theta \in [45^\circ, 60^\circ, 75^\circ, 85^\circ]$ or motor mass) and running batch executions.
  * Aggregates outputs into combined comparison CSVs and multi-curve plots in `FlightLogs`.

### 4.3 Interactive FlightLogs & Hybrid Figure Viewer
* **Run History Tree:** Tree view organized by `FlightLogs/<vehicle_name>/<analysis_timestamp>/`.
* **Summary Table:** Displays `summary.csv` and `results.json` scalars in an interactive `DataTable` with formatted numbers and units.
* **Execution Log Viewer:** Inspects `execution.log` with syntax highlighting and search filtering.
* **Hybrid Plot & Figure Viewer:**
  * **Inline Thumbnail:** Renders a compact half-block/Unicode terminal preview of generated figures in `figures/*.png`, providing immediate visual feedback on curve shapes directly inside the TUI.
  * **Full Resolution Shortcut:** A prominent button / hotkey (`[O] Open Fullscreen`) spawns the system default image viewer (e.g. `xdg-open`) in the background to inspect high-resolution plots, legends, and axes.

---

## 5. Technical Stack & Widget Mapping

| Functionality | Recommended Textual Primitives / Widgets |
| :--- | :--- |
| Main Navigation | `TabbedContent`, `ContentSwitcher`, `Header`, `Footer` |
| Main Dashboard | `Static`, `Card`, `Label`, `Button`, `ProgressBar` |
| Hangar Browsing | `DataTable`, `ListView`, `ListItem`, `Markdown` |
| Component Palette | `OptionList`, `Tree` |
| Spatial Assembly Bay | Custom `Widget` with mouse drag events (`on_mouse_down`, `on_mouse_move`), `Container` drop zones |
| Component Inspector | `Form`, `Input`, `Label`, `Static`, `Tooltip`, custom `Validator` |
| Run Console | `RichLog`, `ProgressBar`, `LoadingIndicator` |
| FlightLogs History | `Tree`, `DataTable` |
| Plot Display | `Static` (Unicode block rendering / `rich-pixels`), background `subprocess` for system viewer |

---

## 6. Semantic Token Mapping (MELprop Color Specification)

| Token Name | Hex Code | Terminal RGB | Primary UI Role | Usage Context |
| :--- | :--- | :--- | :--- | :--- |
| **`$yaado-background`** | `#0b0f17` | `rgb(11, 15, 23)` | Root canvas | Base screen background behind all cards and sidebars. |
| **`$yaado-surface`** | `#111827` | `rgb(17, 24, 39)` | Primary containers | Sidebar tree, main data viewport, resting panels. |
| **`$yaado-panel`** | `#1b2436` | `rgb(27, 36, 54)` | Elevated cards | Modal dialogue windows, active card containers, popovers. |
| **`$yaado-border-subtle`** | `#25334a` | `rgb(37, 51, 74)` | Structural lines | Panel borders, horizontal table dividers, card boundaries. |
| **`$yaado-border-focus`** | `#3b82f6` | `rgb(59, 130, 246)` | Focus indicators | Active panel outlines and navigation selection highlights. |
| **`$yaado-accent`** | `#f59e0b` | `rgb(245, 158, 11)` | Primary highlight | Active tab underlines, run buttons, cursor row accents. |
| **`$yaado-accent-hover`** | `#d97706` | `rgb(217, 119, 6)` | Action hover state | Hovered primary buttons and interactive trigger targets. |
| **`$yaado-primary`** | `#1d4ed8` | `rgb(29, 78, 216)` | Selection fill | Selected row background in `DataTable`, active item badge. |
| **`$yaado-secondary`** | `#0284c7` | `rgb(2, 132, 199)` | Informational | Engine cycle tags, status badges, secondary links. |
| **`$yaado-success`** | `#10b981` | `rgb(16, 185, 129)` | Convergence indicator | Solver converged, test passed, valid configuration. |
| **`$yaado-warning`** | `#f59e0b` | `rgb(245, 158, 11)` | Boundary advisory | Sub-optimal flow state, iteration limit nearing. |
| **`$yaado-error`** | `#ef4444` | `rgb(239, 68, 68)` | Failure state | Solver divergence, invalid TOML syntax, engine stall. |
| **`$yaado-text`** | `#f8fafc` | `rgb(248, 250, 252)` | Primary data | Numerical values, active inputs, headings, calculated state. |
| **`$yaado-text-muted`** | `#94a3b8` | `rgb(148, 163, 184)` | Descriptive metadata | Units (`kg/s`, `rad`, `Mach`), parameter keys, table headers. |
| **`$yaado-text-disabled`** | `#475569` | `rgb(71, 85, 105)` | Passive elements | Inactive tabs, disabled inputs, log timestamps. |

---

## 7. Crucial Design Directives

### 1. The 5% Amber Rule
`#f59e0b` (Propulsion Amber) has high luminous intensity on a dark background. Restrict it strictly to:
* The active tab bottom border
* Primary execution actions (e.g., `[ Run Analysis ]`)
* Active text cursor / focus ring on data fields
* Elevated warnings in the log

*Do not* use amber for container borders or large panel backgrounds, which degrades the interface into looking like industrial caution signage.

### 2. Tri-Level Luminance Hierarchy
Maintain strict typographic separation to prevent information fatigue:
1. **Values / Results (`#f8fafc`):** Computed Mach numbers, thrust values, and entered parameters receive maximum brightness.
2. **Labels / Identifiers (`#94a3b8`):** Variable names (`T04`, `P_amb`, `S_ref`) and units (`[kN]`, `[Pa]`, `[m²]`) remain in neutral silver slate.
3. **Punctuation / Framing (`#475569`):** Parentheses, timestamps, disabled options, and table grid borders remain muted.

### 3. Non-Invasive Focus Rings
Avoid flashing bright background colors when users navigate across panels. Keep container backgrounds stable at `#111827`, shifting only the surrounding border from `#25334a` to `#3b82f6 60%` on `:focus-within`.