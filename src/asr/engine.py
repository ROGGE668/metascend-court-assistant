"""ASR engine based on faster-whisper."""

import logging
from pathlib import Path

import numpy as np
from faster_whisper import WhisperModel

from src.config import Config
from src.data_types import TranscriptLine

logger = logging.getLogger(__name__)


class ASREngine:
    """Local Whisper ASR engine with hotword support."""

    def __init__(
        self,
        model_size: str = Config.ASR_MODEL_SIZE,
        device: str = Config.ASR_DEVICE,
        compute_type: str = Config.ASR_COMPUTE_TYPE,
        language: str = Config.ASR_LANGUAGE,
        beam_size: int = Config.ASR_BEAM_SIZE,
        hotwords: list[str] | None = None,
        cache_dir: Path = Config.MODEL_CACHE_DIR,
    ):
        self.model_size = model_size
        self.device = self._resolve_device(device)
        self.compute_type = compute_type
        self.language = language
        self.beam_size = beam_size
        self.hotwords = hotwords or Config.ASR_HOTWORDS
        self.cache_dir = cache_dir
        self._model: WhisperModel | None = None

    @staticmethod
    def _resolve_device(device: str) -> str:
        if device == "auto":
            import torch

            if torch.backends.mps.is_available():
                return "auto"  # faster-whisper will pick cuda/cpu; mps support is limited
            return "cpu"
        return device

    def load(self) -> None:
        """Load the Whisper model into memory."""
        if self._model is not None:
            return
        logger.info(
            "Loading Whisper model %s on %s (%s)",
            self.model_size,
            self.device,
            self.compute_type,
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._model = WhisperModel(
            self.model_size,
            device=self.device,
            compute_type=self.compute_type,
            download_root=str(self.cache_dir),
            local_files_only=False,
        )
        logger.info("Whisper model loaded")

    def unload(self) -> None:
        """Unload the model to free memory."""
        if self._model is not None:
            del self._model
            self._model = None
            logger.info("Whisper model unloaded")

    def transcribe(self, audio: np.ndarray) -> str:
        """Transcribe a single audio segment. Returns the full text."""
        if self._model is None:
            self.load()

        # Ensure correct shape and dtype
        audio = audio.astype(np.float32).reshape(-1)
        if audio.max() > 1.0 or audio.min() < -1.0:
            audio = np.clip(audio, -1.0, 1.0)

        hotword_prompt = "、".join(self.hotwords) if self.hotwords else None

        segments, info = self._model.transcribe(
            audio,
            language=self.language,
            beam_size=self.beam_size,
            best_of=1,
            condition_on_previous_text=True,
            hotwords=hotword_prompt,
        )
        logger.debug("Transcription language=%s, duration=%.2f", info.language, info.duration)
        text = "".join(segment.text for segment in segments).strip()
        return text

    def transcribe_segment(self, segment) -> TranscriptLine:
        """Transcribe a speaker-tagged segment and preserve metadata."""
        text = self.transcribe(segment.audio)
        return TranscriptLine(
            text=text or "",
            start_ms=segment.start_ms,
            end_ms=segment.end_ms,
            speaker_id=segment.speaker_id,
            role=segment.role,
        )

    def transcribe_stream(
        self,
        audio_stream,
        callback=None,
    ) -> None:
        """Placeholder for future streaming transcription."""
        raise NotImplementedError("Streaming ASR will be implemented in Phase 2")

    @property
    def is_loaded(self) -> bool:
        return self._model is not None
