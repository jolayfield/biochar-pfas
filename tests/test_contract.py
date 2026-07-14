"""
Tests for the biochar seam contract — `require_biochar_md_setup`.

`biochar-pfas` consumes `biochar` only through a handful of `biochar.md_setup`
symbols. These tests verify the fail-fast behaviour when the installed `biochar`
can't satisfy that seam, using `sys.modules` injection so they run whether or
not a real `biochar` is installed (no `gmx`/`ligpargen`, no heavy mocking).
"""

import sys
import types

import pytest

from biochar_pfas.pfas_ligands import (
    REQUIRED_MD_SETUP_SYMBOLS,
    BiocharSeamError,
    require_biochar_md_setup,
)


def _fake_md_setup(symbols):
    """A stand-in `biochar.md_setup` exposing exactly `symbols`."""
    mod = types.ModuleType("biochar.md_setup")
    for s in symbols:
        setattr(mod, s, object())
    return mod


def _install_fake_biochar(monkeypatch, md_setup_module):
    pkg = types.ModuleType("biochar")
    pkg.md_setup = md_setup_module
    monkeypatch.setitem(sys.modules, "biochar", pkg)
    monkeypatch.setitem(sys.modules, "biochar.md_setup", md_setup_module)


class TestSeamContract:
    def test_all_symbols_present_returns_module(self, monkeypatch):
        md = _fake_md_setup(REQUIRED_MD_SETUP_SYMBOLS)
        _install_fake_biochar(monkeypatch, md)
        assert require_biochar_md_setup() is md

    def test_missing_symbol_raises_named(self, monkeypatch):
        present = [s for s in REQUIRED_MD_SETUP_SYMBOLS if s != "PreSolvationStage"]
        md = _fake_md_setup(present)
        _install_fake_biochar(monkeypatch, md)
        with pytest.raises(BiocharSeamError, match="PreSolvationStage"):
            require_biochar_md_setup()

    def test_biochar_not_importable_raises_install_hint(self, monkeypatch):
        # None in sys.modules makes `import biochar` raise ImportError.
        monkeypatch.setitem(sys.modules, "biochar", None)
        monkeypatch.delitem(sys.modules, "biochar.md_setup", raising=False)
        with pytest.raises(BiocharSeamError, match="pip install"):
            require_biochar_md_setup()

    def test_seam_error_is_an_import_error(self):
        # Narrow + catchable by existing `except ImportError` handlers.
        assert issubclass(BiocharSeamError, ImportError)

    def test_required_symbols_are_the_documented_four(self):
        assert set(REQUIRED_MD_SETUP_SYMBOLS) == {
            "MDSetupConfig",
            "PreSolvationStage",
            "MoleculeInsertion",
            "setup_one_structure",
        }
