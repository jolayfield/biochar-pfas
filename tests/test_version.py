"""
Guard against version drift: `biochar_pfas.__version__` must match the version
declared in pyproject.toml. (They are two declarations; this keeps them in sync
without adding a runtime dependency to parse TOML on Python < 3.11.)
"""

import re
from pathlib import Path

import biochar_pfas


def test_version_matches_pyproject():
    root = Path(biochar_pfas.__file__).resolve().parents[1]
    text = (root / "pyproject.toml").read_text()
    m = re.search(r'^\s*version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    assert m, "no `version = \"...\"` found in pyproject.toml"
    assert biochar_pfas.__version__ == m.group(1)
