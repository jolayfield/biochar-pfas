"""
biochar-pfas — PFAS-sorption workflow on top of the biochar-simulator tool.

This package is an *application*: it drives the independent `biochar` library
(surface generation + sweeps + MD equilibration) to set up PFAS/biochar sorption
simulations. All PFAS-specific knowledge (species, LigParGen glue, biochar+ligand
topology merge) lives here; `biochar` itself knows nothing about PFAS and is
consumed through its public API and its generic `PreSolvationStage` seam.
"""

from .pfas_ligands import (
    PFASSpecies,
    PFASLigandError,
    PFAS_SPECIES,
    get_pfas_species,
    LigandPlacement,
    render_ligpargen_molecules_txt,
    render_ligpargen_build_script,
    merge_biochar_pfas_topology,
    build_pre_solvation_stage,
)
from .orchestrate import setup_pfas_md

__version__ = "0.1.0"
__all__ = [
    "PFASSpecies",
    "PFASLigandError",
    "PFAS_SPECIES",
    "get_pfas_species",
    "LigandPlacement",
    "render_ligpargen_molecules_txt",
    "render_ligpargen_build_script",
    "merge_biochar_pfas_topology",
    "build_pre_solvation_stage",
    "setup_pfas_md",
]
