"""
End-to-end (setup-only) test for `setup_pfas_md`.

Generates a real biochar structure, fabricates a fake pre-built ligand system,
and confirms the produced GROMACS run directory is well-formed — with the PFAS
insertion spliced in and the merged topology used from solvation onward.

No `gmx` or `ligpargen` is ever invoked; this only checks the written files.
Skips cleanly if the `biochar` library (which needs RDKit) is not importable.
"""

from pathlib import Path

import pytest

from biochar_pfas import LigandPlacement, setup_pfas_md


def _fake_ligand_system(root: Path) -> Path:
    d = root / "ligsys"
    d.mkdir()
    (d / "atomtypes.itp").write_text("[ atomtypes ]\n; fake\n")
    (d / "PFOA.itp").write_text("[ moleculetype ]\nPFOA  3\n")
    (d / "PFOA.gro").write_text("PFOA fake\n1\n    1PFOA   C1    1\n1 1 1\n")
    return d


def test_setup_pfas_md_produces_run_dir(tmp_path):
    gen_mod = pytest.importorskip("biochar.biochar_generator")

    # A small real biochar structure + GROMACS export.
    gen = gen_mod.BiocharGenerator(gen_mod.GeneratorConfig(
        target_num_carbons=30, H_C_ratio=0.5, O_C_ratio=0.1, strict=False, seed=7,
    ))
    gen.generate()
    gro, top, _itp = gen.export_gromacs(str(tmp_path / "src"), basename="mini")

    ligsys = _fake_ligand_system(tmp_path)
    run_dir = setup_pfas_md(
        gro_path=gro,
        top_path=top,
        output_dir=tmp_path / "run",
        placements=[LigandPlacement("PFOA", n_copies=3, insertion_try=200)],
        ligand_system_dir=ligsys,
        label="mini_pfoa",
    )
    run_dir = Path(run_dir)

    # Merged topology + ligand coordinate file staged into the run dir.
    assert (run_dir / "merged.top").exists()
    assert (run_dir / "PFOA.gro").exists()
    assert (run_dir / "run_pipeline.sh").exists()

    text = (run_dir / "run_pipeline.sh").read_text()
    # PFAS insertion spliced in, before solvation, with the declared counts.
    assert 'insert-molecules' in text and "PFOA.gro" in text
    assert "-nmol 3 -try 200" in text
    assert text.index("insert-molecules") < text.index('"$GMX" solvate')
    # Solvation onward uses the merged topology, not the bare biochar one.
    assert 'cp "$SIM/merged.top" "$SIM/wet.top.base"' in text
