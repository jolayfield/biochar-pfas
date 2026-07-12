"""PFAS ligand parametrization + biochar/PFAS topology merging.

This module bridges two previously separate workflows:

  1. The `biochar` package's surface/MD pipeline (`biochar.md_setup`), which
     builds an OPLS-AA `.gro`/`.top`/`.itp` triple for a biochar surface.
  2. A LigParGen-based small-molecule parametrization workflow (typically run
     on an HPC cluster where `ligpargen` + BOSS are installed), which turns a
     SMILES string into an OPLS-AA (CM1A/CM1A-LBCC) `.itp`/`.gro` pair via
     `ligpargen`, and a `build_gromacs_system.py` helper, which merges several
     such ligands into one atom-type-collision-free topology (LigParGen
     restarts atom-type numbering at `opls_800` and calls every moleculetype
     `MOL` on every run, so naively #include-ing two raw `.gmx.itp` files
     corrupts the system).

Nothing in this module invokes `ligpargen`, `build_gromacs_system.py`, or
`gmx` — it only WRITES the scripts/config that do, plus the pure-Python
topology-merging logic that stitches a biochar `.top` together with
already-built ligand `.itp`/`.gro` files. Running the generated
`build_pfas_ligands.sh` (on the cluster, in a conda env with `ligpargen`
and `$BOSSdir` set) is a separate, user-initiated step.

Species
-------
The three PFAS targeted here (PFOA, PFOS, PFBS) are parametrized as their
deprotonated anions (net charge -1), matching their dominant
environmental/physiological ionization state at near-neutral pH (their
conjugate-acid pKa values are all well below 7). LigParGen's CM1A-LBCC charge
model only supports NEUTRAL molecules, so charged species must use plain CM1A
(see `charge_model` below).
"""

from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


class PFASLigandError(Exception):
    """Raised for malformed ligand specs or unmergeable topology files."""


# --------------------------------------------------------------------------- #
# Species definitions
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class PFASSpecies:
    """One PFAS ligand to be built with LigParGen.

    `name` doubles as the LigParGen `-n`/`-p` molecule name AND the
    `build_gromacs_system.py` atom-type/moleculetype prefix, so it must be
    `\\w+` (letters/digits/underscore only) per that script's `NAME_RE`.
    `resname` is the PDB/GRO residue name (<=5 chars, matches `-r`).
    """

    name: str
    smiles: str
    formal_charge: int
    resname: str
    charge_model: str = "CM1A"  # CM1A-LBCC only supports neutral molecules
    description: str = ""


# Deprotonated (anionic) forms -- see module docstring. SMILES verified with
# RDKit against the expected molecular formula and net charge:
#   PFOA- : C8HF15O2  -> deprotonated to C8F15O2-  (net charge -1)
#   PFOS- : C8HF17O3S -> deprotonated to C8F17O3S- (net charge -1)
#   PFBS- : C4HF9O3S  -> deprotonated to C4F9O3S-  (net charge -1)
PFAS_SPECIES: dict[str, PFASSpecies] = {
    "PFOA": PFASSpecies(
        name="PFOA",
        smiles="[O-]C(=O)C(F)(F)C(F)(F)C(F)(F)C(F)(F)C(F)(F)C(F)(F)C(F)(F)F",
        formal_charge=-1,
        resname="PFOA",
        description="Perfluorooctanoic acid, deprotonated carboxylate anion (C8F15O2-).",
    ),
    "PFOS": PFASSpecies(
        name="PFOS",
        smiles="[O-]S(=O)(=O)C(F)(F)C(F)(F)C(F)(F)C(F)(F)C(F)(F)C(F)(F)C(F)(F)C(F)(F)F",
        formal_charge=-1,
        resname="PFOS",
        description="Perfluorooctane sulfonic acid, deprotonated sulfonate anion (C8F17O3S-).",
    ),
    "PFBS": PFASSpecies(
        name="PFBS",
        smiles="[O-]S(=O)(=O)C(F)(F)C(F)(F)C(F)(F)C(F)(F)F",
        formal_charge=-1,
        resname="PFBS",
        description="Perfluorobutane sulfonic acid, deprotonated sulfonate anion (C4F9O3S-).",
    ),
}

