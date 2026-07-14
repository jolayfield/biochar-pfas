"""
Tests for the `biochar-pfas` command-line interface (`build-inputs`).

`build-inputs` is the primary operator entry point for the remote ligand-build
step: it renders `molecules.txt` + `build_pfas_ligands.sh` for a set of PFAS
species. No `ligpargen`/`gmx` is invoked; these checks only look at the files
the CLI writes and the exit behaviour on bad input.
"""

import pytest

from biochar_pfas.cli import main


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
