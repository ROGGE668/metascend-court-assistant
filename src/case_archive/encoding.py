"""Unified rule-based encoding for case archive entities.

Codes allow every module (ASR hotwords, legal intent, strategy generation,
evidence tracking) to reference a single case entity unambiguously.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class EntityCode:
    """Typed entity code: prefix + sequence, e.g. EVD-0003."""

    prefix: str
    sequence: int

    def __str__(self) -> str:
        return f"{self.prefix}-{self.sequence:04d}"

    @classmethod
    def parse(cls, code: str) -> "EntityCode":
        match = re.match(r"^([A-Z]{3})-(\d{4})$", code)
        if not match:
            raise ValueError(f"Invalid entity code: {code}")
        return cls(prefix=match.group(1), sequence=int(match.group(2)))


class CodeRegistry:
    """Generate and track codes within a case file.

    Prefix reference:
        CASE - case itself
        PST  - party (plaintiff/defendant/judge/third_party)
        MAT  - material/document
        EVD  - evidence
        APL  - appeal/complaint/answer document
        RCS  - related case
        LAW  - legal clause
        FAC  - fact statement
        ARG  - argument/strategy note
    """

    PREFIXES = {
        "case": "CASE",
        "party": "PST",
        "material": "MAT",
        "evidence": "EVD",
        "appeal": "APL",
        "related_case": "RCS",
        "legal_clause": "LAW",
        "fact": "FAC",
        "argument": "ARG",
    }

    def __init__(self, case_id: str) -> None:
        self.case_id = case_id
        self._counters: dict[str, int] = {prefix: 0 for prefix in self.PREFIXES.values()}

    @classmethod
    def generate_case_id(cls) -> str:
        """Generate a new case id: CASE-YYYY-NNNN."""
        year = datetime.now(timezone.utc).year
        # Use a deterministic seed based on timestamp for uniqueness in MVP.
        seq = int(datetime.now(timezone.utc).timestamp()) % 10000
        return f"CASE-{year}-{seq:04d}"

    def next_code(self, entity_type: str) -> str:
        prefix = self.PREFIXES.get(entity_type)
        if prefix is None:
            raise ValueError(f"Unknown entity type: {entity_type}")
        self._counters[prefix] += 1
        return str(EntityCode(prefix, self._counters[prefix]))

    def seed(self, existing_codes: list[str]) -> None:
        """Advance counters so newly generated codes do not collide."""
        for code in existing_codes:
            try:
                entity = EntityCode.parse(code)
            except ValueError:
                continue
            if entity.prefix in self._counters:
                self._counters[entity.prefix] = max(self._counters[entity.prefix], entity.sequence)
