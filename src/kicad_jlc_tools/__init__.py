"""kicad-jlc-tools: Manage JLC/LCSC part numbers in KiCad schematics."""

__version__ = "0.1.0"

from .models import Component, MatchResult, MatchStatus
from .schematic import Schematic
from .database import JLCDatabase
from .matcher import ComponentMatcher

__all__ = [
    "Component",
    "MatchResult",
    "MatchStatus",
    "Schematic",
    "JLCDatabase",
    "ComponentMatcher",
]
