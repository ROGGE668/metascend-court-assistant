"""Dataclasses that represent a case archive file and its entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CaseParty:
    code: str  # PST-XXXX
    role: str  # plaintiff / defendant / third_party / judge / witness
    name: str
    description: str = ""


@dataclass
class CaseMaterial:
    code: str  # MAT-XXXX
    title: str
    content: str
    file_path: str | None = None
    created_at: str = ""


@dataclass
class CaseEvidence:
    code: str  # EVD-XXXX
    title: str
    description: str
    evidence_type: str = "document"  # document / audio / video / physical / witness
    source_party_code: str | None = None
    file_path: str | None = None
    tags: list[str] = field(default_factory=list)


@dataclass
class CaseAppeal:
    code: str  # APL-XXXX
    title: str
    content: str
    appeal_type: str = "complaint"  # complaint / answer / counterclaim / appeal
    created_at: str = ""


@dataclass
class CaseRelatedCase:
    code: str  # RCS-XXXX
    title: str
    source: str
    summary: str
    reference_laws: list[str] = field(default_factory=list)


@dataclass
class CaseLegalClause:
    code: str  # LAW-XXXX
    title: str
    content: str
    law_source: str = ""
    tags: list[str] = field(default_factory=list)


@dataclass
class CaseFact:
    code: str  # FAC-XXXX
    content: str


@dataclass
class CaseArgument:
    code: str  # ARG-XXXX
    content: str


@dataclass
class CaseFile:
    case_id: str  # CASE-YYYY-NNNN
    case_type: str  # loan / divorce / labor / contract / other
    title: str
    created_at: str
    updated_at: str
    parties: list[CaseParty] = field(default_factory=list)
    facts: list[CaseFact] = field(default_factory=list)
    materials: list[CaseMaterial] = field(default_factory=list)
    evidence: list[CaseEvidence] = field(default_factory=list)
    appeals: list[CaseAppeal] = field(default_factory=list)
    related_cases: list[CaseRelatedCase] = field(default_factory=list)
    legal_clauses: list[CaseLegalClause] = field(default_factory=list)
    strategy_notes: list[CaseArgument] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "case_type": self.case_type,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "parties": [
                {"code": p.code, "role": p.role, "name": p.name, "description": p.description}
                for p in self.parties
            ],
            "facts": [{"code": f.code, "content": f.content} for f in self.facts],
            "materials": [
                {
                    "code": m.code,
                    "title": m.title,
                    "content": m.content,
                    "file_path": m.file_path,
                    "created_at": m.created_at,
                }
                for m in self.materials
            ],
            "evidence": [
                {
                    "code": e.code,
                    "title": e.title,
                    "description": e.description,
                    "evidence_type": e.evidence_type,
                    "source_party_code": e.source_party_code,
                    "file_path": e.file_path,
                    "tags": e.tags,
                }
                for e in self.evidence
            ],
            "appeals": [
                {
                    "code": a.code,
                    "title": a.title,
                    "content": a.content,
                    "appeal_type": a.appeal_type,
                    "created_at": a.created_at,
                }
                for a in self.appeals
            ],
            "related_cases": [
                {
                    "code": r.code,
                    "title": r.title,
                    "source": r.source,
                    "summary": r.summary,
                    "reference_laws": r.reference_laws,
                }
                for r in self.related_cases
            ],
            "legal_clauses": [
                {
                    "code": clause.code,
                    "title": clause.title,
                    "content": clause.content,
                    "law_source": clause.law_source,
                    "tags": clause.tags,
                }
                for clause in self.legal_clauses
            ],
            "strategy_notes": [{"code": n.code, "content": n.content} for n in self.strategy_notes],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CaseFile":
        facts_data = data.get("facts", [])
        facts: list[CaseFact]
        if facts_data and isinstance(facts_data[0], str):
            facts = [CaseFact(code=f"FAC-{i+1:04d}", content=f) for i, f in enumerate(facts_data)]
        else:
            facts = [CaseFact(**f) for f in facts_data]

        notes_data = data.get("strategy_notes", [])
        notes: list[CaseArgument]
        if notes_data and isinstance(notes_data[0], str):
            notes = [
                CaseArgument(code=f"ARG-{i+1:04d}", content=n) for i, n in enumerate(notes_data)
            ]
        else:
            notes = [CaseArgument(**n) for n in notes_data]

        return cls(
            case_id=data.get("case_id", ""),
            case_type=data.get("case_type", "other"),
            title=data.get("title", ""),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            parties=[CaseParty(**p) for p in data.get("parties", [])],
            facts=facts,
            materials=[CaseMaterial(**m) for m in data.get("materials", [])],
            evidence=[CaseEvidence(**e) for e in data.get("evidence", [])],
            appeals=[CaseAppeal(**a) for a in data.get("appeals", [])],
            related_cases=[CaseRelatedCase(**r) for r in data.get("related_cases", [])],
            legal_clauses=[CaseLegalClause(**c) for c in data.get("legal_clauses", [])],
            strategy_notes=notes,
        )

    def all_codes(self) -> list[str]:
        codes = [self.case_id]
        codes.extend(p.code for p in self.parties)
        codes.extend(m.code for m in self.materials)
        codes.extend(e.code for e in self.evidence)
        codes.extend(a.code for a in self.appeals)
        codes.extend(r.code for r in self.related_cases)
        codes.extend(c.code for c in self.legal_clauses)
        codes.extend(f.code for f in self.facts)
        codes.extend(n.code for n in self.strategy_notes)
        return codes

    def summary_text(self) -> str:
        """Return a concise text summary for legal analysis prompts."""
        lines = [f"案件类型：{self.case_type}", f"案件标题：{self.title}"]
        if self.parties:
            lines.append("当事人：" + "；".join(f"{p.name}({p.role})" for p in self.parties))
        if self.facts:
            lines.append("事实：" + "\n".join(f"{f.code} {f.content}" for f in self.facts))
        if self.evidence:
            lines.append("证据：" + "；".join(f"{e.title}({e.code})" for e in self.evidence))
        if self.appeals:
            lines.append("诉求：" + "；".join(a.title for a in self.appeals))
        if self.legal_clauses:
            lines.append(
                "关注法条：" + "；".join(f"{c.title}({c.code})" for c in self.legal_clauses)
            )
        if self.strategy_notes:
            lines.append(
                "策略笔记：" + "\n".join(f"{n.code} {n.content}" for n in self.strategy_notes)
            )
        return "\n".join(lines)
