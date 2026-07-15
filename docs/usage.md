---
title: "biochar-pfas usage guide"
status: active
created: 2026-07-14
updated: 2026-07-14
---

# biochar-pfas usage guide

A task-oriented reference for the CLI and Python API. For the operator
procedure across the local/cluster boundary, see the
[workflow runbook](pfas-workflow-runbook.md); for a full worked walk-through,
see [`examples/pfas_binding/`](../examples/pfas_binding/).

> **Setup only.** Everything here *writes files* — inputs, topologies, and run
> scripts. Nothing invokes `ligpargen`, `build_gromacs_system.py`, or `gmx`, and
> nothing submits a cluster job. The two compute steps (building the ligands and
> running the pipeline) are always run by you, by hand.

## Contents

- [Install](#install)
- [The workflow in one screen](#the-workflow-in-one-screen)
- [CLI reference](#cli-reference)
  - [`build-inputs`](#biochar-pfas-build-inputs)
  - [`setup`](#biochar-pfas-setup)
- [Python API reference](#python-api-reference)
- [Recipes](#recipes)
- [Troubleshooting](#troubleshooting)

## Install

```bash
pip install -e ~/Claude_Cowork/Biochar-simulator   # the biochar library (needs RDKit)
pip install -e .                                    # this package
```

`biochar-pfas` depends on `biochar>=0.4.0` exposing the `md_setup` seam
(`MDSetupConfig`, `PreSolvationStage`, `MoleculeInsertion`, `setup_one_structure`).
`import biochar_pfas` never imports `biochar`; the dependency is only touched
when you actually build a run directory, and a missing/old `biochar` fails fast
with a clear `BiocharSeamError`.

## The workflow in one screen

```
 LOCAL                                           CLUSTER (by hand)
 ─────                                           ─────────────────
 1. biochar-sweep / biochar     ─▶ structure(s) (.gro/.top/.itp)
 2. biochar-pfas build-inputs   ─▶ molecules.txt + build_pfas_ligands.sh
                                      ── scp ──▶ 3. ./build_pfas_ligands.sh
                                                    ─▶ pfas_ligands_gmx/
                                      ◀─ scp ──
 4. biochar-pfas setup          ─▶ run directory (merged.top, run_pipeline.sh, …)
    (or setup_pfas_md)
                                      ── scp ──▶ 5. review + run by hand
```

Steps 1 (structure generation) belongs to the `biochar` tool; steps 3 and 5 are
manual cluster work. `biochar-pfas` owns steps 2 and 4.

## CLI reference

The console entry point is `biochar-pfas`, with two subcommands.

### `biochar-pfas build-inputs`

Render the LigParGen build inputs for a set of PFAS species.

```bash
biochar-pfas build-inputs [--species NAME ...] [--output-dir DIR] [--remote-outdir DIR]
```

| Flag | Default | Meaning |
|---|---|---|
| `--species` | all (`PFBS PFOA PFOS`) | which species to render (space-separated) |
| `--output-dir` | `pfas_build` | directory to write `molecules.txt` + `build_pfas_ligands.sh` into |
| `--remote-outdir` | `pfas_ligands_gmx` | directory name the cluster build script writes ligand topologies into |

Example:

```bash
biochar-pfas build-inputs --species PFOA PFOS PFBS --output-dir pfas_build
```

Writes `pfas_build/molecules.txt` and `pfas_build/build_pfas_ligands.sh`. Edit
the paths at the top of the script (`ligpargen` dir, `$BOSSdir`, conda env) for
your cluster before running it there.

### `biochar-pfas setup`

Merge a pre-built ligand system into a biochar structure and build a GROMACS run
directory. Wraps `setup_pfas_md`.

```bash
biochar-pfas setup \
  --gro FILE --top FILE \
  --ligand-system-dir DIR \
  --output-dir DIR \
  --place SPECIES:COUNT[:TRY] [--place ...] \
  [--label NAME] [--ion-profile NAME] [--cluster NAME]
```

| Flag | Required | Default | Meaning |
|---|---|---|---|
| `--gro` | yes | — | biochar structure `.gro` (from `biochar`/`biochar-sweep`) |
| `--top` | yes | — | biochar structure `.top` |
| `--ligand-system-dir` | yes | — | a `build_gromacs_system.py` output dir (`atomtypes.itp` + `<name>.itp`/`.gro` per species), scp'd back from the cluster |
| `--output-dir` | yes | — | run directory to create |
| `--place` | yes (≥1) | — | a placement, repeatable — see below |
| `--label` | no | `pfas` | run label |
| `--ion-profile` | no | — | ion profile passed to `MDSetupConfig` (a `biochar` setting) |
| `--cluster` | no | — | cluster name for `MDSetupConfig`; omit for a local `run_pipeline.sh` |

**`--place` syntax:** `SPECIES:COUNT[:TRY]`, repeatable.

- `SPECIES` — a known PFAS (`PFOA`, `PFOS`, `PFBS`).
- `COUNT` — number of copies to insert (integer ≥ 1). Deliberately required — a
  copy count is a per-run choice, not baked into the topology.
- `TRY` — optional `gmx insert-molecules -try` value (integer ≥ 1, default 500).

Example:

```bash
biochar-pfas setup \
  --gro T300_softwood.gro --top T300_softwood.top \
  --ligand-system-dir pfas_ligands_gmx \
  --output-dir md_runs/T300_softwood_PFOA_PFOS \
  --place PFOA:4 --place PFOS:2:250 \
  --ion-profile mn_calcareous_default
```

Writes `md_runs/T300_softwood_PFOA_PFOS/` containing `merged.top`,
`run_pipeline.sh`, the ligand `.itp`/`.gro` files, and (if `--cluster` is set)
the SLURM chain scripts.

**Error behaviour.** A malformed `--place`, an unknown species, or a
missing/old `biochar` produces a clean `biochar-pfas: error: …` message on
stderr and exit code 2 — not a traceback.

## Python API reference

Everything below is importable from the top-level `biochar_pfas` package.

### Rendering LigParGen inputs

```python
from biochar_pfas import (
    PFAS_SPECIES, render_ligpargen_molecules_txt, render_ligpargen_build_script,
)

species = [PFAS_SPECIES["PFOA"], PFAS_SPECIES["PFOS"], PFAS_SPECIES["PFBS"]]
open("pfas_build/molecules.txt", "w").write(render_ligpargen_molecules_txt(species))
open("pfas_build/build_pfas_ligands.sh", "w").write(
    render_ligpargen_build_script(species, remote_outdir="pfas_ligands_gmx")
)
```

- `render_ligpargen_molecules_txt(species) -> str` — the `name SMILES charge
  chargemodel` table `build_gromacs_system.py` expects.
- `render_ligpargen_build_script(species, remote_ligpargen_dir="$HOME/ligpargen",
  remote_boss_dir="$HOME/boss", conda_env="ligpargen",
  remote_outdir="pfas_ligands_gmx") -> str` — the cluster build script. The path
  defaults are placeholders; point them at your install.

### The species table

- `PFAS_SPECIES: dict[str, PFASSpecies]` — `"PFOA"`, `"PFOS"`, `"PFBS"`, all
  parametrized as deprotonated anions (net charge −1, charge model `CM1A`).
- `get_pfas_species(name_or_species) -> PFASSpecies` — look up by name, or pass a
  `PFASSpecies` through. Raises `PFASLigandError` for an unknown name.
- `PFASSpecies(name, smiles, formal_charge, resname, charge_model="CM1A",
  description="")` — a frozen dataclass, if you need a custom ligand.

### Placements

```python
from biochar_pfas import LigandPlacement
LigandPlacement("PFOA", n_copies=4)              # 4 copies, default -try 500
LigandPlacement("PFOS", n_copies=2, insertion_try=250)
```

### Building a run directory — the one-call path

```python
from biochar_pfas import LigandPlacement, setup_pfas_md
from biochar.md_setup import MDSetupConfig

run_dir = setup_pfas_md(
    gro_path="T300_softwood.gro",
    top_path="T300_softwood.top",
    output_dir="md_runs/T300_softwood_PFOA_PFOS",
    placements=[LigandPlacement("PFOA", n_copies=4),
                LigandPlacement("PFOS", n_copies=2)],
    ligand_system_dir="pfas_ligands_gmx",
    config=MDSetupConfig(ion_profile="mn_calcareous_default"),
)
```

`setup_pfas_md(gro_path, top_path, output_dir, placements, ligand_system_dir,
label="pfas", config=None, stage_name=...) -> Path` merges the topology, builds
a `biochar` `PreSolvationStage`, and calls `biochar.md_setup.setup_one_structure`.
Returns the run directory path.

### Lower-level building blocks

If you want the merge or the stage on their own:

- `merge_biochar_pfas_topology(biochar_top_path, ligand_system_dir, placements,
  output_dir) -> {"top_path": Path, "ligand_gro_names": {species: filename}}` —
  the pure-Python topology merge (writes `merged.top` + copies of the ligand
  files). Raises `PFASLigandError` on missing/duplicate/malformed inputs.
- `build_pre_solvation_stage(placements, merge_result, name=...)` — adapts a
  merge result into a `biochar.md_setup.PreSolvationStage`.

### The `biochar` seam guard

- `require_biochar_md_setup()` — imports and validates `biochar.md_setup`,
  returning the module. Raises `BiocharSeamError` (a subclass of `ImportError`)
  if `biochar` is missing or too old.
- `BiocharSeamError` — catch it if you want to handle a missing `biochar`
  gracefully; `except ImportError` also catches it.

## Recipes

**One species, one structure, local run:**

```bash
biochar-pfas setup --gro s.gro --top s.top --ligand-system-dir pfas_ligands_gmx \
  --output-dir md_runs/s_PFOA --place PFOA:6
```

**Several species with different insertion effort:**

```bash
biochar-pfas setup --gro s.gro --top s.top --ligand-system-dir pfas_ligands_gmx \
  --output-dir md_runs/s_mix --place PFOA:4 --place PFOS:2:250 --place PFBS:2
```

**Generate SLURM chain scripts instead of a local `run_pipeline.sh`:**

```bash
biochar-pfas setup ... --cluster mu3c
```

**A structure × placement matrix (Python):**

```python
from itertools import product
from biochar_pfas import LigandPlacement, setup_pfas_md
from biochar.md_setup import MDSetupConfig

structures = {"T300_softwood": ("...T300.gro", "...T300.top"),
              "T600_softwood": ("...T600.gro", "...T600.top")}
placements = {"PFOA": [LigandPlacement("PFOA", 4)],
              "PFOS": [LigandPlacement("PFOS", 4)]}

for (sname, (gro, top)), (pname, place) in product(structures.items(), placements.items()):
    setup_pfas_md(gro, top, f"md_runs/{sname}_{pname}", place, "pfas_ligands_gmx",
                  config=MDSetupConfig(ion_profile="mn_calcareous_default"))
```

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `biochar-pfas: error: biochar (>=0.4.0) is required but could not be imported` | `biochar` not installed | `pip install -e ~/Claude_Cowork/Biochar-simulator` |
| `BiocharSeamError: installed biochar.md_setup is missing …` | `biochar` too old (no seam) | upgrade to `biochar>=0.4.0` |
| `error: Unknown PFAS species 'X'` | typo / unsupported species | use `PFOA`, `PFOS`, or `PFBS` (case-sensitive) |
| `error: bad --place 'PFOA': expected SPECIES:COUNT[:TRY]` | wrong `--place` shape | e.g. `PFOA:4` or `PFOA:4:250` |
| `PFASLigandError: <dir>/atomtypes.itp not found` | `--ligand-system-dir` isn't a `build_gromacs_system.py` output | point it at the `pfas_ligands_gmx/` you scp'd back |
| `PFASLigandError: <dir>/PFBS.itp not found for ligand 'PFBS'` | placed a species you didn't build | include it in `build-inputs` + the cluster build, or drop the `--place` |
| `biochar .top does not look like the expected format` | `--top` isn't a `biochar` generator `.top` | pass the structure's real `.top` |

See also: [workflow runbook](pfas-workflow-runbook.md) ·
[worked example](../examples/pfas_binding/) · [README](../README.md).
