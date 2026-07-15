"""`biochar-pfas` command-line interface.

Two subcommands, covering the local (setup-only) half of the workflow:

  * ``build-inputs`` — render the LigParGen ``molecules.txt`` +
    ``build_pfas_ligands.sh`` for a set of PFAS species, to be copied to the
    cluster and run there.
  * ``setup`` — merge a pre-built ligand system into a biochar structure and
    build a GROMACS run directory (wraps ``setup_pfas_md``).

Neither subcommand invokes ``ligpargen``/``gmx``; they only write files.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from .pfas_ligands import (
    PFAS_SPECIES,
    PFASLigandError,
    BiocharSeamError,
    LigandPlacement,
    get_pfas_species,
    render_ligpargen_build_script,
    render_ligpargen_molecules_txt,
    require_biochar_md_setup,
)
from .orchestrate import setup_pfas_md


def parse_placement(token: str) -> LigandPlacement:
    """Parse a ``--place SPECIES:COUNT[:TRY]`` token into a `LigandPlacement`.

    ``COUNT`` is the number of copies to insert (must be >= 1); ``TRY`` is the
    optional ``gmx insert-molecules -try`` value (>= 1, default from
    `LigandPlacement`). ``SPECIES`` must be a known PFAS species. Raises
    `PFASLigandError` with a clear message for any malformed token.
    """
    parts = token.split(":")
    if len(parts) not in (2, 3):
        raise PFASLigandError(
            f"bad --place {token!r}: expected SPECIES:COUNT[:TRY] "
            "(e.g. PFOA:4 or PFOA:4:250)"
        )
    species = get_pfas_species(parts[0])  # validates; raises for unknown species

    try:
        n_copies = int(parts[1])
    except ValueError:
        raise PFASLigandError(f"bad --place {token!r}: COUNT must be an integer")
    if n_copies < 1:
        raise PFASLigandError(f"bad --place {token!r}: COUNT must be >= 1")

    kwargs = {}
    if len(parts) == 3:
        try:
            n_try = int(parts[2])
        except ValueError:
            raise PFASLigandError(f"bad --place {token!r}: TRY must be an integer")
        if n_try < 1:
            raise PFASLigandError(f"bad --place {token!r}: TRY must be >= 1")
        kwargs["insertion_try"] = n_try

    return LigandPlacement(species_name=species.name, n_copies=n_copies, **kwargs)


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


def _setup(args) -> int:
    # Validate the user's placements first (clear, biochar-independent errors),
    # then fail fast if the installed biochar can't satisfy the md_setup seam.
    placements = [parse_placement(t) for t in args.place]
    md_setup = require_biochar_md_setup()

    cfg_kwargs = {}
    if args.ion_profile:
        cfg_kwargs["ion_profile"] = args.ion_profile
    if args.cluster:
        cfg_kwargs["cluster"] = args.cluster
    cfg = md_setup.MDSetupConfig(**cfg_kwargs)

    run_dir = setup_pfas_md(
        gro_path=args.gro,
        top_path=args.top,
        output_dir=args.output_dir,
        placements=placements,
        ligand_system_dir=args.ligand_system_dir,
        label=args.label,
        config=cfg,
    )
    print(f"Wrote run directory {run_dir}")
    print("Next: review the generated scripts, then run them by hand.")
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

    st = sub.add_parser(
        "setup",
        help="merge a ligand system into a biochar structure and build a run directory",
    )
    st.add_argument("--gro", required=True, help="biochar structure .gro")
    st.add_argument("--top", required=True, help="biochar structure .top")
    st.add_argument(
        "--ligand-system-dir", required=True,
        help="build_gromacs_system.py output dir (scp'd back from the cluster)",
    )
    st.add_argument("--output-dir", required=True, help="run directory to create")
    st.add_argument(
        "--place", action="append", required=True, metavar="SPECIES:COUNT[:TRY]",
        help="a PFAS placement, repeatable (e.g. --place PFOA:4 --place PFOS:2:250)",
    )
    st.add_argument("--label", default="pfas", help="run label (default: pfas)")
    st.add_argument(
        "--ion-profile", default=None,
        help="ion profile passed to MDSetupConfig (optional)",
    )
    st.add_argument(
        "--cluster", default=None,
        help="cluster name for MDSetupConfig (omit for a local run_pipeline.sh)",
    )
    st.set_defaults(func=_setup)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (PFASLigandError, BiocharSeamError) as exc:
        # Turn a bad placement/species or a missing biochar seam into a clean
        # argparse-style failure (message on stderr, exit 2) instead of a
        # raw traceback.
        parser.error(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
