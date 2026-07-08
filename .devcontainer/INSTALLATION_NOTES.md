# SUAVE Installation Notes for Codespaces

## Current Approach (August 2025)

- Base image: devcontainers Python 3.9
- Dependencies: Installed globally from `.devcontainer/requirements.txt`
- Git LFS initialized on container create
- SUAVE installed in editable mode via `cd trunk && python3.9 setup.py develop`

## Why this works

- Avoids pip build isolation issues by invoking `setup.py develop` directly
- Global dependency install ensures both runtime and setup have consistent env

## Verification

```bash
python3.9 -c "import SUAVE, numpy, scipy, matplotlib, sklearn, plotly; print('✓ SUAVE + deps OK')"
```

## Troubleshooting

- Rebuild the container if imports fail: Codespaces Command Palette → Rebuild Container
- Ensure `.devcontainer/requirements.txt` and `setup.py develop` completed in post-create logs
