"""Tests for the legal reasoning modules."""

import pytest

from src.case_archive.models import CaseFile, CaseLegalClause
from src.data_types import LegalIntent, Strategy
from src.legal.intent_extractor import RuleHeuristicLegalIntentExtractor
from src.legal.risk_filter import StrategyRiskFilter
from src.legal.strategy_generator import StrategyGenerator


def test_intent_extractor_detects_loan_case():
    extractor = RuleHeuristicLegalIntentExtractor()
    intent = extractor.extract("我要求被告归还借款本金五万元及利息")
    assert intent.case_type == "借贷"
    assert intent.claim is not None
    assert intent.legal_ground is not None


def test_intent_extractor_detects_objection():
    extractor = RuleHeuristicLegalIntentExtractor()
    intent = extractor.extract("我对这份证据有异议，不认可其真实性")
    assert intent.objection is True


def test_risk_filter_blocks_high_risk_output():
    risk_filter = StrategyRiskFilter()
    strategy = Strategy(text="你这个混蛋，胡说八道")
    result = risk_filter.filter(strategy)
    assert result.risk_level == "high"
    assert "已过滤" in result.text


def test_risk_filter_marks_medium_risk_output():
    risk_filter = StrategyRiskFilter()
    strategy = Strategy(text="你在撒谎，根本没有这回事")
    result = risk_filter.filter(strategy)
    assert result.risk_level == "medium"
    assert "注意语气" in result.text


class _FakeKB:
    def __init__(self, docs):
        self._docs = docs

    def retrieve(self, query: str, top_k: int = 3):
        return self._docs[:top_k]


class _FakeLLM:
    def __init__(self, reply: str | None):
        self._reply = reply

    def complete(self, prompt: str) -> str | None:
        return self._reply


def test_strategy_generator_uses_rule_template():
    kb = _FakeKB([{"law": "《民法典》第679条", "content": "借款合同自贷款人提供借款时成立"}])
    generator = StrategyGenerator(kb=kb, llm=None)
    intent = LegalIntent(
        case_type="借贷",
        objection=True,
        evidence="借条",
        legal_ground="《民法典》第679条",
        raw_text="对借条有异议",
    )
    strategy = generator.generate(intent, "对借条有异议")
    assert strategy.source == "rule"
    assert "借条" in strategy.text


def test_strategy_generator_falls_back_to_llm():
    kb = _FakeKB([])
    llm = _FakeLLM("建议保持冷静，要求对方出示证据")
    generator = StrategyGenerator(kb=kb, llm=llm)
    intent = LegalIntent(raw_text=" unrelated text ")
    strategy = generator.generate(intent, " unrelated text ")
    assert strategy.source == "llm"
    assert "保持冷静" in strategy.text


def test_strategy_generator_uses_case_clauses():
    kb = _FakeKB([])
    case = CaseFile(
        case_id="CASE-2026-0001",
        case_type="借贷",
        title="测试案件",
        created_at="",
        updated_at="",
    )
    case.legal_clauses.append(
        CaseLegalClause(
            code="LAW-0001",
            title="《民法典》第679条",
            content="自然人之间的借款合同，自贷款人提供借款时成立。",
            law_source="民法典",
        )
    )
    generator = StrategyGenerator(kb=kb, llm=None, case=case)
    intent = LegalIntent(case_type="借贷", raw_text="对方否认借款")
    strategy = generator.generate(intent, "对方否认借款")
    assert any("《民法典》第679条" == law for law in strategy.referenced_laws)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
