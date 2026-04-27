# kicad-jlc-tools

Manage JLC/LCSC part numbers in KiCad schematics — auto-match components against the LCSC database, edit properties, and export JLCPCB-ready BOM.

## Features

- **Auto-match** schematic components to LCSC parts via local FTS5 database
- **Read & write** KiCad `.kicad_sch` files while preserving original formatting
- **BOM export** in JLCPCB-ready CSV (grouped or flat) and full-detail formats
- **Import** LCSC codes from CSV or JSON files
- **CLI and GUI** — `kicad-jlc` for scripting, `kicad-jlc-gui` for interactive editing
- **Zero runtime dependencies** — pure Python stdlib, no pip installs needed to run

## Installation

```bash
pip install .
```

For development:

```bash
pip install -e ".[dev]"
```

## Quick Start

### CLI

```bash
# Download the LCSC component database (~700 MB FTS5 SQLite)
kicad-jlc db download

# List all components in a schematic
kicad-jlc load path/to/board.kicad_sch

# Auto-match components and write LCSC codes back
kicad-jlc match path/to/board.kicad_sch --apply

# Manually set a component's LCSC code
kicad-jlc apply path/to/board.kicad_sch --ref R1 --lcsc C25744

# Export JLCPCB BOM CSV
kicad-jlc export path/to/board.kicad_sch -o bom.csv

# Export full BOM with manufacturer, stock, status, etc.
kicad-jlc export path/to/board.kicad_sch --full
```

### GUI

```bash
kicad-jlc-gui
```

Double-click any component to search the LCSC database, or use the toolbar for batch operations:

- **Open Schematic** — load a `.kicad_sch` file
- **Auto Match All** — batch match unmatched components
- **Export BOM** — save JLCPCB-ready CSV
- **Import Codes** — load LCSC codes from CSV/JSON
- **Download DB** — fetch the LCSC database

## How It Works

```
.kicad_sch  ──parse──►  Component list
                           │
                    ┌──────▼──────┐
                    │ FTS5 Search │ ◄── parts-fts5.db (LCSC catalog)
                    └──────┬──────┘
                           │
                  matched LCSC codes
                           │
              ┌────────────▼────────────┐
              │  Targeted text replace  │ ──►  .kicad_sch (preserved formatting)
              └────────────────────────┘
```

1. **Parse** — S-expression tokenizer and recursive-descent parser reads `.kicad_sch` into an AST
2. **Match** — multi-pass FTS5 search (value+footprint → value → tokens), ranked by stock
3. **Write** — targeted line-level text replacement edits properties in-place, preserving KiCad formatting and whitespace

## Project Structure

```
src/kicad_jlc_tools/
├── __init__.py        # Public API
├── models.py          # Component, MatchResult, MatchStatus dataclasses
├── parser.py          # S-expression tokenizer and parser
├── schematic.py       # KiCad .kicad_sch reader/writer
├── database.py        # JLC/LCSC FTS5 database (search, download)
├── matcher.py         # Auto-match orchestration
├── bom.py             # BOM CSV export and import
├── exceptions.py      # Custom exceptions
├── cli/main.py        # CLI entry point (kicad-jlc)
└── gui/app.py         # Tkinter GUI entry point (kicad-jlc-gui)
```

## Requirements

- Python 3.10+
- No runtime dependencies

Dev dependencies: `pytest`, `pytest-cov`, `ruff`

## License

MIT
