"""CRUD for case archive files on local disk."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.case_archive.encoding import CodeRegistry
from src.case_archive.models import (
    CaseAppeal,
    CaseArgument,
    CaseEvidence,
    CaseFact,
    CaseFile,
    CaseLegalClause,
    CaseMaterial,
    CaseParty,
    CaseRelatedCase,
)
from src.config import Config

logger = logging.getLogger(__name__)


class CaseArchive:
    """Manage case files under data/cases/.

    Each case is a JSON file named {case_id}.json.  The archive exposes a
    simple CRUD interface and auto-generates unified entity codes.
    """

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or Config.DATA_DIR / "cases"
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, case_id: str) -> Path:
        safe = Path(case_id).name
        return (self.base_dir / f"{safe}.json").resolve()

    def list_cases(self) -> list[dict[str, Any]]:
        cases: list[dict[str, Any]] = []
        for path in sorted(self.base_dir.glob("*.json")):
            try:
                with open(path, encoding="utf-8") as fp:
                    data = json.load(fp)
                cases.append(
                    {
                        "case_id": data.get("case_id", path.stem),
                        "case_type": data.get("case_type", "other"),
                        "title": data.get("title", path.stem),
                        "updated_at": data.get("updated_at", ""),
                    }
                )
            except Exception as e:
                logger.warning("Failed to list case %s: %s", path, e)
        return cases

    def create_case(self, title: str, case_type: str = "other") -> CaseFile:
        now = datetime.now(timezone.utc).isoformat()
        case_id = CodeRegistry.generate_case_id()
        case = CaseFile(
            case_id=case_id,
            case_type=case_type,
            title=title,
            created_at=now,
            updated_at=now,
        )
        self._save(case)
        return case

    def load(self, case_id: str) -> CaseFile | None:
        path = self._path(case_id)
        if not path.exists():
            return None
        try:
            with open(path, encoding="utf-8") as fp:
                data = json.load(fp)
            return CaseFile.from_dict(data)
        except Exception as e:
            logger.exception("Failed to load case %s", case_id)
            raise RuntimeError(f"Failed to load case {case_id}: {e}") from e

    def save(self, case: CaseFile) -> None:
        case.updated_at = datetime.now(timezone.utc).isoformat()
        self._save(case)

    def _save(self, case: CaseFile) -> None:
        path = self._path(case.case_id)
        with open(path, "w", encoding="utf-8") as fp:
            json.dump(case.to_dict(), fp, ensure_ascii=False, indent=2)

    def delete(self, case_id: str) -> bool:
        path = self._path(case_id)
        if path.exists():
            path.unlink()
            return True
        return False

    def _registry(self, case: CaseFile) -> CodeRegistry:
        registry = CodeRegistry(case.case_id)
        registry.seed(case.all_codes())
        return registry

    # ------------------------------------------------------------------ #
    # Entity helpers
    # ------------------------------------------------------------------ #
    def add_party(
        self,
        case_id: str,
        role: str,
        name: str,
        description: str = "",
    ) -> CaseParty:
        case = self.load(case_id)
        if case is None:
            raise FileNotFoundError(f"Case not found: {case_id}")
        registry = self._registry(case)
        party = CaseParty(
            code=registry.next_code("party"),
            role=role,
            name=name,
            description=description,
        )
        case.parties.append(party)
        self.save(case)
        return party

    def add_material(
        self,
        case_id: str,
        title: str,
        content: str,
        file_path: str | None = None,
    ) -> CaseMaterial:
        case = self.load(case_id)
        if case is None:
            raise FileNotFoundError(f"Case not found: {case_id}")
        registry = self._registry(case)
        material = CaseMaterial(
            code=registry.next_code("material"),
            title=title,
            content=content,
            file_path=file_path,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        case.materials.append(material)
        self.save(case)
        return material

    def add_evidence(
        self,
        case_id: str,
        title: str,
        description: str,
        evidence_type: str = "document",
        source_party_code: str | None = None,
        file_path: str | None = None,
        tags: list[str] | None = None,
    ) -> CaseEvidence:
        case = self.load(case_id)
        if case is None:
            raise FileNotFoundError(f"Case not found: {case_id}")
        registry = self._registry(case)
        evidence = CaseEvidence(
            code=registry.next_code("evidence"),
            title=title,
            description=description,
            evidence_type=evidence_type,
            source_party_code=source_party_code,
            file_path=file_path,
            tags=tags or [],
        )
        case.evidence.append(evidence)
        self.save(case)
        return evidence

    def add_appeal(
        self,
        case_id: str,
        title: str,
        content: str,
        appeal_type: str = "complaint",
    ) -> CaseAppeal:
        case = self.load(case_id)
        if case is None:
            raise FileNotFoundError(f"Case not found: {case_id}")
        registry = self._registry(case)
        appeal = CaseAppeal(
            code=registry.next_code("appeal"),
            title=title,
            content=content,
            appeal_type=appeal_type,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        case.appeals.append(appeal)
        self.save(case)
        return appeal

    def add_related_case(
        self,
        case_id: str,
        title: str,
        source: str,
        summary: str,
        reference_laws: list[str] | None = None,
    ) -> CaseRelatedCase:
        case = self.load(case_id)
        if case is None:
            raise FileNotFoundError(f"Case not found: {case_id}")
        registry = self._registry(case)
        related = CaseRelatedCase(
            code=registry.next_code("related_case"),
            title=title,
            source=source,
            summary=summary,
            reference_laws=reference_laws or [],
        )
        case.related_cases.append(related)
        self.save(case)
        return related

    def add_legal_clause(
        self,
        case_id: str,
        title: str,
        content: str,
        law_source: str = "",
        tags: list[str] | None = None,
    ) -> CaseLegalClause:
        case = self.load(case_id)
        if case is None:
            raise FileNotFoundError(f"Case not found: {case_id}")
        registry = self._registry(case)
        clause = CaseLegalClause(
            code=registry.next_code("legal_clause"),
            title=title,
            content=content,
            law_source=law_source,
            tags=tags or [],
        )
        case.legal_clauses.append(clause)
        self.save(case)
        return clause

    def set_facts(self, case_id: str, facts: list[str]) -> None:
        case = self.load(case_id)
        if case is None:
            raise FileNotFoundError(f"Case not found: {case_id}")
        registry = self._registry(case)
        case.facts = [CaseFact(code=registry.next_code("fact"), content=f) for f in facts]
        self.save(case)

    def add_fact(self, case_id: str, content: str) -> CaseFact:
        case = self.load(case_id)
        if case is None:
            raise FileNotFoundError(f"Case not found: {case_id}")
        registry = self._registry(case)
        fact = CaseFact(code=registry.next_code("fact"), content=content)
        case.facts.append(fact)
        self.save(case)
        return fact

    def add_strategy_note(self, case_id: str, note: str) -> CaseArgument:
        case = self.load(case_id)
        if case is None:
            raise FileNotFoundError(f"Case not found: {case_id}")
        registry = self._registry(case)
        argument = CaseArgument(code=registry.next_code("argument"), content=note)
        case.strategy_notes.append(argument)
        self.save(case)
        return argument
