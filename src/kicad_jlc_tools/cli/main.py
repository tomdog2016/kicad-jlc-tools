"""CLI entry point for kicad-jlc-tools."""

from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path


def _fix_stdout_encoding():
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def main(argv: list[str] | None = None) -> int:
    _fix_stdout_encoding()
    parser = argparse.ArgumentParser(
        prog="kicad-jlc",
        description="Manage JLC/LCSC part numbers in KiCad schematics",
    )
    sub = parser.add_subparsers(dest="command")

    # load
    p_load = sub.add_parser("load", help="Load and list schematic components")
    p_load.add_argument("schematic", type=Path, help="Path to .kicad_sch file")

    # match
    p_match = sub.add_parser("match", help="Auto-match LCSC part numbers")
    p_match.add_argument("schematic", type=Path, help="Path to .kicad_sch file")
    p_match.add_argument("--db", type=Path, default=None, help="Path to parts-fts5.db")
    p_match.add_argument("--apply", action="store_true", help="Write matches back to file")

    # apply
    p_apply = sub.add_parser("apply", help="Write staged changes to schematic")
    p_apply.add_argument("schematic", type=Path, help="Path to .kicad_sch file")
    p_apply.add_argument("--ref", required=True, help="Component reference")
    p_apply.add_argument("--lcsc", default=None, help="LCSC part number")
    p_apply.add_argument("--footprint", default=None, help="New footprint")
    p_apply.add_argument("--no-backup", action="store_true", help="Skip .bak backup")

    # export
    p_export = sub.add_parser("export", help="Export BOM CSV")
    p_export.add_argument("schematic", type=Path, help="Path to .kicad_sch file")
    p_export.add_argument("-o", "--output", type=Path, default=None, help="Output CSV path")
    p_export.add_argument("--full", action="store_true", help="Export full BOM with all columns")
    p_export.add_argument("--no-group", action="store_true", help="Don't group components")

    # db
    p_db = sub.add_parser("db", help="Database management")
    db_sub = p_db.add_subparsers(dest="db_command")
    db_sub.add_parser("download", help="Download FTS5 database")
    db_sub.add_parser("info", help="Show database status")

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    try:
        if args.command == "load":
            return _cmd_load(args)
        elif args.command == "match":
            return _cmd_match(args)
        elif args.command == "apply":
            return _cmd_apply(args)
        elif args.command == "export":
            return _cmd_export(args)
        elif args.command == "db":
            return _cmd_db(args)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0


def _cmd_load(args) -> int:
    from ..schematic import Schematic

    sch = Schematic(args.schematic)
    comps = sch.components
    print(f"Loaded {len(comps)} components from {args.schematic.name}\n")
    print(f"{'Ref':<12} {'Value':<20} {'Footprint':<40} {'LCSC':<12}")
    print("-" * 86)
    for c in comps:
        print(f"{c.ref:<12} {c.value:<20} {c.footprint:<40} {c.lcsc:<12}")
    return 0


def _cmd_match(args) -> int:
    from ..database import JLCDatabase
    from ..matcher import ComponentMatcher
    from ..schematic import Schematic

    sch = Schematic(args.schematic)
    db = JLCDatabase(args.db)
    if not db.is_available:
        print("Database not found. Run 'kicad-jlc db download' first.", file=sys.stderr)
        return 1

    matcher = ComponentMatcher(db)
    comps = sch.components
    total = len(comps)

    def progress(cur, tot, ref):
        print(f"\r  Matching [{cur}/{tot}] {ref}...", end="", flush=True)

    matches = matcher.match_all(comps, progress_callback=progress)
    print()

    matched = len(matches)
    print(f"Matched {matched}/{total} components\n")

    for comp in comps:
        if comp.lcsc:
            print(f"  {comp.ref:<12} {comp.value:<20} -> {comp.lcsc}")

    if args.apply and matches:
        matcher.apply_matches(sch, matches)
        sch.save()
        print(f"\nSaved to {sch.path}")

    return 0


def _cmd_apply(args) -> int:
    from ..schematic import Schematic

    sch = Schematic(args.schematic)
    if args.lcsc:
        sch.set_lcsc(args.ref, args.lcsc)
    if args.footprint:
        sch.set_footprint(args.ref, args.footprint)
    sch.save(backup=not args.no_backup)
    print(f"Saved to {sch.path}")
    return 0


def _cmd_export(args) -> int:
    from ..bom import export_full_bom, export_jlc_bom
    from ..schematic import Schematic

    sch = Schematic(args.schematic)
    output = args.output or sch.path.with_suffix(".csv")

    if args.full:
        export_full_bom(sch.components, output)
    else:
        export_jlc_bom(sch.components, output, group=not args.no_group)

    print(f"Exported to {output}")
    return 0


def _cmd_db(args) -> int:
    from ..database import JLCDatabase

    if args.db_command == "download":
        print("Downloading JLCPCB FTS5 database...")

        def progress(chunk, total):
            print(f"\r  Downloading chunk {chunk}/{total}...", end="", flush=True)

        path = JLCDatabase.download(progress_callback=progress)
        print(f"\nDatabase saved to {path}")
    elif args.db_command == "info":
        db = JLCDatabase()
        if db.is_available:
            print(f"Database: {db.path}")
            print(f"Size: {db.db_size_mb:.1f} MB")
        else:
            print(f"Database not found at {db.path}")
            print("Run 'kicad-jlc db download' to fetch it.")
    else:
        print("Usage: kicad-jlc db [download|info]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
