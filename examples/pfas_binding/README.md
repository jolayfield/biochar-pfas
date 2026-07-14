# Example: PFOA / PFOS / PFBS binding onto biochar

A worked, **setup-only** walk-through of the whole `biochar-pfas` flow: from a
biochar surface to a GROMACS run directory with PFAS ligand(s) inserted. Every
step here either renders files or documents a manual step — nothing runs
`ligpargen` or `gmx`. See the [workflow runbook](../../docs/pfas-workflow-runbook.md)
for the full operator procedure.

## The setup matrix this example illustrates

A representative sorption study varies the biochar surface and the PFAS placed
on it:

- **structures:** a pyrolysis-temperature × feedstock grid, generated upstream
  by the sibling example [`../pfas_temperature_grid.yaml`](../pfas_temperature_grid.yaml)
  (temperature sets O/C, the variable hypothesised to drive PFAS binding).
- **ligands:** PFOA, PFOS, PFBS — the three anions in
  [`biochar_pfas.PFAS_SPECIES`](../../biochar_pfas/pfas_ligands.py).
- **ion profile:** one competition environment (e.g. `mn_calcareous_default`)
  with Ca²⁺/Mg²⁺/Na⁺/K⁺.

You set up one run directory per (structure × placement × ion-profile) point.
The two steps below show a single point end to end.

## Step 0 — generate the biochar structure(s) (upstream, `biochar`)

```bash
biochar-sweep run examples/pfas_temperature_grid.yaml
# -> sweep_out/pfas_temperature_grid/structures/<...>/<name>.gro/.top/.itp
```

## Step 1 — render the LigParGen build inputs (local, setup-only)

Either via this example's driver:

```bash
python examples/pfas_binding/build_inputs.py --output-dir pfas_build
```

or via the CLI:

```bash
biochar-pfas build-inputs --species PFOA PFOS PFBS --output-dir pfas_build
```

Both write `pfas_build/molecules.txt` + `pfas_build/build_pfas_ligands.sh`.

## Step 2 — build the ligand system (cluster, by hand)

```bash
scp -r pfas_build <cluster>:~/work/ && ssh <cluster>
cd ~/work && ./build_pfas_ligands.sh      # edit its paths first
scp -r <cluster>:~/work/pfas_ligands_gmx ./
```

Produces `pfas_ligands_gmx/{atomtypes.itp, PFOA.itp/.gro, PFOS.itp/.gro,
PFBS.itp/.gro}`. (See the runbook for prerequisites: `ligpargen`, BOSS, conda.)

## Step 3 — build a run directory (local, setup-only)

Via the CLI:

```bash
biochar-pfas setup \
  --gro sweep_out/pfas_temperature_grid/structures/000_T300_softwood/T300_softwood.gro \
  --top sweep_out/pfas_temperature_grid/structures/000_T300_softwood/T300_softwood.top \
  --ligand-system-dir pfas_ligands_gmx \
  --output-dir md_runs/T300_softwood_PFOA_PFOS \
  --place PFOA:4 --place PFOS:2:250 \
  --ion-profile mn_calcareous_default
```

or the Python API (`setup_pfas_md`, see the top-level [README](../../README.md)).

The generated `md_runs/.../run_pipeline.sh` anneals the bare surface, inserts
the PFAS ligand(s), then solvates + adds ions + wet-equilibrates against the
merged topology.

## Step 4 — review and run (cluster, by hand)

Work through the runbook's pre-run checklist, then run the generated scripts
yourself. `biochar-pfas` is done once the run directory is written.
