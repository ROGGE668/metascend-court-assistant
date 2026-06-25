"""Filter risky or inflammatory strategy outputs."""

from src.data_types import Strategy


class StrategyRiskFilter:
    """Prevent the assistant from suggesting aggressive or contemptuous language."""

    HIGH_RISK_WORDS = [
        "傻逼",
        "混蛋",
        "狗屁",
        "胡说八道",
        "你懂不懂法",
        "法官受贿",
        "法院黑",
        "威胁",
        "恐吓",
    ]

    MEDIUM_RISK_WORDS = [
        "你在撒谎",
        "无耻",
        "卑鄙",
        "胡说",
        "颠倒黑白",
        "栽赃",
    ]

    def filter(self, strategy: Strategy) -> Strategy:
        """Return the strategy with adjusted risk level and sanitized text."""
        text = strategy.text.lower()

        if any(word in text for word in self.HIGH_RISK_WORDS):
            strategy.risk_level = "high"
            strategy.text = "[高风险建议已过滤] 请保持冷静，使用规范法律语言回应。"
            strategy.reasoning = "包含情绪化或攻击化表达"
            strategy.referenced_laws.clear()
        elif any(word in text for word in self.MEDIUM_RISK_WORDS):
            strategy.risk_level = "medium"
            strategy.text = "[注意语气] " + strategy.text

        return strategy
