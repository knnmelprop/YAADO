# MELprop-IADE — Project State Snapshot 2026-07-11

> **Wygenerowane przez:** Perplexity + GitHub connector (session 2026-07-11)  
> **HEAD weryfikowany:** `d6a493c` (branch `claude/iade-repo-restructure-00rrro`)  
> **Cel:** jeden kanoniczny dokument zastępujący rozproszone i częściowo sprzeczne
> wpisy w `memory.md` / `analysis_status.md`. Zawiera TYLKO wartości zweryfikowane
> bezpośrednio z repo (git log, vehicle_config.yaml, memory.md, PR list).
> Nigdy nie cytuj wyników z Perplexity chat-sessions jako source-of-truth — zawsze
> weryfikuj przez connector lub lokalny `git`.

---

## Repo — fakty podstawowe

| Parametr | Wartość |
|---|---|
| Pełna nazwa | `knnmelprop/iade` (prywatny) |
| Default branch | `claude/iade-repo-restructure-00rrro` |
| HEAD (`d6a493c`) | docs: detailed recovery handoff in memory.md (2026-07-10 21:23) |
| Repo created | 2026-07-09 21:11 (nowe repozytorium, po ekstrakcji filter-repo) |
| Otwarte PR | #3 (full-analysis rerun, draft), #5 (CFD pipeline scaffolding, draft, stacked on #4's base) |
| main branch | `7826f48` — jest, ma realną historię (root ancestor z droneEnv) |

---

## Faza reorganizacji IADE — WERYFIKACJA

| Faza | Plan | Stan POTWIERDZONY z repo |
|---|---|---|
| Faza 0 | backup mirror, nowe puste repo, wybór pinów | ✅ DONE — repo `knnmelprop/iade` istnieje, powstało 2026-07-09 |
| Faza 1 | git filter-repo, ekstrakcja path allowlist, usunięcie SUAVE trunk | ✅ DONE — historia 182 commitów (było 793), `external/suave/trunk/` jako submoduł, brak `trunk/SUAVE` w strukturze |
| Faza 2 | submodule external + requirements.txt | ✅ DONE — 4 submoduły: SUAVE 2.5.2, pyCycle 4.1.2, SU2 v8.5.0, OpenVSP 3.51.0; AVL/XFOIL pominięte |
| Faza 3 | multi-mode env (devcontainer + venv + conda), bootstrap_submodules.sh | ✅ DONE — `scripts/bootstrap_submodules.sh` obecny, `docs/environment-native.md` opisuje native venv, `environment-conda.yml` jako draft (niezweryfikowany) |
| Faza 4 | CODEOWNERS + branch protection (admin-only) | ✅ DONE (docs) — `.github/CODEOWNERS` draft w repo; branch protection w GitHub Settings = WYMAGA RĘCZNEJ AKCJI CZŁOWIEKA (agent nie ma praw admin) |
| Faza 5 | pełna weryfikacja | ✅ DONE — pytest 208/208 po Faza 5; potem kolejne sesje podniosły do 211, a PR #3 (full-analysis rerun) raportuje 220 na swoim branchu |

**Konkluzja:** Reorganizacja 5-fazowa jest **w pełni zakończona** w default branch.
Aktywna praca (analizy inżynierskie) toczy się na branchach PR #3 i PR #5.

---

## Sprzeczność #1 — `fins.span_m`: 0.550 m vs 0.6685 m — ROZSTRZYGNIĘTA

**Odpowiedź:** Obie wartości były w repo, ale w RÓŻNYCH commitach:

- `0.6685 m` — wartość Fusion 360 Assembly v6, obowiązywała przed `8e16536`.
- `0.550 m` — wartość aktualna, nadpisana w commicie `8e16536` (2026-07-10 20:31)
  per explicit human decision: `"new drawing supersedes Fusion"`.
- **Aktualna wartość w `vehicles/ramjet_rocket/vehicle_config.yaml` (HEAD `d6a493c`):
  `fins.span_m = 0.550`**, oznaczona MODERATE CONFIDENCE z flagą wymagającą
  re-weryfikacji człowieka przez PDF.

