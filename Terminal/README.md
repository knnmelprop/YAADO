# Interactive Terminal Interface (TUI) Specification

The YAADO interactive terminal user interface is built on [`textual`](https://textual.textualize.io/) as a modern, high-contrast, keyboard- and mouse-accessible terminal interface. It serves as the primary cockpit for vehicle assembly, solver workflow chaining, and interactive results analysis.

## 1. Design Principles & Architecture

* **Modern TUI Aesthetic:** Clean layouts using crisp terminal borders (`round` or `heavy`), distinct semantic coloring (`$primary`, `$accent`, `$success`, `$error`), and complete support for dark and light terminal themes. Modern UI design principles must be used (such as rounded edges).
* **Decoupled & Data-Driven:** The TUI dynamically reflects Pydantic schemas from [`ComponentStore`](../YAADO_Core/ComponentStore) and solver discovery from [`SolverRegistry`](../YAADO_Core/Foundation/solver_registry.py). It does not hardcode vehicle models or leaf classes.
* **Non-Blocking Async Execution:** All solver routines run in background worker threads (`textual.worker.Worker`), streaming live logs and progress to the UI without freezing user interaction.
* **Three-Tab Stage Structure:**
  1. **Hangar (Vehicle Manager):** Browse, inspect, and manage vehicles and reference configurations.
  2. **Assembly Bay (Vehicle Builder):** Interactive spatial vehicle layout, drag-and-drop sequencing, and schema-driven parameter forms.
  3. **Flight Deck (Analyses & Logs):** Configure solvers, build execution pipelines, run batch sweeps, and inspect historical runs in `FlightLogs`.

## 2. Tab 1: Hangar (Vehicle Manager)

The Hangar tab manages declarative vehicle TOML configurations stored in `Hangar/`.

* **Vehicle Library Browser:**
  * Displays user-created configurations (`Hangar/<name>/`) and pre-built reference vehicles (`Hangar/examples/`).
  * Shows key metadata: vehicle name, description, overall mass properties, and subsystem summaries (bodies, aero surfaces, propulsion).
* **Reference Protection (Forking):**
  * Vehicles in `Hangar/examples/` (such as ALVRJ or AGM-84 Harpoon) are strictly **read-only** templates.
  * Attempting to modify an example opens a **"Fork Vehicle"** prompt, cloning the configuration into a new writable user directory (`Hangar/<new_name>/`).
* **Actions:**
  * `[N] New Vehicle`: Launches the Assembly Bay with a fresh template.
  * `[E] Edit Vehicle`: Loads an existing user configuration into the Assembly Bay.
  * `[C] Fork / Clone`: Duplicates any selected vehicle to a new target name.
  * `[D] Delete / Archive`: Safely removes user configurations.
Actions should also be available as clickable buttons. 

## 3. Tab 2: Assembly Bay (Vehicle Builder)

The Assembly Bay coordinates Lego-like component composition into a validated `BaseVehicleConfig`.

### 3.1 Spatial Orientation & Layout Canvas
Spatial positioning along the longitudinal ($x$) axis is critical in aerospace design (nose $\to$ forward body $\to$ wings $\to$ aft body $\to$ fins $\to$ propulsion):
* **Component Palette:** Categorized drawer on the side listing components dynamically discovered from `ComponentStore` (`bodies`, `aero_surfaces`, `propulsion`, `mass_properties`).
* **Visual Longitudinal Axis (Assembly Canvas):**
  * An interactive track or schematic diagram representing the vehicle from nose to tail with positional snap zones (Nose, Forward, Mid, Aft, Base).
  * Components can be dragged from the palette and dropped into spatial zones, or re-ordered along the longitudinal axis via drag or keyboard shortcuts.
* **Unique Component Naming:**
  * When components are dropped onto the canvas, the TUI auto-generates descriptive, globally unique tags (e.g. `main_body`, `aft_fins`, `solid_booster_1`) to satisfy `BaseVehicleConfig` namespace validation. Tags remain user-editable in the inspector.

### 3.2 Dynamic Component Inspector & Form
Selecting any placed component opens its parameter inspector in the side panel:
* **Schema-Driven Inputs:** Fields, types, constraints, and tooltips are generated directly from Pydantic `model_fields`.
* **SI Unit Badges:** Every field displays its canonical SI unit (retrieved from `UNITS: ClassVar[dict[str, str]]`).
* **Field Descriptions:** Contextual tooltips sourced dynamically from `field_info.description`.
* **Reactive Validation States:**
  * Outline turns green (`border: tall $success`) when the user enters a value that satisfies schema constraints (`gt`, `le`, etc.).
  * Outline turns red with an inline error hint when input fails validation.
* **Baseline Prefill Support:**
  * **Per-Field Fallback:** Pressing a shortcut (e.g. `F2` or `Tab`) populates the field with its mandatory baseline schema example (`field_info.examples[0]`).
  * **Component Baseline:** A one-click "Fill Baseline Examples" button pre-populates all parameters with standard reference values (leveraging `VehicleTemplateGenerator.prefill_component_values`).

### 3.3 Draft Persistence vs. Canonical TOML
* **Auto-Saving Drafts:** While editing or assembling, intermediate state is saved to `Hangar/<name>/.draft.toml` after every component modification, ensuring work is never lost even if incomplete.
* **Final Validation & Serialization:** The canonical `Hangar/<name>/<name>.toml` is generated only when the user clicks **"Finalize / Save Vehicle"**, executing strict validation through `BaseVehicleConfig.model_validate()`.

---

## 4. Tab 3: Flight Deck (Analyses, Pipelines & FlightLogs)

The Flight Deck coordinates physics solver runs and serves as an interactive viewer for `FlightLogs`.

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

## 5. Technical Stack & Widget Mapping

| Functionality | Recommended Textual Primitives / Widgets |
| :--- | :--- |
| Main Navigation | `TabbedContent`, `ContentSwitcher`, `Header`, `Footer` |
| Hangar Browsing | `DataTable`, `ListView`, `ListItem`, `Markdown` |
| Component Palette | `OptionList`, `Tree` |
| Spatial Assembly Bay | Custom `Widget` with mouse drag events (`on_mouse_down`, `on_mouse_move`), `Container` drop zones |
| Component Inspector | `Form`, `Input`, `Label`, `Static`, `Tooltip`, custom `Validator` |
| Run Console | `RichLog`, `ProgressBar`, `LoadingIndicator` |
| FlightLogs History | `Tree`, `DataTable` |
| Plot Display | `Static` (Unicode block rendering / `rich-pixels`), background `subprocess` for system viewer |