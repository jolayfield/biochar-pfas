"""`biochar-pfas` command-line interface.

Currently exposes the first step of the workflow: rendering the LigParGen
`molecules.txt` + `build_pfas_ligands.sh` for a set of PFAS species, to be
copied to the cluster and run there (this never invokes ligpargen/gmx).
"""

from __future__ import annotations

import argparse
from pathlib import Path

from .pfas_ligands import (
    PFAS_SPECIES,
    get_pfas_species,
    render_ligpargen_build_script,
    render_ligpargen_molecules_txt,
)


def _build_inputs(args) -> int:
    species = [get_pfas_species(n) for n in args.species]
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "molecules.txt").write_text(render_ligpargen_molecules_txt(species))
    (out / "build_pfas_ligands.sh").write_text(
        render_ligpargen_build_script(species, remote_outdir=args.remote_outdir)
    )
    print(f"Wrote {out/'molecules.txt'} and {out/'build_pfas_ligands.sh'}")
    print("Next: scp that directory to the cluster and run build_pfas_ligands.sh there.")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="biochar-pfas", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    bi = sub.add_parser(
        "build-inputs",
        help="render molecules.txt + build_pfas_ligands.sh for LigParGen (run on cluster)",
    )
    bi.add_argument(
        "--species", nargs="+", default=sorted(PFAS_SPECIES),
        metavar="NAME", help=f"PFAS species (default: all -- {sorted(PFAS_SPECIES)})",
    )
    bi.add_argument("--output-dir", default="pfas_build", help="where to write the inputs")
    bi.add_argument(
        "--remote-outdir", default="pfas_ligands_gmx",
        help="directory the cluster build script writes ligand topologies into",
    )
    bi.set_defaults(func=_build_inputs)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
