---
title: "Phase 2 plan — biochar-pfas scaffold completion and next steps"
status: active
created: 2026-07-12
updated: 2026-07-12
---

# Phase 2 plan — biochar-pfas scaffold completion and next steps

## Problem frame

`biochar-pfas` exists to keep PFAS-specific MD setup logic out of the generic `biochar` package while still reusing `biochar`'s structure-generation and MD-pipeline machinery. The missing artifact in this repo was not code; it was a durable in-repo plan documenting what Phase 2 was supposed to deliver, what is already complete, and what work remains after the scaffold.

## Scope

This plan covers the Phase 2 repo scaffold and the immediate follow-on work required to make it usable and reviewable as a standalone package.

In scope:

- package structure and dependency boundary
- PFAS ligand input rendering
- topology merge and pre-solvation-stage adapter
- orchestration entry point
- test coverage for pure logic and setup-only end-to-end generation
- documentation and release-readiness follow-up

Out of scope:

- running `ligpargen`
- running `gmx`
- cluster execution or scheduler integration
- scientific validation of PFAS sorption outcomes

## Requirements traceability

Phase 2 needed to produce a separate repo that:

- depends on `biochar>=0.4.0` rather than embedding generic MD setup code
- owns PFAS-specific ligand preparation and topology merge logic
- exposes a usable entry point for generating LigParGen build inputs
- composes PFAS insertion into `biochar.md_setup` through the generic `PreSolvationStage` seam
- proves the setup path with local tests that do not invoke external chemistry or MD tools

## Current status

Phase 2 scaffold is functionally complete.

Completed implementation units:

- `pyproject.toml`
  - standalone package metadata
  - dependency on `biochar>=0.4.0`
  - `biochar-pfas` console entry point

- `biochar_pfas/pfas_ligands.py`
  - PFAS species table for PFOA, PFOS, PFBS
  - `molecules.txt` rendering for LigParGen input
  - cluster-side build script rendering
  - pure-Python biochar + ligand topology merge
  - adapter from merged ligand assets to `PreSolvationStage`

- `biochar_pfas/orchestrate.py`
  - `setup_pfas_md(...)` composition entry point
  - scratch merge flow feeding `biochar.md_setup.setup_one_structure(...)`

- `biochar_pfas/cli.py`
  - `biochar-pfas build-inputs`

- `tests/test_pfas_ligands.py`
  - species-table coverage
  - rendering coverage
  - topology split/merge coverage
  - error-path coverage
  - pre-solvation-stage adapter coverage

- `tests/test_orchestrate.py`
  - setup-only end-to-end verification that the generated run directory is well-formed

- `README.md`
  - package purpose
  - dependency direction
  - local/cluster workflow
  - API and CLI usage

## Gaps that remain after the scaffold

The remaining work is not foundational architecture. It is packaging, operator ergonomics, and stronger proof that the standalone repo is ready for reuse.

### 1. CLI coverage is missing

The CLI currently has no direct test file. The command is small, but it is the primary operator entry point for the remote ligand-build step.

Implementation units:

- `biochar_pfas/cli.py`
- new `tests/test_cli.py`

Test scenarios:

- `build-inputs` writes `molecules.txt` and `build_pfas_ligands.sh`
- default species selection renders all supported PFAS
- explicit `--species` restricts output to the requested subset
- invalid species name exits with a clear failure
- `--remote-outdir` is reflected in the rendered script

### 2. The repo lacks a tracked operator handoff document

The README explains the workflow, but there is no dedicated runbook for the human boundary between local rendering and cluster execution.

Implementation units:

- new `docs/pfas-workflow-runbook.md`
- optional README link to that runbook

Content requirements:

- exact local-to-cluster handoff sequence
- expected files before and after cluster execution
- required cluster prerequisites (`ligpargen`, BOSS, conda env, editable paths)
- review checklist before using generated ligand assets in `setup_pfas_md(...)`
- explicit statement that setup is generated locally but execution is manual

### 3. Compatibility constraints should be made explicit

The package depends on a specific seam in `biochar`, but the compatibility contract is only described informally.

Implementation units:

- `README.md`
- `biochar_pfas/orchestrate.py`
- optional new `tests/test_contract.py`

Decisions:

- document that `biochar` must expose `MDSetupConfig`, `PreSolvationStage`, `MoleculeInsertion`, and `setup_one_structure`
- fail fast with a clearer message if the installed `biochar` lacks the required seam

Test scenarios:

- if feasible without heavy mocking, verify the failure mode when required `biochar.md_setup` symbols are absent
- otherwise document the contract explicitly and keep runtime import errors narrow and readable

## Sequencing

1. Add CLI tests
2. Add the operator runbook
3. Tighten compatibility-contract documentation and failure messaging
4. Re-run the repo test suite
5. Decide whether the package is ready for a tagged initial release

## Recommended next implementation slice

The next slice should be:

1. add `tests/test_cli.py`
2. add `docs/pfas-workflow-runbook.md`
3. update `README.md` to link the runbook and state the `biochar` seam contract

That slice is small, reviewable, and closes the main documentation/testing holes without changing the package architecture.

## Definition of done for this plan

This Phase 2 plan is complete when:

- this repo contains an in-repo planning artifact for the scaffold
- the remaining non-architectural gaps are explicit
- each remaining gap names the files to touch and the tests to add
- an implementer can take the next slice without consulting the old planning repo
