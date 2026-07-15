"""
Smoke tests for the setup-only worked example under examples/pfas_binding/.

Loads the example's driver by path (examples/ is not an installed package) and
checks that it renders the LigParGen build inputs. No `biochar`/`gmx`/`ligpargen`
is needed — the rendering half of the flow is pure text.
"""

import importlib.util
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DRIVER = _REPO_ROOT / "examples" / "pfas_binding" / "build_inputs.py"


def _load_driver():
    spec = importlib.util.spec_from_file_location(
        "pfas_binding_build_inputs", _DRIVER
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_example_files_exist():
    assert _DRIVER.exists()
    assert (_DRIVER.parent / "README.md").exists()


def test_driver_renders_build_inputs(tmp_path):
    mod = _load_driver()
    out = mod.render(tmp_path / "pfas_build")

    molecules = (out / "molecules.txt").read_text()
    for name in ("PFOA", "PFOS", "PFBS"):
        assert name in molecules

    script = (out / "build_pfas_ligands.sh").read_text()
    assert "build_gromacs_system.py" in script
    assert "BOSSdir" in script


def test_driver_main_writes_to_output_dir(tmp_path, capsys):
    mod = _load_driver()
    rc = mod.main(["--output-dir", str(tmp_path / "out")])
    assert rc == 0
    assert (tmp_path / "out" / "molecules.txt").exists()
    assert (tmp_path / "out" / "build_pfas_ligands.sh").exists()
