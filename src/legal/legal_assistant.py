"""Facade that wires together intent extraction and strategy generation."""

from src.case_archive.models import CaseFile
from src.data_types import Strategy
from src.legal.intent_extractor import RuleHeuristicLegalIntentExtractor
from src.legal.strategy_generator import StrategyGenerator


class LegalAssistant:
    """High-level helper: transcript -> LegalIntent -> Strategy."""

    def __init__(self, case: CaseFile | None = None) -> None:
        self.extractor = RuleHeuristicLegalIntentExtractor()
        self.generator = StrategyGenerator(case=case)
        self.case = case

    def set_case(self, case: CaseFile | None) -> None:
        """Switch the active case context."""
        self.case = case
        self.generator.set_case(case)

    def suggest(self, transcript: str) -> Strategy:
        """Analyze the transcript and return a reference strategy."""
        intent = self.extractor.extract(transcript)
        return self.generator.generate(intent, transcript, case=self.case)