NAME_RE = re.compile(r"^\w+$")


def get_pfas_species(name_or_species) -> PFASSpecies:
    if isinstance(name_or_species, PFASSpecies):
        return name_or_species
    try:
        return PFAS_SPECIES[name_or_species]
    except KeyError as exc:
        raise PFASLigandError(
            f"Unknown PFAS species {name_or_species!r}; choices: {sorted(PFAS_SPECIES)}"
        ) from exc


# --------------------------------------------------------------------------- #
# Step 1 (remote cluster, NOT executed here): LigParGen molecule-list + build
# script for `build_gromacs_system.py`.
# --------------------------------------------------------------------------- #
def render_ligpargen_molecules_txt(species: list[PFASSpecies]) -> str:
    """`molecules.txt` in `build_gromacs_system.py`'s expected format:
    `name  input(SMILES)  charge  chargemodel`, one molecule per line.
    """
    for sp in species:
        if not NAME_RE.match(sp.name):
            raise PFASLigandError(
                f"species name {sp.name!r} must be letters/digits/underscore only "
                "(build_gromacs_system.py requires this for its atom-type prefix)"
            )
    lines = [
        "# name      input (SMILES)                                              charge   chargemodel",
    ]
    for sp in species:
        lines.append(f"{sp.name:<10s}  {sp.smiles:<60s}  {sp.formal_charge:<7d}  {sp.charge_model}")
    return "\n".join(lines) + "\n"


def render_ligpargen_build_script(
    species: list[PFASSpecies],
    remote_ligpargen_dir: str = "$HOME/ligpargen",
    remote_boss_dir: str = "$HOME/boss",
    conda_env: str = "ligpargen",
    remote_outdir: str = "pfas_ligands_gmx",
) -> str:
    """Bash script that builds all PFAS ligands into one internally-consistent
    GROMACS topology via `build_gromacs_system.py`. Meant to run on the cluster
    where `ligpargen` + BOSS are installed; NOT executed by this module -- copy
    it (with the accompanying `molecules.txt`) to the cluster and run it there
    once ligand parametrization is wanted.

    Point ``remote_ligpargen_dir`` / ``remote_boss_dir`` / ``conda_env`` at your
    own cluster's LigParGen + BOSS install (the defaults are placeholders).
    """
    names = ", ".join(sp.name for sp in species)
    return f"""#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# Build OPLS-AA/CM1A topologies for PFAS ligands: {names}
# Generated by biochar_pfas.pfas_ligands -- run this on the cluster, in a conda
# env where `ligpargen` and BOSS are installed. Produces one
# internally-consistent, collision-free topology via build_gromacs_system.py
# (LigParGen alone restarts atom-type numbering at opls_800 and names every
# moleculetype 'MOL' on every run -- naively #include-ing multiple raw
# .gmx.itp files corrupts the system).
#
# NOT executed automatically -- edit the paths below for your install, then run
# by hand once you're ready to build the ligands:
#   scp molecules.txt build_pfas_ligands.sh <cluster>:~/some/workdir/
#   ssh <cluster>
#   cd ~/some/workdir && ./build_pfas_ligands.sh
# ============================================================================

conda activate {conda_env}
export BOSSdir="{remote_boss_dir}"

HERE="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
python "{remote_ligpargen_dir}/build_gromacs_system.py" "$HERE/molecules.txt" "$HERE/{remote_outdir}"

echo ""
echo "Built ligand topologies in $HERE/{remote_outdir}/:"
echo "  atomtypes.itp + one <name>.itp/<name>.gro pair per species."
echo "Copy that directory back to merge with a biochar structure, e.g.:"
echo "  scp -r <cluster>:~/some/workdir/{remote_outdir} ./"
"""


# --------------------------------------------------------------------------- #
# Step 2 (local, pure Python): merge an already-built ligand system
# (atomtypes.itp + <name>.itp + <name>.gro, from build_gromacs_system.py)
# into a biochar structure's topology.
# --------------------------------------------------------------------------- #
_SECTION_RE = re.compile(r"^\s*\[\s*(.+?)\s*\]")


