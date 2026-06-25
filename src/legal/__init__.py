"""Legal reasoning modules."""

from src.legal.intent_extractor import RuleHeuristicLegalIntentExtractor
from src.legal.knowledge_base import LocalLegalKnowledgeBase
from src.legal.legal_assistant import LegalAssistant
from src.legal.llm_client import OllamaClient
from src.legal.risk_filter import StrategyRiskFilter
from src.legal.strategy_generator import StrategyGenerator

__all__ = [
    "LegalAssistant",
    "RuleHeuristicLegalIntentExtractor",
    "LocalLegalKnowledgeBase",
    "StrategyGenerator",
    "StrategyRiskFilter",
    "OllamaClient",
]
