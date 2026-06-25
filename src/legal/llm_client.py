"""Local LLM client using Ollama."""

import logging

from src.config import Config

logger = logging.getLogger(__name__)


class OllamaClient:
    """Thin wrapper around Ollama for local inference."""

    def __init__(self, model: str | None = None, timeout: float = Config.LLM_TIMEOUT):
        self.model = model or Config.LLM_MODEL
        self.timeout = timeout

    def complete(self, prompt: str) -> str | None:
        """Call the local model and return the generated text, or None on failure."""
        try:
            import ollama

            response = ollama.chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                options={"num_predict": 200},
                timeout=self.timeout,
            )
            return response["message"]["content"].strip()
        except Exception as e:
            logger.warning("Ollama call failed: %s", e)
            return None

    def is_available(self) -> bool:
        """Quickly probe whether the configured model can be reached."""
        try:
            import ollama

            ollama.list()
            return True
        except Exception:
            return False