def _split_biochar_top(top_text: str) -> tuple[str, str, str]:
    """Split a biochar `.top` (as written by `biochar.biochar_generator`) into
    (header, moleculetype_body, molecules_name). `header` is everything up to
    and including the `#include "oplsaa.ff/forcefield.itp"` line;
    `moleculetype_body` is the `[ moleculetype ]` ... block up to (not
    including) `[ system ]`; `molecules_name` is the residue/moleculetype
    label used in `[ molecules ]` (e.g. "BC000").
    """
    lines = top_text.splitlines()
    mt_idx = next((i for i, ln in enumerate(lines) if _SECTION_RE.match(ln) and
                   _SECTION_RE.match(ln).group(1).lower() == "moleculetype"), None)
    sys_idx = next((i for i, ln in enumerate(lines) if _SECTION_RE.match(ln) and
                    _SECTION_RE.match(ln).group(1).lower() == "system"), None)
    mol_idx = next((i for i, ln in enumerate(lines) if _SECTION_RE.match(ln) and
                    _SECTION_RE.match(ln).group(1).lower() == "molecules"), None)
    if mt_idx is None or sys_idx is None or mol_idx is None:
        raise PFASLigandError(
            "biochar .top does not look like the expected format "
            "([moleculetype]/[system]/[molecules] section not found)"
        )
    header = "\n".join(lines[:mt_idx]).rstrip() + "\n"
    body = "\n".join(lines[mt_idx:sys_idx]).rstrip() + "\n"
    # [ molecules ] lists exactly one "<name> 1" row for a bare biochar structure.
    mol_lines = [ln for ln in lines[mol_idx + 1:] if ln.strip() and not ln.strip().startswith(";")]
    if not mol_lines:
        raise PFASLigandError("biochar .top [ molecules ] section is empty")
    name = mol_lines[0].split()[0]
    return header, body, name


@dataclass
class LigandPlacement:
    """One PFAS species to include in the merged system + how many copies."""

    species_name: str          # key into PFAS_SPECIES, and the ligand-system
                                # basename (<species_name>.itp / .gro)
    n_copies: int = 1
    insertion_try: int = 500   # `gmx insert-molecules -try`


