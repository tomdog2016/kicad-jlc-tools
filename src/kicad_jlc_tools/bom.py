"""BOM CSV export and import for JLC/LCSC part numbers."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Optional

from .models import Component


def export_jlc_bom(
    components: list[Component],
    output_path: Path | str,
    group: bool = True,
) -> Path:
    """Export JLCPCB-ready BOM CSV.

    Columns: Reference, Value, Footprint, LCSC Part
    If group=True, groups identical value+footprint components onto one line.
    """
    output_path = Path(output_path)
    rows = _prepare_bom_rows(components, group)

    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["Reference", "Value", "Footprint", "LCSC Part"])
        for row in rows:
            w.writerow(row)

    return output_path


def export_full_bom(
    components: list[Component],
    output_path: Path | str,
) -> Path:
    """Export full BOM CSV with all available columns."""
    output_path = Path(output_path)
    headers = [
        "Reference", "Value", "Footprint", "LCSC Part",
        "Manufacturer", "Part Number", "Description", "Stock", "Status",
    ]

    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(headers)
        for comp in components:
            w.writerow([
                comp.ref,
                comp.value,
                comp.footprint,
                comp.lcsc,
                comp.manufacturer,
                comp.part_number,
                comp.description,
                comp.stock,
                comp.status.value if hasattr(comp.status, "value") else str(comp.status),
            ])

    return output_path


def import_jlc_codes(
    components: list[Component],
    path: Path | str,
) -> tuple[int, list[str]]:
    """Import JLC/LCSC codes from a CSV or JSON file.

    Returns (count_updated, list_of_warnings).
    """
    path = Path(path)
    if path.suffix.lower() == ".json":
        return _import_json(components, path)
    return _import_csv(components, path)


def _prepare_bom_rows(
    components: list[Component], group: bool
) -> list[list[str]]:
    if not group:
        return [
            [c.ref, c.value, c.footprint, c.lcsc]
            for c in components
        ]

    groups: dict[tuple[str, str], list[str]] = {}
    group_lcsc: dict[tuple[str, str], str] = {}

    for comp in components:
        key = (comp.value, comp.footprint)
        groups.setdefault(key, []).append(comp.ref)
        group_lcsc[key] = comp.lcsc

    rows: list[list[str]] = []
    for (value, fp), refs in groups.items():
        rows.append([
            ",".join(refs),
            value,
            fp,
            group_lcsc.get((value, fp), ""),
        ])
    return rows


def _import_csv(
    components: list[Component], path: Path
) -> tuple[int, list[str]]:
    warnings: list[str] = []
    count = 0
    ref_map = {c.ref: c for c in components}

    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ref = row.get("Reference") or row.get("参考号") or row.get("Designator") or ""
            code = (
                row.get("LCSC Part")
                or row.get("JLC物料编号")
                or row.get("JLC")
                or row.get("Part Number")
                or ""
            )
            if not ref or not code:
                continue
            if ref in ref_map:
                ref_map[ref].lcsc = code
                count += 1
            else:
                warnings.append(f"Reference not found: {ref}")

    return count, warnings


def _import_json(
    components: list[Component], path: Path
) -> tuple[int, list[str]]:
    warnings: list[str] = []
    count = 0
    ref_map = {c.ref: c for c in components}

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    items = data if isinstance(data, list) else [data]
    for item in items:
        ref = item.get("reference") or item.get("Reference") or ""
        code = item.get("lcsc") or item.get("jlc_part") or item.get("JLC") or ""
        if not ref or not code:
            continue
        if ref in ref_map:
            ref_map[ref].lcsc = code
            count += 1
        else:
            warnings.append(f"Reference not found: {ref}")

    return count, warnings
