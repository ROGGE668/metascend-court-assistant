"""Local / online LLM client with provider switching via environment."""

import logging
import os

from src.config import Config

logger = logging.getLogger(__name__)


class OllamaClient:
    """Thin wrapper that routes to Ollama (local) or an OpenAI-compatible endpoint."""

    def __init__(self, model: str | None = None, timeout: float = Config.LLM_TIMEOUT):
        self.model = model or os.getenv("METASCEND_LLM_MODEL") or Config.LLM_MODEL
        self.timeout = timeout

    def complete(self, prompt: str) -> str | None:
        provider = (os.getenv("METASCEND_LLM_PROVIDER") or "ollama").lower()
        if provider == "openai":
            return self._openai_complete(prompt)
        return self._ollama_complete(prompt)

    def _ollama_complete(self, prompt: str) -> str | None:
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

    def _openai_complete(self, prompt: str) -> str | None:
        base_url = os.getenv("METASCEND_LLM_BASE_URL", "https://api.openai.com/v1")
        api_key = os.getenv("METASCEND_LLM_API_KEY", "")
        url = base_url.rstrip("/") + "/chat/completions"
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 200,
        }
        try:
            import requests

            response = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.warning("OpenAI-compatible call failed: %s", e)
            return None

    def is_available(self) -> bool:
        provider = (os.getenv("METASCEND_LLM_PROVIDER") or "ollama").lower()
        if provider == "openai":
            return bool(os.getenv("METASCEND_LLM_API_KEY"))
        try:
            import ollama

            ollama.list()
            return True
        except Exception:
            return False
