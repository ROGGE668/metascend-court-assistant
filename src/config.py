"""Configuration loaded from environment and .env file."""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _expand(path: str | None, default: str) -> Path:
    if path is None or path.strip() == "":
        path = default
    return Path(path).expanduser().resolve()


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name, "")
    if value == "":
        return default
    return value.lower() in ("1", "true", "yes", "on")


class Config:
    """Global application configuration."""

    # Audio
    SAMPLE_RATE: int = int(os.getenv("SAMPLE_RATE", "16000"))
    CHANNELS: int = int(os.getenv("CHANNELS", "1"))
    CHUNK_DURATION_MS: int = int(os.getenv("CHUNK_DURATION_MS", "100"))
    VAD_AGGRESSIVENESS: int = int(os.getenv("VAD_AGGRESSIVENESS", "2"))

    # ASR
    ASR_MODEL_SIZE: str = os.getenv("ASR_MODEL_SIZE", "large-v3-turbo")
    ASR_DEVICE: str = os.getenv("ASR_DEVICE", "auto")
    ASR_COMPUTE_TYPE: str = os.getenv("ASR_COMPUTE_TYPE", "int8")
    ASR_LANGUAGE: str = os.getenv("ASR_LANGUAGE", "zh")
    ASR_BEAM_SIZE: int = int(os.getenv("ASR_BEAM_SIZE", "5"))
    ASR_HOTWORDS: list[str] = [
        w.strip() for w in os.getenv("ASR_HOTWORDS", "").split(",") if w.strip()
    ]

    # Diarization (Phase 2)
    ENABLE_DIARIZATION: bool = _bool_env("ENABLE_DIARIZATION", False)
    DIARIZATION_BACKEND: str = os.getenv("DIARIZATION_BACKEND", "mock")
    DIARIZATION_SIMILARITY_THRESHOLD: float = float(
        os.getenv("DIARIZATION_SIMILARITY_THRESHOLD", "0.65")
    )
    DIARIZATION_ROLE_THRESHOLD: float = float(os.getenv("DIARIZATION_ROLE_THRESHOLD", "0.60"))
    DIARIZATION_MAX_SPEAKERS: int = int(os.getenv("DIARIZATION_MAX_SPEAKERS", "4"))

    # UI
    UI_WINDOW_OPACITY: float = float(os.getenv("UI_WINDOW_OPACITY", "0.95"))
    UI_FONT_SIZE: int = int(os.getenv("UI_FONT_SIZE", "18"))
    UI_MAX_LINES: int = int(os.getenv("UI_MAX_LINES", "5"))

    # OCR
    ENABLE_OCR_FALLBACK: bool = _bool_env("ENABLE_OCR_FALLBACK", True)

    # Paths
    MODEL_CACHE_DIR: Path = _expand(os.getenv("MODEL_CACHE_DIR"), "~/.cache/metascend/models")
    DATA_DIR: Path = _expand(os.getenv("DATA_DIR"), "./data")

    # Legal assistant (Phase 3)
    ENABLE_LEGAL_ASSISTANT: bool = _bool_env("ENABLE_LEGAL_ASSISTANT", False)
    LLM_BACKEND: str = os.getenv("LLM_BACKEND", "ollama")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "qwen2.5:7b")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-zh-v1.5")
    KNOWLEDGE_BASE_DIR: Path = _expand(
        os.getenv("KNOWLEDGE_BASE_DIR"),
        str(DATA_DIR / "knowledge_base"),
    )
    TEMPLATES_DIR: Path = _expand(
        os.getenv("TEMPLATES_DIR"),
        str(DATA_DIR / "templates"),
    )
    LLM_TIMEOUT: float = float(os.getenv("LLM_TIMEOUT", "10.0"))

    # TTS (Phase 4)
    ENABLE_TTS: bool = _bool_env("ENABLE_TTS", False)
    TTS_BACKEND: str = os.getenv("TTS_BACKEND", "system")
    TTS_VOICE: str = os.getenv("TTS_VOICE", "Ting-Ting")
    TTS_VOLUME: float = float(os.getenv("TTS_VOLUME", "0.8"))
    TTS_DUCKING: bool = _bool_env("TTS_DUCKING", True)

    # Recording & privacy (Phase 5)
    ENABLE_RECORDING: bool = _bool_env("ENABLE_RECORDING", False)
    ENABLE_ENCRYPTED_LOGS: bool = _bool_env("ENABLE_ENCRYPTED_LOGS", False)
    RECORDING_PASSWORD: str = os.getenv("RECORDING_PASSWORD", "")

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    @property
    def chunk_samples(self) -> int:
        """Number of samples per audio chunk."""
        return int(self.SAMPLE_RATE * self.CHUNK_DURATION_MS / 1000)


def configure_logging(level: str | None = None, encrypted: bool | None = None) -> None:
    level = level or Config.LOG_LEVEL
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if encrypted is None:
        encrypted = Config.ENABLE_ENCRYPTED_LOGS
    if not encrypted:
        return

    from src.utils.encrypted_log import EncryptedLogFileHandler

    root = logging.getLogger()
    # Avoid duplicate encrypted handlers across repeated initializations.
    for handler in list(root.handlers):
        if isinstance(handler, EncryptedLogFileHandler):
            root.removeHandler(handler)
            handler.close()

    log_path = Config.DATA_DIR / "logs" / "app.log.enc"
    handler = EncryptedLogFileHandler(log_path, Config.RECORDING_PASSWORD)
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    root.addHandler(handler)