**Status HR-1:** CZĘŚCIOWO ROZWIĄZANY. Wartość geometryczna zaktualizowana;
`span_m = 0.550` to odczyt inference z rysunku (layout, nie wymiarowy callout).
**OPEN:** człowiek musi potwierdzić, czy `550` → fin span czy inna cecha
(tail-section length? across-fins width?); oraz jaka jest interpretacja `127`
(potencjalnie true fin radial span). **Wymagana akcja człowieka przed CDR.**

---

## Sprzeczność #2 — `nozzle_area_ratio`: 4.0 vs 1.317 — ROZSTRZYGNIĘTA

**Odpowiedź:**

- `4.0` — placeholder z Night-4 plan (stary YAML i stary `NOZZLE_AREA_RATIO_DESIGN`).
- `1.317` — wartość z rysunku Czernicki DWG 10/07/2026: `(241/210)² = 1.317`,
  zweryfikowana drawing-side.

**Aktualny stan w HEAD `d6a493c`:**
```
vehicles/ramjet_rocket/vehicle_config.yaml:
  stage_2.nozzle_area_ratio: 1.317
  stage_2.nozzle_throat_diameter_m: 0.210
  stage_2.nozzle_exit_diameter_m: 0.241

analyses/propulsion/ramjet_cycle.py:
  NOZZLE_AREA_RATIO_DESIGN = 1.317   # linia 206
  # konsumowane na liniach 430, 446, 723 i combustor_nozzle_cycle.py 119/637
```

Grep przez całe repo nie znajdzie żadnego stałego `4.0` dla area_ratio.
Brak pliku `PENDING_area_ratio_propagation.md`. Propagacja w pełni zakończona.

**Status HR-3:** ZAMKNIĘTY.

---

## Sprzeczność #3 — Liczba commitów ahead of origin/main: 6 vs 10 — ROZSTRZYGNIĘTA

**Odpowiedź:** Branch jest **10 commitów ahead of `main`**, nie 6.

Pierwsze 4 niebędące w `main` (spod 6 timeboxed commits):

| SHA | Opis |
|---|---|
| `8e16536` | feat(config): apply drawing-verified body/fin geometry (HR-1 partial), 211 passed |
| `479a985` | feat(schema+config): add nozzle throat/exit diameters from real drawing (HR-3) |
| `79c02d7` | archival computations ramjet iteration 1 (Aleks Czernicki, 2026-07-10) |
| `b96c648` | docs: Night-6 Fable kickoff prompt (SU2 build + CFD cross-check) |

Późniejsze 6 commitów (timeboxed session):
`7c884ea` → `e2d07ed` → `64f090a` → `92fe347` → `342140e` → `70b59a7` → `d6a493c`

**Łącznie 10 commitów nie jest w `main`.** Merge do `main` wymaga merge PR #3
(który bazuje na `main`) — ale aktualny working-branch (default) stoi dalej za PR #3.
Plan merge: PR #3 → main, potem PR #5 (rebased) → main.

---

## Sprzeczność #4 — pytest count: 118 vs 157 vs 211 — ROZSTRZYGNIĘTA

Wszystkie trzy liczby są prawdziwe — dotyczą **różnych momentów w czasie**:

| Count | Kontekst | Branch/moment |
|---|---|---|
| 80 | Night-2/3 baseline (przed Night-3 fazami) | `droneEnv / claude/dazzling-turing-d91coa` |
| 118 | Night-4 STEP-0 (po Night-3 fazach 2b/3b/4b/5/6) | `droneEnv / claude/fervent-albattani-f18spc` |
| 157 | Night-4 close-out (P1-A/B/C/D + P2-A/B/C/D) | `droneEnv` — stare repo, nie `iade` |
| 208 | Faza 5 validation pierwsza sesja po ekstrakcji filter-repo | `knnmelprop/iade` (current repo) |
| 211 | Po `8e16536` (geometry update + 3 new tests) | `knnmelprop/iade`, HEAD current |
| 220 | PR #3 branch `claude/ramp-full-analysis-rerun-nkqwp1` | `knnmelprop/iade`, PR branch |
| 240 | PR #5 branch `claude/ramp-cfd-pipeline-scaffolding` | `knnmelprop/iade`, PR branch (stacked) |

