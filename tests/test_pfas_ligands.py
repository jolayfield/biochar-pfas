"""
Tests for biochar_pfas.pfas_ligands — the PFAS species table, LigParGen input
rendering, biochar+ligand topology merge, and the PreSolvationStage adapter.

No `gmx`/`ligpargen` is invoked; everything here is pure file/text logic against
fabricated inputs.
"""

import pytest

from biochar_pfas.pfas_ligands import (
    PFAS_SPECIES,
    PFASLigandError,
    PFASSpecies,
    LigandPlacement,
    _split_biochar_top,
    build_pre_solvation_stage,
    get_pfas_species,
    merge_biochar_pfas_topology,
    render_ligpargen_build_script,
    render_ligpargen_molecules_txt,
)


# --------------------------------------------------------------------------- #
# Fixtures: a fake biochar .top and a fake build_gromacs_system.py ligand dir
# --------------------------------------------------------------------------- #
_BIOCHAR_TOP = """; biochar topology (fabricated for tests)
#include "oplsaa.ff/forcefield.itp"

[ moleculetype ]
; name  nrexcl
BC000   3

[ atoms ]
;   nr  type  resnr residue atom cgnr charge  mass
     1   opls_145  1  BC000  C1   1   -0.115  12.011

[ system ]
biochar

[ molecules ]
BC000   1
"""


@pytest.fixture()
def biochar_top(tmp_path):
    p = tmp_path / "bio.top"
    p.write_text(_BIOCHAR_TOP)
    return p


@pytest.fixture()
def ligand_system(tmp_path):
    """A fake build_gromacs_system.py output dir: atomtypes.itp + PFOA/PFOS."""
    d = tmp_path / "ligsys"
    d.mkdir()
    (d / "atomtypes.itp").write_text("[ atomtypes ]\n; fake\n")
    for name in ("PFOA", "PFOS"):
        (d / f"{name}.itp").write_text(f"[ moleculetype ]\n{name}  3\n")
        (d / f"{name}.gro").write_text(f"{name} fake gro\n1\n    1{name}   C1    1\n1 1 1\n")
    return d


# --------------------------------------------------------------------------- #
# Species table
# --------------------------------------------------------------------------- #
class TestSpecies:
    def test_three_pfas_present_as_anions(self):
        for n in ("PFOA", "PFOS", "PFBS"):
            assert n in PFAS_SPECIES
            assert PFAS_SPECIES[n].formal_charge == -1
            assert PFAS_SPECIES[n].charge_model == "CM1A"  # CM1A-LBCC is neutral-only

    def test_get_by_name_and_passthrough(self):
        assert get_pfas_species("PFOA") is PFAS_SPECIES["PFOA"]
        custom = PFASSpecies(name="X", smiles="C", formal_charge=0, resname="X")
        assert get_pfas_species(custom) is custom

    def test_unknown_species_raises(self):
        with pytest.raises(PFASLigandError):
            get_pfas_species("PFXX")


# --------------------------------------------------------------------------- #
# LigParGen input rendering
# --------------------------------------------------------------------------- #
class TestRendering:
    def test_molecules_txt_has_one_line_per_species(self):
        txt = render_ligpargen_molecules_txt([PFAS_SPECIES["PFOA"], PFAS_SPECIES["PFBS"]])
        body = [ln for ln in txt.splitlines() if ln and not ln.startswith("#")]
        assert len(body) == 2
        assert "PFOA" in txt and "PFBS" in txt and "CM1A" in txt

    def test_bad_species_name_rejected(self):
        bad = PFASSpecies(name="PF-OA", smiles="C", formal_charge=-1, resname="PFOA")
        with pytest.raises(PFASLigandError):
            render_ligpargen_molecules_txt([bad])

    def test_build_script_mentions_species_and_boss(self):
        script = render_ligpargen_build_script([PFAS_SPECIES["PFOA"]])
        assert "build_gromacs_system.py" in script
        assert "BOSSdir" in script
        assert "PFOA" in script


# --------------------------------------------------------------------------- #
# _split_biochar_top
# --------------------------------------------------------------------------- #
class TestSplitTop:
    def test_splits_valid_top(self):
        header, body, name = _split_biochar_top(_BIOCHAR_TOP)
        assert "forcefield.itp" in header
        assert "[ moleculetype ]" in body
        assert name == "BC000"

    def test_malformed_top_raises(self):
        with pytest.raises(PFASLigandError):
            _split_biochar_top("just some text with no gromacs sections")


