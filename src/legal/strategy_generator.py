"""Generate legal strategy from intent, templates, RAG, and LLM."""

import logging

import yaml

from src.case_archive.models import CaseFile
from src.config import Config
from src.data_types import LegalIntent, Strategy
from src.legal.knowledge_base import LocalLegalKnowledgeBase
from src.legal.llm_client import OllamaClient
from src.legal.risk_filter import StrategyRiskFilter

logger = logging.getLogger(__name__)


class StrategyGenerator:
    """Combine rule templates, RAG, and a local LLM to produce a suggestion."""

    def __init__(
        self,
        kb: LocalLegalKnowledgeBase | None = None,
        llm: OllamaClient | None = None,
        case: CaseFile | None = None,
    ):
        self.kb = kb
        if self.kb is None:
            self.kb = LocalLegalKnowledgeBase()
            self.kb.load()

        self.llm = llm if llm is not None else OllamaClient()
        self.risk_filter = StrategyRiskFilter()
        self.templates = self._load_templates()
        self.case = case
        self._llm_available: bool | None = None

    def _llm_ready(self) -> bool:
        """Cache the LLM availability probe so repeated calls stay fast."""
        if self._llm_available is None:
            try:
                self._llm_available = self.llm.is_available()
            except AttributeError:
                self._llm_available = True
            except Exception:
                self._llm_available = False
        return self._llm_available

    def set_case(self, case: CaseFile | None) -> None:
        """Switch the active case context."""
        self.case = case

    def _load_templates(self) -> dict:
        """Load strategy templates from disk or use built-ins."""
        path = Config.TEMPLATES_DIR / "strategies.yaml"
        if path.exists():
            try:
                with open(path, encoding="utf-8") as fp:
                    return yaml.safe_load(fp) or {}
            except Exception as e:
                logger.warning("Failed to load templates from %s: %s", path, e)
        return self._built_in_templates()

    def _built_in_templates(self) -> dict:
        return {
            "借贷": {
                "质证": "对{evidence}的真实性、合法性提出异议，要求对方出示原件并说明来源。",
                "辩论": (
                    "主张借款本金以实际交付金额为准；" "利息约定不得超过合同成立时一年期LPR的四倍。"
                ),
                "通用": "请对方明确借款金额、利息约定、还款时间以及已还款金额。",
            },
            "离婚": {
                "质证": "质疑对方提交的{evidence}真实性与取得方式，要求补充证据链。",
                "辩论": "围绕子女最佳利益与财产实际贡献进行陈述，避免情绪化攻击。",
                "通用": "请对方说明财产来源、抚养能力及具体分割方案。",
            },
            "劳动": {
                "质证": "对{evidence}的完整性提出异议，要求出示原始考勤、工资条或社保记录。",
                "辩论": "主张用人单位应及时足额支付工资并依法支付加班费或经济补偿。",
                "通用": "请对方明确工资标准、加班时长、社保缴纳及解除劳动关系的依据。",
            },
            "合同": {
                "质证": "对{evidence}的签订过程与签字真实性提出质疑，要求核对原件。",
                "辩论": "依据合同约定与《民法典》第577条，要求对方承担继续履行或赔偿损失责任。",
                "通用": "请对方说明合同履行情况、违约事实及损失计算方式。",
            },
        }

    def generate(
        self,
        intent: LegalIntent,
        transcript: str,
        case: CaseFile | None = None,
    ) -> Strategy:
        """Return a Strategy for the given intent and transcript."""
        active_case = case or self.case
        if active_case and not intent.case_type:
            intent.case_type = self._case_type_from_archive(active_case)

        strategy = self._rule_strategy(intent)
        rule_text = strategy.text
        rule_countermeasure = strategy.text
        query = self._build_query(active_case, transcript)
        retrieved = self.kb.retrieve(query, top_k=3) if self.kb else []
        case_clauses: list[dict] = []
        if active_case is not None and active_case.legal_clauses:
            case_clauses = [
                {
                    "law": c.title,
                    "content": c.content,
                    "case_type": active_case.case_type,
                }
                for c in active_case.legal_clauses[:3]
            ]
        all_retrieved = case_clauses + retrieved
        referenced = [d.get("law") for d in all_retrieved if d.get("law")]

        if rule_text:
            strategy.referenced_laws = list(dict.fromkeys(strategy.referenced_laws + referenced))

        if not rule_text and self.llm is not None and self._llm_ready():
            llm_text = self._llm_suggest(intent, transcript, all_retrieved, active_case)
            if llm_text:
                strategy = Strategy(
                    text=llm_text,
                    reasoning=llm_text,
                    countermeasure=llm_text,
                    source="llm",
                    referenced_laws=referenced,
                )

        if not rule_text and not strategy.countermeasure:
            snippets = "；".join(d.get("content", "") for d in all_retrieved[:2])
            strategy = Strategy(
                text=f"参考：{snippets}",
                reasoning=f"参考：{snippets}",
                source="rag",
                referenced_laws=referenced,
            )

        if rule_text and not strategy.reasoning:
            strategy.reasoning = rule_text
        if not strategy.countermeasure:
            strategy.countermeasure = strategy.text or "请保持冷静，要求对方补充证据或事实细节。"
        return self.risk_filter.filter(strategy)

    def _case_type_from_archive(self, case: CaseFile) -> str | None:
        """Map archive case_type to template keys used by the intent extractor."""
        mapping = {
            "loan": "借贷",
            "divorce": "离婚",
            "labor": "劳动",
            "contract": "合同",
        }
        return mapping.get(case.case_type)

    def _build_query(self, case: CaseFile | None, transcript: str) -> str:
        """Blend case facts/evidence with the transcript for retrieval."""
        parts = [transcript]
        if case is not None:
            if case.case_type:
                parts.append(case.case_type)
            if case.facts:
                parts.append(" ".join(f.content for f in case.facts[:3]))
            if case.evidence:
                parts.append(" ".join(e.title for e in case.evidence[:5]))
            if case.legal_clauses:
                parts.append(" ".join(c.title for c in case.legal_clauses[:5]))
            if case.appeals:
                parts.append(" ".join(a.title for a in case.appeals[:3]))
        return " ".join(parts)

    def _evidence_matches(self, case: CaseFile, transcript: str) -> list[str]:
        """Return codes of case evidence mentioned in the transcript."""
        matches: list[str] = []
        for ev in case.evidence:
            if ev.title and ev.title in transcript:
                matches.append(f"{ev.title}({ev.code})")
            elif ev.tags and any(t in transcript for t in ev.tags):
                matches.append(f"{ev.title}({ev.code})")
        return matches

    def _rule_strategy(self, intent: LegalIntent) -> Strategy:
        """Select a template based on the extracted intent."""
        if not intent.case_type or intent.case_type not in self.templates:
            return Strategy()

        templates = self.templates[intent.case_type]
        if intent.objection:
            text = templates.get("质证", templates.get("通用", ""))
        elif intent.claim:
            text = templates.get("辩论", templates.get("通用", ""))
        elif intent.evidence:
            text = templates.get("质证", templates.get("通用", ""))
        else:
            text = templates.get("通用", "")

        if not text:
            return Strategy()

        defaults = {
            "claim": intent.claim or "",
            "evidence": intent.evidence or "",
            "legal_ground": intent.legal_ground or "",
        }
        try:
            text = text.format(**defaults)
        except Exception:
            pass

        referenced = [intent.legal_ground] if intent.legal_ground else []
        return Strategy(text=text, source="rule", referenced_laws=referenced)

    def _llm_suggest(
        self,
        intent: LegalIntent,
        transcript: str,
        retrieved: list[dict],
        case: CaseFile | None,
    ) -> str | None:
        """Build a prompt and ask the local LLM for a concise suggestion."""
        context = "\n".join(f"- {d.get('law', '')}：{d.get('content', '')}" for d in retrieved[:3])
        case_context = ""
        if case is not None:
            case_context = f"\n案情档案摘要：\n{case.summary_text()}"
            matches = self._evidence_matches(case, transcript)
            if matches:
                case_context += "\n提及的证据：" + "、".join(matches)
        parties = ""
        if case is not None and case.parties:
            parties = "\n当事人：" + "、".join(f"{p.name}({p.role})" for p in case.parties)
        prompt = f"""你是为普通当事人服务的AI庭审助手，只输出1-2句简短建议，不要编造法条。

对方/法官发言：{transcript}
案件类型：{intent.case_type or (case.case_type if case else None) or '未知'}
{case_context}{parties}
可能涉及法条：
{context}

请给出应对建议（仅参考，不构成法律意见）："""
        return self.llm.complete(prompt)
