#!/usr/bin/env python3
"""Render the LigParGen build inputs for the PFAS-binding example.

Setup-only: writes ``molecules.txt`` + ``build_pfas_ligands.sh`` for
PFOA / PFOS / PFBS into an output directory. Nothing here runs
``ligpargen``/``gmx`` — see this directory's README.md for the full flow and
the cluster handoff.

    python examples/pfas_binding/build_inputs.py --output-dir pfas_build
"""

from __future__ import annotations

import argparse
from pathlib import Path

from biochar_pfas import (
    PFAS_SPECIES,
    render_ligpargen_build_script,
    render_ligpargen_molecules_txt,
)

#: The three PFAS this example parametrizes (all deprotonated anions).
SPECIES = ["PFOA", "PFOS", "PFBS"]


def render(output_dir: Path) -> Path:
    """Write molecules.txt + build_pfas_ligands.sh into ``output_dir``."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    species = [PFAS_SPECIES[name] for name in SPECIES]
    (output_dir / "molecules.txt").write_text(
        render_ligpargen_molecules_txt(species)
    )
    (output_dir / "build_pfas_ligands.sh").write_text(
        render_ligpargen_build_script(species)
    )
    return output_dir


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--output-dir", default="pfas_build", type=Path,
        help="where to write the inputs (default: ./pfas_build)",
    )
    args = ap.parse_args(argv)
    out = render(args.output_dir)
    print(f"Wrote {out / 'molecules.txt'} and {out / 'build_pfas_ligands.sh'}")
    print("Next: scp that directory to the cluster and run build_pfas_ligands.sh there.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
