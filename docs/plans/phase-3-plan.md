---
title: "Phase 3 plan — biochar-pfas operator ergonomics and release readiness"
status: draft
created: 2026-07-14
updated: 2026-07-14
---

# Phase 3 plan — biochar-pfas operator ergonomics and release readiness

## Problem frame

Phase 2 finished the scaffold and closed its three post-scaffold gaps: CLI test
coverage, an operator runbook, and the `biochar` seam contract (documented plus
a runtime fail-fast). See `docs/plans/phase-2-plan.md` and PR #1.

What remains is not new architecture. The package works end to end through its
Python API, but two things keep it from being comfortably reusable by someone
other than its author: the full setup path (merge + run-directory build) is
Python-API-only, and there is no continuous verification, no worked example, and
no cut release. Phase 3 is about making the package *operable and shippable* —
closing the API/CLI parity gap, proving the whole flow with a runnable
(setup-only) example, and getting to a tagged `v0.1.0` behind green CI.

## Scope

In scope:

- CLI parity with the Python API for the setup/merge path
- a top-level, end-to-end worked example (setup-only)
- continuous integration for the `biochar`-independent test suite
- release hygiene: changelog, version single-sourcing, and a go/no-go on `v0.1.0`

Out of scope (unchanged standing constraint — **setup only, never execute**):

- running `ligpargen`, `build_gromacs_system.py`, or `gmx`
- cluster execution or SLURM/scheduler integration
- scientific validation of PFAS sorption outcomes
- the mu3c `scratch_root` configuration fix (execution-time concern; see
  "Explicitly deferred")

## Current status

