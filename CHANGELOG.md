# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] — 2026-07-14

Initial release: a setup-only PFAS-sorption MD-setup workflow on top of the
independent `biochar` (biochar-simulator) tool. Everything writes files; nothing
invokes `ligpargen`/`gmx` or submits a cluster job.

### Added

- PFAS species table (PFOA / PFOS / PFBS, deprotonated anions, CM1A) and
  LigParGen `molecules.txt` + `build_pfas_ligands.sh` rendering.
- Pure-Python biochar + ligand topology merge (`merge_biochar_pfas_topology`).
- `PreSolvationStage` adapter and `setup_pfas_md` orchestration over
  `biochar.md_setup`.
- `biochar-pfas` CLI with two subcommands: `build-inputs` (render LigParGen
  inputs) and `setup` (build a run directory, with a repeatable
  `--place SPECIES:COUNT[:TRY]` placement syntax).
- `biochar` seam contract: `require_biochar_md_setup` + `BiocharSeamError`,
  failing fast with a clear message when the installed `biochar` lacks the
  required `md_setup` symbols.
- Worked example under `examples/pfas_binding/` (setup-only).
- Documentation: operator runbook (`docs/pfas-workflow-runbook.md`) and usage
  guide (`docs/usage.md`).
- Continuous integration (`.github/workflows/ci.yml`) running the
  `biochar`-independent suite on Python 3.9–3.12.
- Test coverage for the pure logic, CLI, seam contract, worked example, and
  version drift.

### Notes

- `biochar` needs RDKit and is not on PyPI, so CI installs this package with
  `--no-deps`; the `biochar`-integrated tests skip cleanly in CI and run locally
  where `biochar` is installed.

[Unreleased]: https://github.com/jolayfield/biochar-pfas/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/jolayfield/biochar-pfas/releases/tag/v0.1.0