# --------------------------------------------------------------------------- #
# merge_biochar_pfas_topology — happy path + every documented error
# --------------------------------------------------------------------------- #
class TestMerge:
    def test_happy_path(self, biochar_top, ligand_system, tmp_path):
        placements = [LigandPlacement("PFOA", n_copies=4),
                      LigandPlacement("PFOS", n_copies=2)]
        out = tmp_path / "merged"
        result = merge_biochar_pfas_topology(biochar_top, ligand_system, placements, out)

        merged_top = result["top_path"]
        assert merged_top.exists()
        assert result["ligand_gro_names"] == {"PFOA": "PFOA.gro", "PFOS": "PFOS.gro"}
        # ligand files copied alongside
        for f in ("atomtypes.itp", "PFOA.itp", "PFOA.gro", "PFOS.itp", "PFOS.gro"):
            assert (out / f).exists()
        text = merged_top.read_text()
        assert '#include "atomtypes.itp"' in text
        assert '#include "PFOA.itp"' in text
        # [ molecules ] has biochar + requested copy counts
        assert "BC000" in text
        assert "PFOA" in text and " 4" in text
        assert "PFOS" in text and " 2" in text

    def test_missing_atomtypes_raises(self, biochar_top, tmp_path):
        empty = tmp_path / "empty"; empty.mkdir()
        with pytest.raises(PFASLigandError, match="atomtypes"):
            merge_biochar_pfas_topology(
                biochar_top, empty, [LigandPlacement("PFOA")], tmp_path / "o")

    def test_missing_species_files_raise(self, biochar_top, ligand_system, tmp_path):
        with pytest.raises(PFASLigandError, match="PFBS"):
            merge_biochar_pfas_topology(
                biochar_top, ligand_system, [LigandPlacement("PFBS")], tmp_path / "o")

    def test_duplicate_species_raises(self, biochar_top, ligand_system, tmp_path):
        with pytest.raises(PFASLigandError, match="duplicate"):
            merge_biochar_pfas_topology(
                biochar_top, ligand_system,
                [LigandPlacement("PFOA"), LigandPlacement("PFOA")], tmp_path / "o")

    def test_zero_copies_raises(self, biochar_top, ligand_system, tmp_path):
        with pytest.raises(PFASLigandError, match="n_copies"):
            merge_biochar_pfas_topology(
                biochar_top, ligand_system, [LigandPlacement("PFOA", n_copies=0)],
                tmp_path / "o")

    def test_empty_placements_raises(self, biochar_top, ligand_system, tmp_path):
        with pytest.raises(PFASLigandError):
            merge_biochar_pfas_topology(biochar_top, ligand_system, [], tmp_path / "o")

    def test_missing_biochar_top_raises(self, ligand_system, tmp_path):
        with pytest.raises(PFASLigandError):
            merge_biochar_pfas_topology(
                tmp_path / "nope.top", ligand_system, [LigandPlacement("PFOA")],
                tmp_path / "o")


# --------------------------------------------------------------------------- #
# build_pre_solvation_stage — the adapter into biochar's generic seam
# --------------------------------------------------------------------------- #
class TestPreSolvationStageAdapter:
    def test_maps_merge_result_to_stage(self, biochar_top, ligand_system, tmp_path):
        biochar_md = pytest.importorskip("biochar.md_setup")
        if not hasattr(biochar_md, "PreSolvationStage"):
            pytest.skip("installed biochar lacks the PreSolvationStage seam")

        placements = [LigandPlacement("PFOA", n_copies=4, insertion_try=250),
                      LigandPlacement("PFOS", n_copies=2)]
        out = tmp_path / "merged"
        merge_result = merge_biochar_pfas_topology(biochar_top, ligand_system, placements, out)
        stage = build_pre_solvation_stage(placements, merge_result)

        assert isinstance(stage, biochar_md.PreSolvationStage)
        assert stage.solvation_top == "merged.top"
        # one MoleculeInsertion per placement, carrying counts through
        assert [(i.gro_file, i.n_copies, i.n_try) for i in stage.insertions] == [
            ("PFOA.gro", 4, 250), ("PFOS.gro", 2, 500),
        ]
        # extra_files point at real, existing files to stage into the run dir
        from pathlib import Path
        for f in stage.extra_files:
            assert Path(f).exists()
        names = {Path(f).name for f in stage.extra_files}
        assert {"merged.top", "atomtypes.itp", "PFOA.itp", "PFOA.gro"} <= names
