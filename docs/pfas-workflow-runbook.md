---
title: "PFAS workflow runbook — local rendering to cluster execution"
status: active
created: 2026-07-12
updated: 2026-07-12
---

# PFAS workflow runbook

This runbook is the operator-facing companion to the [README](../README.md). The
README explains *what* `biochar-pfas` is; this document is the step-by-step
procedure for the one part of the workflow a human has to drive by hand: the
boundary between **local setup rendering** and **cluster execution**.

## Standing constraint: setup is generated locally, execution is manual

`biochar-pfas` never runs chemistry or MD. It does not invoke `ligpargen`,
`build_gromacs_system.py`, or `gmx`, and it does not submit anything to a
scheduler. Every script it emits (`build_pfas_ligands.sh`, `run_pipeline.sh`,
and any cluster chain scripts) is meant to be **reviewed and then run by you**,
by hand, when you are ready. The two steps below that touch cluster compute —
building the ligands (step 2) and running the pipeline (step 5) — are always
yours to execute.

## The handoff at a glance

```
 LOCAL (this repo)                         CLUSTER (by hand)
 ─────────────────                         ─────────────────
 1. render build inputs
    biochar-pfas build-inputs
    → pfas_build/molecules.txt
    → pfas_build/build_pfas_ligands.sh
                                 ── scp ──▶ 2. run build_pfas_ligands.sh
                                              (conda env + BOSS + ligpargen)
                                              → pfas_ligands_gmx/
                                 ◀─ scp ──
 3. merge + set up run dir
    setup_pfas_md(...)
    → md_runs/<name>/ (merged.top,
      run_pipeline.sh, ligand .itp/.gro)
                                 ── scp ──▶ 4. review, then run by hand
                                              (run_pipeline.sh / chain scripts)
```

## Step-by-step

### Step 1 — render the LigParGen build inputs (local)

```bash
biochar-pfas build-inputs --species PFOA PFOS PFBS --output-dir pfas_build
```

Files that must exist **before** cluster execution (all written by this step):

| File | Purpose |
|---|---|
| `pfas_build/molecules.txt` | `name  SMILES  charge  chargemodel` table `build_gromacs_system.py` consumes |
| `pfas_build/build_pfas_ligands.sh` | cluster build script (edit its paths — see below — then run on the cluster) |

Copy the directory to the cluster:

```bash
scp -r pfas_build <cluster>:~/some/workdir/
```

### Step 2 — build the ligand system (cluster, by hand)

Cluster prerequisites — the build script assumes all of these and will not
provision them for you:

- **`ligpargen`** installed and importable, plus its `build_gromacs_system.py`
  helper. The rendered script points at it via `remote_ligpargen_dir`
  (default `$HOME/ligpargen` — a placeholder; edit it for your install).
- **BOSS** installed, with `$BOSSdir` pointing at it. The script exports
  `BOSSdir` from `remote_boss_dir` (default `$HOME/boss` — also a placeholder).
- A **conda env** where `ligpargen` and BOSS resolve. The script runs
  `conda activate <conda_env>` (default `ligpargen`). LigParGen historically
  requires Python 3.7-era dependencies, so this is usually a dedicated env.

Edit those three paths at the top of `build_pfas_ligands.sh` to match your
cluster, then run it:

```bash
ssh <cluster>
cd ~/some/workdir && ./build_pfas_ligands.sh
```

Files that must exist **after** cluster execution, in `pfas_ligands_gmx/`
(named by `--remote-outdir`):

| File | Purpose |
|---|---|
| `atomtypes.itp` | one collision-free atom-type block shared by every ligand |
| `<SPECIES>.itp` | one moleculetype per species (e.g. `PFOA.itp`, `PFOS.itp`, `PFBS.itp`) |
| `<SPECIES>.gro` | single-copy coordinates per species, for `gmx insert-molecules -ci` |

`build_gromacs_system.py` exists precisely to make these `#include`-compatible:
plain LigParGen restarts atom-type numbering at `opls_800` and names every
moleculetype `MOL` on every run, so two raw `.gmx.itp` outputs cannot be
combined without corruption. The merge logic in `biochar-pfas` relies on this
renaming having already happened.

Copy the result back:

```bash
scp -r <cluster>:~/some/workdir/pfas_ligands_gmx ./
```

### Step 3 — merge + build the run directory (local)

```python
from biochar_pfas import LigandPlacement, setup_pfas_md
from biochar.md_setup import MDSetupConfig

setup_pfas_md(
    gro_path="T300_softwood.gro",
    top_path="T300_softwood.top",
    output_dir="md_runs/T300_softwood_PFOA_PFOS",
    placements=[LigandPlacement("PFOA", n_copies=4),
                LigandPlacement("PFOS", n_copies=2)],
    ligand_system_dir="pfas_ligands_gmx",   # scp'd back in step 2
    config=MDSetupConfig(ion_profile="mn_calcareous_default"),
)
```

### Review checklist — before you trust the generated run directory

Run through this before scp-ing the run directory back to the cluster and
executing anything in step 4/5:

- [ ] `pfas_ligands_gmx/` contains `atomtypes.itp` **and** a matching
      `<SPECIES>.itp`/`<SPECIES>.gro` pair for every species you plan to place.
- [ ] Each `LigandPlacement.species_name` matches a species key
      (`PFOA`/`PFOS`/`PFBS`) and the corresponding ligand filenames.
- [ ] `n_copies >= 1` for every placement, and the counts are the ones you
      intend for this run (copy count is a per-run choice, not baked into the
      topology).
- [ ] `md_runs/<name>/merged.top` exists and its `[ molecules ]` section lists
      the biochar moleculetype once plus each ligand at its requested count.
- [ ] `md_runs/<name>/run_pipeline.sh` inserts the ligand(s)
      (`gmx insert-molecules`) **before** solvation, and every `grompp` call
      from solvation onward uses `merged.top`, not the bare biochar `.top`.
- [ ] The ligand `.itp`/`.gro` files were copied into `md_runs/<name>/`
      alongside `merged.top` (they are staged there, not referenced in place).
- [ ] Ion profile / equilibration settings in `MDSetupConfig` are what you want
      for this system.

### Steps 4–5 — review and run on the cluster (by hand)

Copy the run directory to the cluster, read the generated scripts, and run them
yourself. `biochar-pfas` has done its job once the run directory is written;
nothing in this repo launches the simulation.

## Reference: files before and after each cluster step

| Boundary | Must exist before | Produced after |
|---|---|---|
| Step 2 (build ligands) | `pfas_build/molecules.txt`, `pfas_build/build_pfas_ligands.sh` | `pfas_ligands_gmx/{atomtypes.itp, <SPECIES>.itp, <SPECIES>.gro}` |
| Step 5 (run pipeline) | `md_runs/<name>/{merged.top, run_pipeline.sh, <SPECIES>.itp, <SPECIES>.gro}` | GROMACS trajectory/output (produced by you, on the cluster) |