def merge_biochar_pfas_topology(
    biochar_top_path: str | Path,
    ligand_system_dir: str | Path,
    placements: list[LigandPlacement],
    output_dir: str | Path,
) -> dict:
    """Combine a biochar `.top` with a `build_gromacs_system.py` ligand system
    (`atomtypes.itp` + one `<name>.itp`/`<name>.gro` per species) into one
    merged, internally-consistent OPLS-AA topology.

    Writes into `output_dir`:
        <output_dir>/merged.top     -- oplsaa.ff + atomtypes.itp + biochar
                                        moleculetype + each ligand moleculetype
                                        + [system]/[molecules] (biochar: 1,
                                        each ligand: its requested n_copies)
        <output_dir>/atomtypes.itp  -- copied verbatim from ligand_system_dir
        <output_dir>/<name>.itp     -- copied verbatim, one per ligand species
        <output_dir>/<name>.gro     -- copied verbatim, one per ligand species
                                        (single-copy coordinates for
                                        `gmx insert-molecules -ci`)

    No `.gro` is written for the *merged* system here -- the biochar+ligand
    box is assembled at run time by chained `gmx insert-molecules -ci
    <name>.gro -nmol n_copies` calls (see `md_setup.LigandSpec` /
    `_render_pipeline_script`), because the ligand copy count and starting
    positions are a per-run choice, not a fixed structure file.

    Returns {"top_path": ..., "ligand_gro_names": {species_name: filename}}.
    """
    biochar_top_path = Path(biochar_top_path)
    ligand_system_dir = Path(ligand_system_dir)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    if not biochar_top_path.exists():
        raise PFASLigandError(f"biochar top not found: {biochar_top_path}")
    atomtypes_src = ligand_system_dir / "atomtypes.itp"
    if not atomtypes_src.exists():
        raise PFASLigandError(
            f"{atomtypes_src} not found -- expected build_gromacs_system.py output "
            "(atomtypes.itp + one <name>.itp/<name>.gro per ligand)"
        )
    if not placements:
        raise PFASLigandError("merge_biochar_pfas_topology needs at least one LigandPlacement")

    header, biochar_body, biochar_mol_name = _split_biochar_top(biochar_top_path.read_text())

    import shutil

    shutil.copy(atomtypes_src, out / "atomtypes.itp")

    ligand_gro_names: dict[str, str] = {}
    include_lines = []
    molecules_lines = [f"{biochar_mol_name:<20s} 1"]
    seen = set()
    for p in placements:
        if p.species_name in seen:
            raise PFASLigandError(f"duplicate ligand species in placements: {p.species_name}")
        seen.add(p.species_name)
        if p.n_copies < 1:
            raise PFASLigandError(f"{p.species_name}: n_copies must be >= 1, got {p.n_copies}")

        itp_src = ligand_system_dir / f"{p.species_name}.itp"
        gro_src = ligand_system_dir / f"{p.species_name}.gro"
        if not itp_src.exists():
            raise PFASLigandError(f"{itp_src} not found for ligand {p.species_name!r}")
        if not gro_src.exists():
            raise PFASLigandError(f"{gro_src} not found for ligand {p.species_name!r}")

        shutil.copy(itp_src, out / itp_src.name)
        shutil.copy(gro_src, out / gro_src.name)
        ligand_gro_names[p.species_name] = gro_src.name

        include_lines.append(f'#include "{p.species_name}.itp"')
        molecules_lines.append(f"{p.species_name:<20s} {p.n_copies}")

    merged = []
    merged.append(header.rstrip())
    merged.append('#include "atomtypes.itp"')
    merged.append("")
    merged.append(biochar_body.rstrip())
    merged.append("")
    merged.extend(include_lines)
    merged.append("")
    merged.append("[ system ]")
    merged.append(f"{biochar_mol_name} + PFAS ligands (biochar.pfas_ligands merge)")
    merged.append("")
    merged.append("[ molecules ]")
    merged.extend(molecules_lines)
    merged_text = "\n".join(merged) + "\n"

    merged_top_path = out / "merged.top"
    merged_top_path.write_text(merged_text)

    return {"top_path": merged_top_path, "ligand_gro_names": ligand_gro_names}


# --------------------------------------------------------------------------- #
# Step 3 (local): adapt a merged ligand system into biochar's generic
# pre-solvation insertion seam (biochar.md_setup.PreSolvationStage).
# --------------------------------------------------------------------------- #
def build_pre_solvation_stage(
    placements: list[LigandPlacement],
    merge_result: dict,
    name: str = "Insert PFAS ligand(s)",
):
    """Turn a `merge_biochar_pfas_topology` result into a biochar
    `PreSolvationStage` so `biochar.md_setup` can splice the ligand insertion
    into its pipeline without knowing anything about PFAS.

    biochar owns the pipeline and the generic seam; this function is the only
    place that translates PFAS placements → generic `MoleculeInsertion`s.
    `merge_result` is exactly what `merge_biochar_pfas_topology` returns; the
    files it wrote (merged.top, atomtypes.itp, per-species .itp/.gro) live next
    to `merge_result["top_path"]` and are passed through as `extra_files` so
    `setup_one_structure` copies them into the run directory.
    """
    from biochar.md_setup import PreSolvationStage, MoleculeInsertion

    merged_top = Path(merge_result["top_path"])
    ligand_dir = merged_top.parent
    ligand_gro_names = merge_result["ligand_gro_names"]

    insertions = [
        MoleculeInsertion(
            gro_file=ligand_gro_names[p.species_name],
            n_copies=p.n_copies,
            n_try=p.insertion_try,
        )
        for p in placements
    ]

    extra_files = [str(merged_top), str(ligand_dir / "atomtypes.itp")]
    for p in placements:
        extra_files.append(str(ligand_dir / f"{p.species_name}.itp"))
        extra_files.append(str(ligand_dir / ligand_gro_names[p.species_name]))

    return PreSolvationStage(
        name=name,
        insertions=insertions,
        solvation_top=merged_top.name,
        extra_files=extra_files,
    )