Phase 2 is complete (PR #1). Baseline relevant to Phase 3:

- `biochar_pfas/cli.py` exposes exactly one subcommand, `build-inputs`. The
  merge + run-directory build (`setup_pfas_md`) has no CLI surface.
- `examples/` contains only `pfas_temperature_grid.yaml` — the *structure
  generation* input (consumed by `biochar-sweep`, upstream). There is no example
  that carries a structure through `build-inputs` → merge → `setup_pfas_md`.
- No `.github/workflows/` (no CI). No `CHANGELOG.md`.
- `pyproject.toml` declares `version = "0.1.0"` and `biochar_pfas/__init__.py`
  independently declares `__version__ = "0.1.0"` (two sources, kept in sync by
  hand).
- Test suite: 27 passed, 2 skipped (the 2 skips are the `biochar`-dependent
  orchestrate/adapter tests; `biochar` needs RDKit and is not on PyPI).

## Work items

### 1. CLI parity: expose the setup path

Today an operator can render LigParGen inputs from the shell but must drop into
Python to merge a ligand system and build a run directory. Add a `setup`
subcommand that wraps `setup_pfas_md`, so the whole workflow is drivable from the
CLI.

Implementation units:

- `biochar_pfas/cli.py`
  - new `setup` subparser + `_setup(args)` handler
  - a small pure `parse_placement(token)` helper (its own function, so it is
    unit-testable without `biochar`)
- `tests/test_cli.py` (extend)

Decisions:

- **Placement syntax:** repeatable `--place SPECIES:COUNT[:TRY]`, e.g.
  `--place PFOA:4 --place PFOS:2:250`. `COUNT` defaults are not allowed to be
  omitted (a copy count is a deliberate per-run choice); `TRY` defaults to the
  `LigandPlacement` default (500). Parse into `list[LigandPlacement]`.
- **Required flags:** `--gro`, `--top`, `--ligand-system-dir`, `--output-dir`,
  and at least one `--place`.
- **Optional flags:** `--label`, `--ion-profile` (threaded into `MDSetupConfig`),
  `--cluster`.
- **Fail-fast:** the handler calls into `setup_pfas_md`, which already routes
  through `require_biochar_md_setup()`; a missing/old `biochar` therefore
  surfaces as the same clear `BiocharSeamError` rather than a raw traceback.
- Keep `build-inputs` unchanged.

Test scenarios:

- `parse_placement` accepts `PFOA:4` → `LigandPlacement("PFOA", 4)` and
  `PFOA:4:250` → `LigandPlacement("PFOA", 4, insertion_try=250)`.
- `parse_placement` rejects `PFOA`, `PFOA:0`, `PFOA:x`, and extra fields with a
  clear failure.
- `setup` with no `--place` exits with a clear failure.
- an unknown species in `--place` produces the same clean error as
  `build-inputs`.
- end-to-end (`importorskip biochar`, mirroring `tests/test_orchestrate.py`):
  `setup` writes `merged.top` + `run_pipeline.sh` into `--output-dir`.

### 2. A top-level worked example (setup-only)

There is no single artifact that shows the whole flow. Add one, wired to the
existing structure-generation example so the two halves connect.

Implementation units:

- new `examples/pfas_binding/README.md` — the end-to-end narrative
- new `examples/pfas_binding/build_inputs.py` (or a documented CLI command
  sequence) that renders `molecules.txt` + `build_pfas_ligands.sh` for
  PFOA/PFOS/PFBS
- pointer from the example to `examples/pfas_temperature_grid.yaml` as the
  structure source and to `docs/pfas-workflow-runbook.md` for the cluster
  handoff
- `tests/test_examples.py` (new, smoke-level)

Decisions:

- The example **renders and documents**; it does not execute. The cluster build
  (step 2 of the workflow) and the MD run (step 5) stay manual, per the standing
  constraint.
- Prefer committing a small **driver script** over committing rendered artifacts,
  so the example stays honest if the species table or script format changes.
- Show a representative setup matrix (e.g. 3 species × a couple of biochar
  structures × one ion profile) as documentation, not as generated run
  directories.

Test scenarios:

- the example driver renders `molecules.txt` + `build_pfas_ligands.sh` to a temp
  dir (no `biochar` needed for this half).
- the rendered `molecules.txt` lists all three species; the build script
  mentions `build_gromacs_system.py` and `BOSSdir`.

### 3. Release readiness: CI, changelog, versioning, tag

Lock in the value already delivered and get to a tagged initial release.

Implementation units:

- new `.github/workflows/ci.yml`
- new `CHANGELOG.md`
- `pyproject.toml` and/or `biochar_pfas/__init__.py` (version single-sourcing)

Decisions:

- **CI cannot install `biochar`** from PyPI (it is a GitHub-hosted package that
  needs RDKit). CI therefore installs this package *without resolving that
  dependency* (e.g. `pip install pytest && pip install -e . --no-deps`) and runs
  the suite; the 2 `biochar`-dependent tests skip cleanly via their existing
  `importorskip`. Document this explicitly in the workflow — the pure-logic, CLI,
  and contract tests (the bulk of coverage) run on every push; the
  `biochar`-integrated paths remain covered locally where `biochar` is installed.
- **Python matrix:** 3.9–3.12 (matching `requires-python = ">=3.9"`).
- **Versioning:** single-source the version — either derive `__version__` from
  package metadata, or add a test asserting the two declarations agree — so a
  release bump can't drift.
- **Changelog:** start a Keep-a-Changelog `CHANGELOG.md` and record the Phase 2
  + Phase 3 work under an `Unreleased` → `0.1.0` heading.
- **Tag decision (phase-2 sequencing step 5):** cut `v0.1.0` once CI is green and
  the example lands — or record an explicit reason to hold. This is the go/no-go,
  not open-ended work.

Test scenarios:

- a version-agreement test (if the two declarations are kept rather than
  single-sourced).
- CI green on the `biochar`-independent suite across the Python matrix.

## Sequencing

1. **CI** — smallest, lowest-risk slice; makes the already-green suite durable
   before more code lands on top of it.
2. **CLI parity** — the most operator-visible gap; covered by the new CI.
3. **Worked example** — depends on the CLI `setup` command reading well.
4. **Changelog + `v0.1.0` go/no-go** — the closing decision.

## Recommended next implementation slice

Start with CI:

1. add `.github/workflows/ci.yml` running the `biochar`-independent suite on
   Python 3.9–3.12
2. confirm it is green (27 passed / 2 skipped, or equivalent)

It is small, self-contained, protects everything Phase 2 delivered, and turns
"green on my machine" into "green on every push" before the CLI-parity and
example slices build on it.

## Explicitly deferred (standing constraint)

These stay out of scope while the package is setup-only, and would each require a
deliberate decision to relax the constraint:

- executing `ligpargen` / `build_gromacs_system.py` / `gmx`
- SLURM submission or any scheduler integration
- scientific validation of sorption outcomes
- the mu3c `scratch_root` misconfiguration (`/scratch/layfield` likely wants to
  be `/home0/layfield` or `/extra0/layfield`) — an execution-time config issue
  that only matters once a run is actually launched by hand.

## Definition of done for this plan

Phase 3 is complete when:

- the full setup path (merge + run-directory build) is drivable from the
  `biochar-pfas` CLI, with tests
- a runnable, setup-only worked example carries a structure through the whole
  flow and is smoke-tested
- CI runs the `biochar`-independent suite on every push, green
- a `CHANGELOG.md` exists and the version is single-sourced (or agreement-tested)
- `v0.1.0` is tagged, or there is a recorded, explicit reason to hold
