# MELprop-IADE — Integrated Aircraft Design Environment

Projekt Koła Naukowego **KNN MELprop** (Politechnika Warszawska).
Repo bazuje na forku **SUAVE** (kod SUAVE jako git submodule w `external/suave/trunk/SUAVE/`, pin 2.5.2 — NIE modyfikuj go).

> 🧭 **Nowa sesja agenta?** Przeczytaj najpierw [`docs/AGENT_CONTEXT.md`](docs/AGENT_CONTEXT.md)
> — pełny handoff: stan repo, setup zależności, jak uruchamiać analizy, wykonana
> praca, znane problemy i następne kroki. Live tracker: [`docs/ramP/analysis_status.md`](docs/ramP/analysis_status.md).

## Architektura

```
core/                    # Fundament — rozszerzaj przez dziedziczenie, NIE przepisuj
  component_base.py      #   BaseComponent, BaseAnalysis, FidelityLevel (L0–L3),
                         #   AnalysisResults, ComponentRegistry
  vehicle_factory.py     #   Fabryka pojazdów SUAVE (buildery per vehicle_type)
  mission_builder.py     #   Builder segmentów misji (solver-agnostic)
  solver_registry.py     #   Rejestr solverów zewnętrznych (AVL, XFOIL, ...)
src/schemas/             # Pydantic v2 schemas konfiguracji pojazdów
vehicles/                # Konfiguracje YAML pojazdów (gtm140_drone/, ramjet_rocket/)
analyses/aerodynamics/   # AVL wrapper, XFOIL, empiryczna aero rakiety
analyses/propulsion/     # pyCycle (ramjet), solid rocket, GTM-140 performance map
workflows/               # OpenMDAO Problems, MDO, staging events
tests/unit/              # pytest
.claude/agents/          # Definicje subagentów (aero-analyst, propulsion-designer, ...)
```

## Dwa projekty

### Projekt A — Dron z silnikiem GTM-140
- Silnik: Jetpol GTM-140 — polska miniaturowa **turbina odrzutowa** (turbojet,
  NIE turbofan — brak śmigła).
- Aerodynamika: skrzydło stałe, subsonic, VLM (AVL); profile: XFOIL (niski Re).
- Config: `vehicles/gtm140_drone/vehicle_config.yaml`.

### Projekt B — Dwustopniowa rakieta z ramjetem
- Stopień 1: poradziecki silnik rakietowy na paliwo stałe (booster).
- Stopień 2: ramjet własnego projektu, docelowo Mach 2–3.
- Aerodynamika: body-of-revolution + płetwy, korelacje empiryczne
  (DATCOM-style). **NIE używaj AVL dla części naddźwiękowej.**
- Staging event: ramjet przejmuje napęd po burnout stopnia 1.
- Config: `vehicles/ramjet_rocket/vehicle_config.yaml`.

## Reguły projektu (obowiązkowe)

1. **Jednostki SI zawsze.** Nazwy pól z sufiksem jednostki (`thrust_N`,
   `span_m`, `isp_s`). Używaj `openmdao.utils.units` lub Pint gdzie możliwe.
2. **Type hints** na wszystkich funkcjach publicznych.
3. **Docstringi Google-style** (po angielsku) dla każdej klasy i metody publicznej.
4. Każdy nowy plik zaczyna się od: `# MELprop-IADE | [nazwa modułu] | v0.1.0`.
5. NIE commituj sekretów, tokenów, haseł. Plik `.env` (jeśli istnieje) — ignoruj.
6. NIE przepisuj kodu z `core/` — rozszerzaj przez dziedziczenie.
7. Ograniczenia metod: AVL tylko dla Ma < 0.6 i alpha < 15°; powyżej —
   korelacje empiryczne.
8. Po każdej zmianie: `python -m pytest tests/ -v --tb=short`.
9. Wartości oznaczone `# TBD` w YAML to placeholdery — wymagają rzeczywistych
   danych (datasheet GTM-140, dokumentacja silnika rakietowego) przed analizami.

## Subagenci (`.claude/agents/`)

| Agent | Model | Zakres plików |
|---|---|---|
| aero-analyst | claude-sonnet-4-5 | `analyses/aerodynamics/`, `tests/test_aero_*.py` |
| propulsion-designer | claude-opus-4-5 | `analyses/propulsion/`, `tests/test_propulsion_*.py` |
| vehicle-builder | claude-sonnet-4-5 | `src/schemas/`, `vehicles/**`, `tests/test_vehicles_*.py` |
| mission-planner | claude-sonnet-4-5 | `workflows/`, `tests/test_missions_*.py` |
| code-reviewer | claude-haiku-4-5 | read-only wszystko, write tylko `tests/` |
| docs-writer | claude-haiku-4-5 | `notebooks/`, `*.md` |

## Uruchamianie testów

```bash
python -m pytest tests/ -v --tb=short
```

Zależności dev: `pydantic>=2`, `pyyaml`, `pytest`. SUAVE (submodule w `external/suave/`) jest
opcjonalne dla testów jednostkowych — importy SUAVE w `core/` są osłonięte
(guarded) i moduły działają bez niego.