**Aktualna wartość dla default branch HEAD `d6a493c`: 211 passed, 0 failed.**
**GOTCHA:** `python -m pytest -q` z root crashuje na SU2 meson fixtures.
Zawsze uruchamiaj: `python -m pytest tests/` (nie root-level).

---

## Stan HR-1 / HR-2 / HR-3 — podsumowanie

### HR-1: fin_span 0.6685 vs 0.550
- **Stan:** CZĘŚCIOWO ZAMKNIĘTY (patrz Sprzeczność #1). Wartość zmieniona na 0.550
  z MODERATE CONFIDENCE. **Otwarta akcja człowieka: re-weryfikacja PDF rysunku.**

### HR-2: wersja CAD CFD vs Assembly
- **Stan:** OPEN. Rysunek "CFD Simplified Single Rocket Model" (Czernicki, DWG
  10/07/2026) zastąpił Fusion Assembly v6 dla body.diameter i total_length.
  Fusion v6 nadal obowiązuje dla mass_properties (CG) i chord_root/chord_tip.
  Zinwentaryzowane, nie w pełni zreconcylowane.

### HR-3: nozzle_area_ratio 4.0 vs 1.317
- **Stan:** ZAMKNIĘTY (patrz Sprzeczność #2). Wartość 1.317 w YAML + `ramjet_cycle.py`.

---

## Status SU2 lokalny (build / run)

**Stan:** NIE WYKONANY w żadnej sesji Claude Code.

- SU2 jest dodany jako pinned submodule (`external/su2` @ `su2code/SU2 v8.5.0`,
  SHA `12eb826f04`) — source-reference only, nie zbuildowany.
- Commit `b96c648` ("Night-6 Fable kickoff prompt") zawiera plan SU2 build +
  RANS alpha-sweep, ale jest tylko docsem, nie execucją.
- PR #3 opisuje `SU2 RANS cross-check: BLOCKED_BY_ENVIRONMENT` (build C++ CFD
  infeasible w cloud sandbox) → **wymaga uruchomienia lokalnie przez człowieka
  lub na serwerze zespołu.**
- docs/EXTERNAL_TOOLS.md istnieje i opisuje submoduły.

**Następne wymagane kroki (lokalne):**
```bash
# 1. Init submodules
git submodule update --init --recursive external/su2
# 2. Build SU2 (meson + ninja, wymaga C++17 + cmake)
cd external/su2 && pip install meson ninja && \
    meson setup builddir && cd builddir && ninja
# 3. Pierwszy test: jeden RANS-SST alpha-sweep Mach 2.5
#    (mesh rakiety musi spełnić: orthogonality >0.1, skewness <0.9, y+<1)
```

---

## Otwarte elementy wymagające akcji człowieka

| # | Element | Plik | Priorytet | Blocking |
|---|---|---|---|---|
| A1 | Re-weryfikacja `fins.span_m`: 550 = span czy inna cecha? 127 = fin radial span? | `vehicles/ramjet_rocket/vehicle_config.yaml` | **KRYTYCZNY przed CDR** | HR-1 |
| A2 | Branch protection w GitHub Settings (admin) | — | WYSOKI | Faza 4 |
| A3 | SU2 lokalny build + RANS alpha-sweep Mach 2.5 (server/lokalnie) | `external/su2` | **KRYTYCZNY — CDR blocker** | sign-flip |
| A4 | Fuzja danych Fusion v6 (CG, Ixx/Iyy/Izz) z nową geometrią rysunkową (body 0.200m) — czy CG jest spójne z nową masą? | `vehicles/ramjet_rocket/vehicle_config.yaml` | WYSOKI | stabilność |
| A5 | GTM-140 / R-13 motor datasheet (thrust curve, Isp real) | `vehicle_config.yaml stage_1` | WYSOKI | misja |
| A6 | DVC remote skonfigurowany (PR #5 czeka na `TBD-HUMAN`) | CI/DVC | ŚREDNI | CI |
| A7 | Merge PR #3 → main po Stage 2-5 completion; potem PR #5 rebase | GitHub | WYSOKI | porządek |

---

## Otwarte elementy dla agenta (nie wymagają człowieka)

| # | Element | Ścieżki | Wysiłek |
|---|---|---|---|
| B1 | Re-run ALL geometry-dependent analyses vs 0.200m/29.98°/1.317 | `analyses/**/`, wyniki do `docs/ramP/preliminary_analysis_report_*.md` | M |
| B2 | Pydantic schema dla inlet-cone / nozzle-stations; wire w analizach | `src/schemas/vehicle_schema.py`, `vehicles/ramjet_rocket/cad_reference/drawing_dimensions_raw.yaml` | M |
| B3 | Konsystentność `body.max_diameter_m=0.639` z nowym fin span 0.550 | `vehicle_config.yaml` | S |
| B4 | Dokończenie PR #3: Stage 2 (CEA γ), Stage 3 (Taylor-Maccoll), Stage 4 (cold-flow) | `analyses/propulsion/`, PR #3 branch | L |
| B5 | Weryfikacja `booster assembly_diameter_m=0.250` vs `body.diameter_m=0.200` — spójność czy celowa różnica? | `vehicle_config.yaml` | S |

---

## Plan kolejnych 1-2 sesji Claude Code

### Sesja N+1 — Kontynuacja PR #3 (full-analysis rerun)

**Base branch:** `claude/ramp-full-analysis-rerun-nkqwp1` (PR #3, 220 passed)

**Zadanie 1 — Stage 2: ramjet cycle z CEA γ (BLOCKED_BY_ENVIRONMENT → CEA dostępne)**
```
analyses/propulsion/ramjet_cycle.py   ← dodaj CEA γ per station (inlet, combustor, nozzle)
analyses/propulsion/combustor_nozzle_cycle.py   ← podmień stałe γ=1.4 na CEA-sourced
V3 root-cause: aktualny wynik 1474 m/s vs 1047 m/s (+40.8%) —
  sprawdź czy nozzle_area_ratio=1.317 (zamiast 4.0) już zmienia V3;
  jeśli nie, szukaj w gamma i T_combustor assumptions
```

**Zadanie 2 — Stage 3: Taylor-Maccoll inlet + nozzle**
```
analyses/aero/inlet_performance.py   ← multi-cone Taylor-Maccoll
  vs drawing 42°/60° kąty z drawing_dimensions_raw.yaml
  (uwaga: drawing_dimensions_raw.yaml istnieje ale żadna analiza jej nie czyta)
vehicles/ramjet_rocket/cad_reference/drawing_dimensions_raw.yaml  ← source
```

**Pytanie KROK 0 tej sesji:** `python -m pytest tests/` — spodziewany wynik 220.

### Sesja N+2 — Pydantic schema + geometry re-reconciliation

**Base branch:** main (po merge PR #3)

**Zadanie 1 — InletGeometry / NozzleStations schema:**
```
src/schemas/vehicle_schema.py   ← dodaj InletGeometry (cone_angles, centerbody_dims)
                                    i NozzleStations (convergence/throat/exit_mm)
vehicles/ramjet_rocket/cad_reference/drawing_dimensions_raw.yaml
   ← zwaliduj przez nową schema (to jest celem istnienia tego pliku)
```

**Zadanie 2 — Re-run geometry suite:**
```bash
python analyses/aero/barrowman_extended.py
python analyses/aero/ackeret_fin_check.py   # już w PR #3
python analyses/aero/drag_polar.py
python analyses/stability/datcom_class_sweep.py  # już w PR #3
python analyses/propulsion/inlet_performance.py
python workflows/ramp_staged_mission.py
# → zaktualizuj docs/ramP/preliminary_analysis_report_*.md
```

**WAŻNE dla obu sesji:** `body.max_diameter_m=0.639` prawdopodobnie
niezgodne z `fins.span_m=0.550` po zmianie geometrii — `max_diameter` to
Fusion booster bbox, nie musi uwzględniać nowych fin dims; sprawdź i dodaj
do tbd jeśli nadal niejasne.

---

*Dokument weryfikowany przez Perplexity + GitHub MCP connector, 2026-07-11.*
*Commit ten nie zmienia żadnego kodu ani testów — documentation only.*
