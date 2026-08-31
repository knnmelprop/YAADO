# RFC 0001 — Solid-motor modeling in YAADO

**Status:** Draft / Request for Comments
**Related:** #29 (VehicleFactory), #28 (analysis setup contract), PR #33 (SUAVE integration notes)

> An RFC is a design proposal circulated for team feedback *before* implementation:
> it states the problem, lays out the options with their trade-offs, and gives a
> recommendation. Nothing here is implemented yet — comment and steer.

## 1. Problem

`VehicleFactory` (#29) currently raises `NotImplementedError` when it meets a
`SolidMotor`, because **SUAVE 2.5.2 ships no solid-propellant energy network**
(confirmed against the real package in PR #33: the rocket/high-speed networks are
`Liquid_Rocket`, `Ramjet`, `Scramjet` — there is no `Solid_Rocket`). The question
is how YAADO should let users model solid-fuel motors in their designs.

## 2. Current state — what already works today

Solid motors are **not** unsupported in YAADO; only the SUAVE bridge is missing.

- **Schema — `YAADO_Core/ComponentStore/propulsion.py::SolidMotor`** is complete and
  validated (SI): `isp_vacuum_s`, `isp_sl_s`, `propellant_mass_kg`, `burn_time_s`,
  `thrust_mean_N`, `thrust_peak_N`, `propellant_density_kg_m3`, casing dimensions,
  `mass`. It even carries a cross-check validator (mean thrust vs `Isp·ṁ·g₀`).
- **Solver — `YAADO_Core/modules/flight_dynamics/methods/point_mass_3dof.py::PointMass3DOFBoostAnalysis`**
  (migrated to the #28 contract) already reads a `SolidMotor` from the vehicle
  (`ṁ = propellant_mass_kg / burn_time_s`, thrust from `isp_sl_s·ṁ·g₀`) plus
  body/fins geometry and integrates the boost phase (burnout Mach / altitude /
  q_max / range). This is a real, SUAVE-independent solid-motor performance model.

So the gap is narrow and specific: **translating a `SolidMotor` into SUAVE's
mission solver**, not modeling solid motors as such.

## 3. Options

### Option A — Native YAADO solid-motor analysis (recommended)
Add a first-class `SolidMotorPerformanceAnalysis(BaseAnalysis)` (e.g. under
`YAADO_Core/modules/powerplant/solid_methods/`) that owns the internal-ballistics
side the `SolidMotor` schema already describes:
- **L0/L1:** constant or regressive thrust curve, total impulse `I_t = F̄·t_b`,
  burnout mass, sea-level↔vacuum `Isp` altitude lapse, mass-flow schedule.
- **L1+ (optional, later):** grain-geometry regression (BATES, star), chamber
  pressure from a burn-rate law `r = a·pⁿ`, nozzle expansion.

Pros: fits the architecture (inheritance for solvers), zero SUAVE dependency, no
semantic mismatch. Cons: new code to write and validate against handbook cases.

### Option B — Map `SolidMotor` → SUAVE `Liquid_Rocket`
At the point-mass mission level a rocket network mostly needs thrust / `Isp` / `ṁ(t)`,
all of which a solid provides. `VehicleFactory` could translate `SolidMotor` into a
`Liquid_Rocket` network (populated from the solid's params) with a documented caveat.

Pros: gets solids into SUAVE missions immediately; small change to #29. Cons:
`Liquid_Rocket` ≠ solid physics (feed system, regressive burn, grain) — semantically
misleading; risks users trusting SUAVE outputs that assume liquid behavior.

### Option C — Add a `Solid_Rocket` network to a SUAVE fork
Subclass SUAVE's rocket network with solid burn behavior inside `external/suave`.

Pros: cleanest *within* SUAVE. Cons: `external/suave` is a **pinned submodule** — this
means maintaining a fork, and it violates the project's "don't edit pinned submodules"
rule. Not recommended now.

### Option D — Hybrid staging (complements A)
Use SUAVE where it is strong (airframe aero, cruise mission) and YAADO's native boost
model for the solid stage. This mirrors how a real solid-booster → ramjet-cruise vehicle
is actually staged, and needs no `SolidMotor`→SUAVE translation at all.

## 4. Trade-off summary

| Option | Effort | SUAVE dependency | Physical fidelity for solids | Architectural fit |
|---|---|---|---|---|
| A. Native solver | Medium | none | High (purpose-built) | Excellent |
| B. → Liquid_Rocket | Low | required | Low (liquid proxy) | Poor (semantic) |
| C. Fork SUAVE | High | fork burden | Medium | Violates submodule rule |
| D. Hybrid staging | Low–Med (uses A) | partial | High | Excellent |

## 5. Recommendation

**A + D.** Build the native `SolidMotorPerformanceAnalysis` (the schema and the boost
solver already give it a foundation) and adopt hybrid staging so SUAVE handles the
airframe/cruise while YAADO owns the solid stage. Keep #29's `NotImplementedError` as
an honest boundary marker until/unless Option B is explicitly wanted for a full-SUAVE
mission loop, in which case add it as an opt-in translation with a loud caveat.

## 6. Open questions

- Which fidelity does the first native solver need — a simple constant/regressive
  thrust curve (L0/L1), or grain-regression + chamber pressure (L1+) from day one?
- Should `thrust_peak_N` / a time-resolved thrust curve be schema-owned, or derived?
- Does the team want Option B available at all as a pragmatic SUAVE bridge, or is the
  hybrid boundary preferred permanently?

---
_Generated by [Claude Code](https://claude.ai/code)_
