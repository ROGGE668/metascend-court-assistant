"""Rule-based legal intent extraction from transcribed text."""

from src.data_types import LegalIntent


class RuleHeuristicLegalIntentExtractor:
    """Extract legal intent using keyword heuristics.

    This is a lightweight, deterministic baseline for Phase 3. It can be
    replaced by a fine-tuned legal-NER model once labelled data is available.
    """

    CASE_TYPE_KEYWORDS = {
        "借贷": ["借款", "借钱", "借条", "欠条", "还款", "利息", "本金", "贷款"],
        "离婚": ["离婚", "抚养权", "抚养费", "财产分割", "夫妻共同财产", "感情破裂"],
        "劳动": ["工资", "加班", "劳动合同", "社保", "赔偿金", "辞退", "解雇", "劳动仲裁"],
        "合同": ["合同", "违约", "违约金", "履行", "解除", "赔偿损失"],
    }

    CLAIM_KEYWORDS = ["要求", "请求", "诉求", "主张", "诉请"]
    EVIDENCE_KEYWORDS = ["证据", "借条", "合同", "记录", "截图", "发票", "流水", "录音"]
    OBJECTION_KEYWORDS = ["异议", "反对", "不认可", "无效", "不属实", "伪造", "诱导"]

    GROUND_PATTERNS = {
        "利息": "《民法典》第680条 / 《民间借贷司法解释》第25条",
        "借款": "《民法典》第679条",
        "违约": "《民法典》第577条",
        "离婚": "《民法典》第1079条",
        "工资": "《劳动合同法》第30条 / 《劳动法》第50条",
        "加班": "《劳动合同法》第31条",
    }

    def extract(self, text: str) -> LegalIntent:
        """Return a LegalIntent populated from keyword matches."""
        intent = LegalIntent(raw_text=text)

        for case_type, keywords in self.CASE_TYPE_KEYWORDS.items():
            if any(k in text for k in keywords):
                intent.case_type = case_type
                break

        if any(k in text for k in self.CLAIM_KEYWORDS):
            intent.claim = text

        if any(k in text for k in self.EVIDENCE_KEYWORDS):
            intent.evidence = text

        intent.objection = any(k in text for k in self.OBJECTION_KEYWORDS)

        for keyword, ground in self.GROUND_PATTERNS.items():
            if keyword in text:
                intent.legal_ground = ground
                break

        return intent
