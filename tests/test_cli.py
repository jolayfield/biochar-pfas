"""
Tests for the `biochar-pfas` command-line interface (`build-inputs`).

`build-inputs` is the primary operator entry point for the remote ligand-build
step: it renders `molecules.txt` + `build_pfas_ligands.sh` for a set of PFAS
species. No `ligpargen`/`gmx` is invoked; these checks only look at the files
the CLI writes and the exit behaviour on bad input.
"""

import pytest

from biochar_pfas import LigandPlacement, PFASLigandError
from biochar_pfas.cli import main, parse_placement


class TestBuildInputs:
    def test_writes_both_files(self, tmp_path):
        rc = main(["build-inputs", "--output-dir", str(tmp_path)])
        assert rc == 0
        assert (tmp_path / "molecules.txt").exists()
        assert (tmp_path / "build_pfas_ligands.sh").exists()

    def test_default_species_renders_all_supported_pfas(self, tmp_path):
        main(["build-inputs", "--output-dir", str(tmp_path)])
        txt = (tmp_path / "molecules.txt").read_text()
        body = [ln for ln in txt.splitlines() if ln and not ln.startswith("#")]
        assert len(body) == 3
        for name in ("PFOA", "PFOS", "PFBS"):
            assert name in txt

    def test_explicit_species_restricts_to_requested_subset(self, tmp_path):
        main(["build-inputs", "--species", "PFOA", "--output-dir", str(tmp_path)])
        txt = (tmp_path / "molecules.txt").read_text()
        body = [ln for ln in txt.splitlines() if ln and not ln.startswith("#")]
        assert len(body) == 1
        assert "PFOA" in txt
        assert "PFOS" not in txt and "PFBS" not in txt

    def test_creates_nested_output_dir(self, tmp_path):
        out = tmp_path / "deeper" / "pfas_build"
        main(["build-inputs", "--output-dir", str(out)])
        assert (out / "molecules.txt").exists()

    def test_remote_outdir_reflected_in_build_script(self, tmp_path):
        main([
            "build-inputs", "--output-dir", str(tmp_path),
            "--remote-outdir", "custom_ligdir",
        ])
        script = (tmp_path / "build_pfas_ligands.sh").read_text()
        assert "custom_ligdir" in script

    def test_invalid_species_exits_with_clear_failure(self, tmp_path, capsys):
        with pytest.raises(SystemExit) as exc:
            main([
                "build-inputs", "--species", "PFXX",
                "--output-dir", str(tmp_path),
            ])
        assert exc.value.code != 0
        err = capsys.readouterr().err
        assert "PFXX" in err        # names the offending input
        assert "PFOA" in err        # lists the valid choices
        # nothing should have been written on the failure path
        assert not (tmp_path / "molecules.txt").exists()

    def test_missing_subcommand_exits(self):
        with pytest.raises(SystemExit):
            main([])


class TestParsePlacement:
    def test_two_fields(self):
        p = parse_placement("PFOA:4")
        assert isinstance(p, LigandPlacement)
        assert p.species_name == "PFOA"
        assert p.n_copies == 4
        assert p.insertion_try == 500  # default

    def test_three_fields(self):
        p = parse_placement("PFOS:2:250")
        assert (p.species_name, p.n_copies, p.insertion_try) == ("PFOS", 2, 250)

    def test_rejects_missing_count(self):
        with pytest.raises(PFASLigandError, match="SPECIES:COUNT"):
            parse_placement("PFOA")

    def test_rejects_zero_count(self):
        with pytest.raises(PFASLigandError, match="COUNT must be >= 1"):
            parse_placement("PFOA:0")

    def test_rejects_noninteger_count(self):
        with pytest.raises(PFASLigandError, match="COUNT must be an integer"):
            parse_placement("PFOA:x")

    def test_rejects_noninteger_try(self):
        with pytest.raises(PFASLigandError, match="TRY must be an integer"):
            parse_placement("PFOA:4:x")

    def test_rejects_too_many_fields(self):
        with pytest.raises(PFASLigandError, match="SPECIES:COUNT"):
            parse_placement("PFOA:4:250:oops")

    def test_rejects_unknown_species(self):
        with pytest.raises(PFASLigandError, match="PFXX"):
            parse_placement("PFXX:1")


class TestSetup:
    _COMMON = ["--gro", "g.gro", "--top", "t.top", "--ligand-system-dir", "ls"]

    def test_requires_place(self, tmp_path):
        with pytest.raises(SystemExit):
            main(["setup", *self._COMMON, "--output-dir", str(tmp_path)])

    def test_unknown_species_exits_cleanly(self, tmp_path, capsys):
        # parse_placement runs before any biochar/file access, so this fails
        # clearly even without biochar installed and touches no files.
        with pytest.raises(SystemExit) as exc:
            main([
                "setup", *self._COMMON,
                "--output-dir", str(tmp_path), "--place", "PFXX:1",
            ])
        assert exc.value.code != 0
        assert "PFXX" in capsys.readouterr().err

    def test_bad_placement_exits_cleanly(self, tmp_path, capsys):
        with pytest.raises(SystemExit):
            main([
                "setup", *self._COMMON,
                "--output-dir", str(tmp_path), "--place", "PFOA:0",
            ])
        assert "COUNT" in capsys.readouterr().err

    def test_end_to_end_builds_run_dir(self, tmp_path):
        gen_mod = pytest.importorskip("biochar.biochar_generator")
        gen = gen_mod.BiocharGenerator(gen_mod.GeneratorConfig(
            target_num_carbons=30, H_C_ratio=0.5, O_C_ratio=0.1, strict=False, seed=7,
        ))
        gen.generate()
        gro, top, _itp = gen.export_gromacs(str(tmp_path / "src"), basename="mini")

        ligsys = tmp_path / "ligsys"
        ligsys.mkdir()
        (ligsys / "atomtypes.itp").write_text("[ atomtypes ]\n; fake\n")
        (ligsys / "PFOA.itp").write_text("[ moleculetype ]\nPFOA  3\n")
        (ligsys / "PFOA.gro").write_text("PFOA fake\n1\n    1PFOA   C1    1\n1 1 1\n")

        out = tmp_path / "run"
        rc = main([
            "setup",
            "--gro", str(gro), "--top", str(top),
            "--ligand-system-dir", str(ligsys),
            "--output-dir", str(out),
            "--place", "PFOA:3:200",
            "--label", "mini_pfoa",
        ])
        assert rc == 0
        assert (out / "merged.top").exists()
        assert (out / "run_pipeline.sh").exists()
        text = (out / "run_pipeline.sh").read_text()
        assert "insert-molecules" in text and "-nmol 3 -try 200" in text
