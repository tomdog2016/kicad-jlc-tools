"""KiCad schematic reader/writer with targeted property replacement."""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Optional

from .exceptions import ComponentNotFoundError, SchematicError
from .models import Component, MatchStatus
from .parser import parse_schematic

SKIP_PREFIXES = ("TP", "MP", "FID", "PAD", "TH", "#PWR", "#FLG")


def _is_lib_symbol_def(entry: list) -> bool:
    """Check if a symbol AST node is a lib_symbol definition (has nested symbol children)."""
    for item in entry[1:]:
        if isinstance(item, list) and item and item[0] == "symbol":
            return True
    return False


class Schematic:
    """Represents a KiCad .kicad_sch file with read/write capability.

    Uses AST parsing for reading and targeted text replacement for writing,
    preserving the original file formatting.
    """

    def __init__(self, path: Path | str):
        self.path = Path(path)
        if not self.path.exists():
            raise SchematicError(f"File not found: {self.path}")
        self._raw_text: str = self.path.read_text(encoding="utf-8")
        self._ast = parse_schematic(self._raw_text)
        self._components: Optional[list[Component]] = None
        self._pending_writes: dict[str, dict[str, str]] = {}

    @classmethod
    def from_text(cls, text: str) -> Schematic:
        """Create a Schematic from raw text (for testing). Does not require a file."""
        obj = object.__new__(cls)
        obj.path = Path("")
        obj._raw_text = text
        obj._ast = parse_schematic(text)
        obj._components = None
        obj._pending_writes = {}
        return obj

    @property
    def components(self) -> list[Component]:
        """Extract and return all non-skipped components from the schematic."""
        if self._components is not None:
            return self._components

        comps: list[Component] = []
        seen: set[str] = set()

        for entry in self._ast[1:]:
            if not (isinstance(entry, list) and entry and entry[0] == "symbol"):
                continue
            if _is_lib_symbol_def(entry):
                continue

            props: dict[str, str] = {}
            lib_id = ""
            for item in entry[1:]:
                if not isinstance(item, list) or not item:
                    continue
                tag = item[0]
                if tag == "lib_id":
                    lib_id = str(item[1]) if len(item) > 1 else ""
                elif tag == "property" and len(item) >= 3:
                    prop_name = item[1]
                    prop_val = item[2]
                    if isinstance(prop_name, str) and isinstance(prop_val, str):
                        props[prop_name] = prop_val

            ref = props.get("Reference", "")
            if not ref:
                continue
            ref_upper = ref.strip().upper()
            if any(ref_upper.startswith(pfx) for pfx in SKIP_PREFIXES):
                continue
            if ref_upper in seen:
                continue
            seen.add(ref_upper)

            fp_full = props.get("Footprint", "")
            lcsc = props.get("LCSC", "") or props.get("JLC", "")
            comp = Component(
                ref=ref,
                value=props.get("Value", ""),
                footprint=fp_full,
                footprint_full=fp_full,
                lib_id=lib_id,
                lcsc=lcsc,
                status=MatchStatus.SKIP if not lcsc else MatchStatus.MANUAL,
            )
            comps.append(comp)

        self._components = comps
        return comps

    def get_component(self, ref: str) -> Optional[Component]:
        """Get a specific component by reference designator."""
        for comp in self.components:
            if comp.ref == ref:
                return comp
        return None

    def set_property(self, ref: str, property_name: str, value: str) -> bool:
        """Stage a property change for a component. Applied on save()."""
        if not self.get_component(ref):
            raise ComponentNotFoundError(f"Component not found: {ref}")
        if ref not in self._pending_writes:
            self._pending_writes[ref] = {}
        self._pending_writes[ref][property_name] = value
        return True

    def set_lcsc(self, ref: str, lcsc_code: str) -> bool:
        """Set the LCSC part number for a component."""
        return self.set_property(ref, "LCSC", lcsc_code)

    def set_footprint(self, ref: str, footprint: str) -> bool:
        """Set the footprint for a component."""
        return self.set_property(ref, "Footprint", footprint)

    def save(self, target: Optional[Path | str] = None, backup: bool = True) -> Path:
        """Apply all pending property changes and save the schematic file.

        Args:
            target: Output file path. Defaults to overwriting the original.
            backup: If True, create a .bak backup before overwriting.

        Returns:
            Path to the saved file.
        """
        if not self._pending_writes:
            return self.path

        target = Path(target) if target else self.path

        # Apply pending writes to the raw text
        updated_text = self._apply_pending_writes(self._raw_text)

        if backup and target.exists():
            backup_path = target.with_suffix(target.suffix + ".bak")
            shutil.copy2(target, backup_path)

        target.write_text(updated_text, encoding="utf-8")

        # Reset state
        self._raw_text = updated_text
        self._ast = parse_schematic(updated_text)
        self._components = None
        self._pending_writes = {}

        return target

    def _apply_pending_writes(self, text: str) -> str:
        """Apply all pending property writes using targeted text replacement."""
        lines = text.split("\n")
        updated_lines: list[str] = []
        i = 0

        while i < len(lines):
            line = lines[i]

            if "(symbol" in line and self._is_after_lib_symbols(i, lines):
                block_lines, ref, end_i = self._extract_symbol_block(lines, i)

                if ref and ref in self._pending_writes:
                    changes = self._pending_writes[ref]
                    block_lines = self._apply_changes_to_block(block_lines, changes)
                    updated_lines.extend(block_lines)
                else:
                    updated_lines.extend(block_lines)

                i = end_i
            else:
                updated_lines.append(line)
                i += 1

        return "\n".join(updated_lines)

    def _is_after_lib_symbols(self, line_idx: int, lines: list[str]) -> bool:
        """Heuristic: check if we're past the lib_symbols section."""
        for j in range(min(line_idx, 20)):
            if "(lib_symbols" in lines[j]:
                return True
        # If lib_symbols not in first 20 lines, assume it's there or not needed
        # Check if we've seen enough lines to be past it
        return line_idx > 50

    def _extract_symbol_block(
        self, lines: list[str], start: int
    ) -> tuple[list[str], Optional[str], int]:
        """Extract a symbol block from the lines, returning (block_lines, reference, end_index)."""
        block_lines: list[str] = []
        depth = 0
        reference = None
        j = start

        while j < len(lines):
            ln = lines[j]
            block_lines.append(ln)

            if '(property "Reference"' in ln:
                m = re.search(r'\(property\s+"Reference"\s+"([^"]+)"', ln)
                if m:
                    reference = m.group(1)

            depth += ln.count("(") - ln.count(")")
            if depth <= 0 and j > start:
                return block_lines, reference, j + 1
            j += 1

        return block_lines, reference, j

    def _apply_changes_to_block(
        self, block_lines: list[str], changes: dict[str, str]
    ) -> list[str]:
        """Apply property value changes to a symbol block."""
        result: list[str] = []
        properties_found: dict[str, bool] = {name: False for name in changes}

        for idx, ln in enumerate(block_lines):
            # Try to match and replace existing properties
            replaced = False
            for prop_name, new_value in changes.items():
                if f'(property "{prop_name}"' in ln:
                    properties_found[prop_name] = True
                    pattern = (
                        r'(property\s+"' + re.escape(prop_name) + r'"\s+")([^"]*)(")'
                    )
                    new_ln = re.sub(pattern, r'\1' + new_value + r'\3', ln)
                    result.append(new_ln)
                    replaced = True
                    break

            if not replaced:
                result.append(ln)

        # Insert any properties that weren't found — before the final closing paren
        missing = [
            (name, val) for name, val in changes.items() if not properties_found[name]
        ]
        if missing and len(result) >= 2:
            # The last line is the closing ) of the symbol block
            closing = result.pop()
            # Use indentation from the line before the closing paren
            indent = self._get_indent(result[-1])
            for prop_name, new_value in missing:
                new_prop = self._build_property_block(indent, prop_name, new_value)
                result.append(new_prop)
            result.append(closing)

        return result

    @staticmethod
    def _get_indent(line: str) -> str:
        """Extract the leading whitespace from a line."""
        m = re.match(r"^(\s*)", line)
        return m.group(1) if m else "\t\t\t\t"

    @staticmethod
    def _build_property_block(indent: str, name: str, value: str) -> str:
        """Build a new hidden property block for insertion."""
        return (
            f'{indent}(property "{name}" "{value}"\n'
            f"{indent}\t(at 0 0 0)\n"
            f"{indent}\t(effects\n"
            f"{indent}\t\t(font\n"
            f"{indent}\t\t\t(size 1.27 1.27)\n"
            f"{indent}\t\t)\n"
            f"{indent}\t\t(hide yes)\n"
            f"{indent}\t)\n"
            f"{indent})"
        )
