"""
End-to-end driver: biochar surface + PFAS ligand system -> a GROMACS run
directory with the ligand(s) inserted before solvation.

This is the glue that composes the two halves:
  * PFAS side (this package): merge the biochar topology with a pre-built
    LigParGen ligand system and describe the insertion as a biochar
    `PreSolvationStage`.
  * biochar side (`biochar.md_setup`): render the actual pipeline and stage the
    files, entirely unaware that the inserted molecules are PFAS.

Nothing here invokes `gmx` or `ligpargen`; it only writes files (setup only).
"""

from __future__ import annotations

import dataclasses
import tempfile
from pathlib import Path
from typing import Optional

from .pfas_ligands import (
    LigandPlacement,
    build_pre_solvation_stage,
    merge_biochar_pfas_topology,
)


def setup_pfas_md(
    gro_path: str | Path,
    top_path: str | Path,
    output_dir: str | Path,
    placements: list[LigandPlacement],
    ligand_system_dir: str | Path,
    label: str = "pfas",
    config=None,
    stage_name: str = "Insert PFAS ligand(s)",
) -> Path:
    """Set up one biochar+PFAS MD run directory.

    Args:
        gro_path/top_path: a bare biochar structure (from `biochar` /
            `biochar.sweep`).
        output_dir: run directory to create.
        placements: which PFAS species + how many copies to insert.
        ligand_system_dir: a `build_gromacs_system.py` output directory
            (atomtypes.itp + one <name>.itp/<name>.gro per species), built
            offline on the cluster via `render_ligpargen_build_script`.
        config: an optional `biochar.md_setup.MDSetupConfig`; its
            `pre_solvation_stage` is filled in here (any existing value is
            replaced).
        stage_name: banner label for the insertion stage.

    Returns the created run directory `Path`.
    """
    from biochar.md_setup import MDSetupConfig, setup_one_structure

    # Merge into a scratch dir; setup_one_structure copies the stage's
    # extra_files (merged.top + ligand .itp/.gro) into the run directory, so the
    # scratch dir is disposable.
    with tempfile.TemporaryDirectory() as scratch:
        merge_result = merge_biochar_pfas_topology(
            top_path, ligand_system_dir, placements, scratch
        )
        stage = build_pre_solvation_stage(placements, merge_result, name=stage_name)
        cfg = dataclasses.replace(config or MDSetupConfig(), pre_solvation_stage=stage)
        return setup_one_structure(
            gro_path, top_path, output_dir, label=label, config=cfg
        )
