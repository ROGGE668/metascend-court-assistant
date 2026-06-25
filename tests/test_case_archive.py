"""Tests for case archive encoding, models, and store."""

import tempfile
from pathlib import Path

import pytest

from src.case_archive import CaseArchive
from src.case_archive.encoding import CodeRegistry, EntityCode
from src.case_archive.models import CaseFact, CaseFile


def test_entity_code_str():
    code = EntityCode("EVD", 3)
    assert str(code) == "EVD-0003"


def test_entity_code_parse():
    code = EntityCode.parse("LAW-0042")
    assert code.prefix == "LAW"
    assert code.sequence == 42


def test_code_registry_generates_sequential_codes():
    registry = CodeRegistry("CASE-2026-0001")
    assert registry.next_code("evidence") == "EVD-0001"
    assert registry.next_code("evidence") == "EVD-0002"
    assert registry.next_code("party") == "PST-0001"


def test_code_registry_seeds_existing_codes():
    registry = CodeRegistry("CASE-2026-0001")
    registry.seed(["EVD-0005", "PST-0002"])
    assert registry.next_code("evidence") == "EVD-0006"
    assert registry.next_code("party") == "PST-0003"


def test_case_file_summary_contains_entities():
    case = CaseFile(
        case_id="CASE-2026-0001",
        case_type="loan",
        title="张三诉李四民间借贷纠纷",
        created_at="",
        updated_at="",
    )
    summary = case.summary_text()
    assert "民间借贷" in summary
    assert "张三诉李四民间借贷纠纷" in summary


def test_case_archive_crud():
    with tempfile.TemporaryDirectory() as tmp:
        archive = CaseArchive(base_dir=Path(tmp))
        case = archive.create_case("测试案件", "loan")
        assert case.case_id.startswith("CASE-")
        assert case.title == "测试案件"

        party = archive.add_party(case.case_id, "plaintiff", "张三", "原告")
        assert party.code.startswith("PST-")
        evidence = archive.add_evidence(case.case_id, "借条", "借款凭证", "document")
        assert evidence.code.startswith("EVD-")

        loaded = archive.load(case.case_id)
        assert loaded is not None
        assert loaded.title == "测试案件"
        assert len(loaded.parties) == 1
        assert len(loaded.evidence) == 1

        cases = archive.list_cases()
        assert len(cases) == 1
        assert cases[0]["case_id"] == case.case_id

        archive.delete(case.case_id)
        assert archive.load(case.case_id) is None


def test_case_archive_save_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        archive = CaseArchive(base_dir=Path(tmp))
        case = archive.create_case("roundtrip", "contract")
        archive.set_facts(case.case_id, ["事实一", "事实二"])

        loaded = archive.load(case.case_id)
        assert loaded is not None
        assert len(loaded.facts) == 2
        assert all(isinstance(f, CaseFact) for f in loaded.facts)
        assert [f.content for f in loaded.facts] == ["事实一", "事实二"]
        assert all(f.code.startswith("FAC-") for f in loaded.facts)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
