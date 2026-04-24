"""Component matching orchestration: tie schematic components to FTS5 database search."""

from __future__ import annotations

from typing import Optional

from .database import JLCDatabase
from .models import Component, MatchResult, MatchStatus
from .schematic import Schematic


class ComponentMatcher:
    """Matches schematic components to JLC/LCSC parts using the FTS5 database."""

    def __init__(self, db: JLCDatabase):
        self.db = db

    def match_one(self, component: Component) -> Optional[MatchResult]:
        """Match a single component. Returns the best MatchResult or None."""
        if not self.db.is_available:
            return None
        results = self.db.search(component.value, component.footprint, limit=1)
        return results[0] if results else None

    def match_all(
        self,
        components: list[Component],
        skip_matched: bool = True,
        progress_callback=None,
    ) -> dict[str, MatchResult]:
        """Match all components. Returns {ref: MatchResult}.

        Args:
            components: List of components to match.
            skip_matched: Skip components that already have an LCSC code.
            progress_callback: Called as progress_callback(current, total, ref).
        """
        matches: dict[str, MatchResult] = {}
        total = len(components)

        for idx, comp in enumerate(components):
            if skip_matched and comp.lcsc:
                if progress_callback:
                    progress_callback(idx + 1, total, comp.ref)
                continue

            result = self.match_one(comp)
            if result:
                matches[comp.ref] = result
                comp.lcsc = result.lcsc
                comp.manufacturer = result.manufacturer
                comp.part_number = result.part_number
                comp.description = result.description
                comp.stock = result.stock
                comp.jlc_package = result.package
                comp.status = MatchStatus.MATCHED
            else:
                comp.status = MatchStatus.NO_MATCH

            if progress_callback:
                progress_callback(idx + 1, total, comp.ref)

        return matches

    def apply_matches(
        self,
        schematic: Schematic,
        matches: dict[str, MatchResult],
        include_footprint: bool = False,
    ) -> int:
        """Apply match results to the schematic (stages changes for save).

        Writes LCSC property. Optionally writes JLC package as footprint.

        Returns the count of properties written.
        """
        count = 0
        for ref, match in matches.items():
            try:
                schematic.set_lcsc(ref, match.lcsc)
                count += 1
                if include_footprint and match.package:
                    schematic.set_footprint(ref, match.package)
            except Exception:
                pass
        return count
