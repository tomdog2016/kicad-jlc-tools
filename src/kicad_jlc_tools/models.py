from dataclasses import dataclass, field
from enum import Enum


class MatchStatus(Enum):
    PENDING = "pending"
    MATCHED = "matched"
    NO_MATCH = "no_match"
    MANUAL = "manual"
    SKIP = "skip"


@dataclass
class Component:
    ref: str = ""
    value: str = ""
    footprint: str = ""
    footprint_full: str = ""
    lib_id: str = ""
    lcsc: str = ""
    manufacturer: str = ""
    part_number: str = ""
    description: str = ""
    stock: str = ""
    jlc_package: str = ""
    status: MatchStatus = MatchStatus.PENDING

    @property
    def footprint_short(self) -> str:
        if ":" in self.footprint:
            return self.footprint.split(":")[-1]
        return self.footprint


@dataclass
class MatchResult:
    lcsc: str = ""
    manufacturer: str = ""
    part_number: str = ""
    description: str = ""
    package: str = ""
    stock: str = ""
    match_pass: int = 0
