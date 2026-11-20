# usdsensors

A general library: sensors and sensor rigs as USDA, read into dataclasses (`model`) and
written back (`read`, `write`). `README.md` has what the files are and the schemas.

## Rules

- **General, not any one user's.** Nothing here names an application, a vehicle or a site.
- **Dataclasses in, USDA out, and back.** Read what was written and get what was given:
  every change has a test that writes, reads and compares.
- **USD's and NVIDIA's schemas first** (Camera, OmniLens, OmniSensorAPI, OmniLidar); this
  library's own schemas say only what theirs do not (`schema/schema.usda`).
- **A file is written whole.** No editing a layer in place: build it, export it.
- Comments and docstrings say plainly what the code does, for a reader with only the file.
- Work on a branch; merge to `main` with `--no-ff` when `make` passes. Commit only when asked.

## Commands

```bash
uv sync
make        # lint, format, types, the tests
make fmt
uv run python scripts/check.py   # what `make` runs, without make (Windows)
tools/generate.sh   # after editing schema/schema.usda (bash)
```
