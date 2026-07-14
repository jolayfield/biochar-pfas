# biochar-pfas

A PFAS-sorption MD-setup workflow built **on top of** the independent
[`biochar-simulator`](https://github.com/jolayfield/Biochar-simulator) tool.

`biochar-simulator` generates and equilibrates biochar surfaces and knows
nothing about PFAS. `biochar-pfas` is the *application* that drives it to set up
PFOA / PFOS / PFBS sorption simulations: it parametrizes the PFAS anions (via
LigParGen, offline), merges their topology into a biochar structure, and hands
the insertion to biochar's generic `PreSolvationStage` seam.

Nothing here invokes `gmx` or `ligpargen` — it only writes the files/scripts you
then run yourself (setup only).

## Dependency direction

```
biochar-pfas  ──imports──▶  biochar   (>=0.4.0, needs the md_setup PreSolvationStage seam)
```

`biochar` never imports `biochar-pfas`.

### `biochar` seam contract

`biochar-pfas` consumes `biochar` only through its public `md_setup` API. The
installed `biochar` (>=0.4.0) must expose all of the following symbols from
`biochar.md_setup`, or setup will fail at import time:

| Symbol | Used by | For |
|---|---|---|
| `MDSetupConfig` | `orchestrate.setup_pfas_md` | run configuration; its `pre_solvation_stage` slot is where PFAS insertion is spliced in |
| `PreSolvationStage` | `pfas_ligands.build_pre_solvation_stage` | the generic seam that carries the ligand insertion + merged topology into the pipeline |
| `MoleculeInsertion` | `pfas_ligands.build_pre_solvation_stage` | one per placed species (`gro_file`, `n_copies`, `n_try`) |
| `setup_one_structure` | `orchestrate.setup_pfas_md` | renders the run directory from a structure + config |

The seam is checked at the point of use (not at `import biochar_pfas`) by
`require_biochar_md_setup()`: if `biochar` is not importable, or is too old to
expose every symbol above, it raises `BiocharSeamError` (a subclass of
`ImportError`) naming exactly what is missing and the required version — rather
than letting a bare `ImportError` or `AttributeError` surface deep in the call
stack. `import biochar_pfas` itself never imports `biochar`.

## Install (dev)

```bash
pip install -e ~/Claude_Cowork/Biochar-simulator      # the biochar library
pip install -e .                                       # this package
```

## Workflow

For the full operator procedure across the local/cluster boundary — exact
handoff sequence, expected files before and after each cluster step, cluster
prerequisites, and a pre-run review checklist — see the
[PFAS workflow runbook](docs/pfas-workflow-runbook.md).

```
 (local)                                        (cluster, by hand)
 ────────                                        ──────────────────
 1. biochar / biochar-sweep  ─▶ biochar surface(s) (.gro/.top/.itp)

 2. biochar-pfas build-inputs ─▶ molecules.txt + build_pfas_ligands.sh
                                          ─── scp ──▶ 3. run build_pfas_ligands.sh
                                                         (conda env: ligpargen + BOSS)
                                                         ─▶ atomtypes.itp +
                                                            PFOA/PFOS/PFBS .itp/.gro
                                          ◀── scp back ──
 4. biochar_pfas.setup_pfas_md(...) ─▶ merge topology + build a biochar
    PreSolvationStage + call biochar.md_setup.setup_one_structure
    ─▶ a run directory (run_pipeline.sh, mdp files, merged.top, ligand .gro/.itp)
                                          ─── scp ──▶ 5. review + run by hand
```

### 1. Render the LigParGen build inputs

```bash
biochar-pfas build-inputs --species PFOA PFOS PFBS --output-dir pfas_build
# -> scp pfas_build/ to the cluster, run build_pfas_ligands.sh there,
#    scp the resulting pfas_ligands_gmx/ directory back.
```

### 2. Set up a biochar+PFAS run directory (Python API)

```python
from biochar_pfas import LigandPlacement, setup_pfas_md
from biochar.md_setup import MDSetupConfig

setup_pfas_md(
    gro_path="T300_softwood.gro",
    top_path="T300_softwood.top",
    output_dir="md_runs/T300_softwood_PFOA_PFOS",
    placements=[LigandPlacement("PFOA", n_copies=4),
                LigandPlacement("PFOS", n_copies=2)],
    ligand_system_dir="pfas_ligands_gmx",         # scp'd back from the cluster
    config=MDSetupConfig(ion_profile="mn_calcareous_default"),
)
```

Under the hood this merges the biochar topology with the ligand system, builds a
`biochar.md_setup.PreSolvationStage`, and lets `biochar` render the pipeline —
which anneals the bare surface, inserts the PFAS ligand(s) into its box, then
solvates + adds ions + wet-equilibrates against the merged topology.

## Modules

| Module | Responsibility |
|---|---|
| `biochar_pfas/pfas_ligands.py` | PFAS species table, LigParGen input rendering, biochar+ligand topology merge, `build_pre_solvation_stage` adapter |
| `biochar_pfas/orchestrate.py` | `setup_pfas_md` — compose merge + `biochar.md_setup` |
| `biochar_pfas/cli.py` | `biochar-pfas` command (`build-inputs`) |

## Tests

```bash
python -m pytest -q
```
