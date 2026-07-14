# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **`biochar-pfas setup` CLI** — merge a pre-built ligand system into a biochar
  structure and build a GROMACS run directory from the command line (wraps
  `setup_pfas_md`), with a repeatable `--place SPECIES:COUNT[:TRY]` placement
  syntax. Previously this half of the workflow was Python-API-only.
- **Worked example** under `examples/pfas_binding/` — a setup-only walk-through
  (README + `build_inputs.py` driver) carrying a structure through
  `build-inputs` → ligand build → `setup` / `setup_pfas_md`.
- **Continuous integration** (`.github/workflows/ci.yml`) running the
  `biochar`-independent test suite on Python 3.9–3.12.
- **Version-drift guard** (`tests/test_version.py`) asserting
  `biochar_pfas.__version__` matches `pyproject.toml`.
- This changelog.

### Notes

- `biochar` needs RDKit and is not on PyPI, so CI installs this package with
  `--no-deps`; the `biochar`-integrated tests skip cleanly (they run locally
  where `biochar` is installed).

## [0.1.0] — unreleased

Initial scaffold and Phase 2 completion (the following are in place but not yet
tagged):

### Added

- PFAS species table (PFOA / PFOS / PFBS deprotonated anions) and LigParGen
  `molecules.txt` + `build_pfas_ligands.sh` rendering.
- Pure-Python biochar + ligand topology merge (`merge_biochar_pfas_topology`).
- `PreSolvationStage` adapter and `setup_pfas_md` orchestration over
  `biochar.md_setup` (setup only — never invokes `gmx`/`ligpargen`).
- `biochar-pfas build-inputs` CLI.
- `biochar` seam contract: `require_biochar_md_setup` + `BiocharSeamError`,
  failing fast with a clear message when the installed `biochar` lacks the
  required `md_setup` symbols.
- Operator runbook (`docs/pfas-workflow-runbook.md`) and test coverage for the
  pure logic, CLI, and seam contract.

[Unreleased]: https://github.com/jolayfield/biochar-pfas/compare/main...HEAD
