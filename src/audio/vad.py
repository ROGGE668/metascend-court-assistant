"""Voice activity detection and speech buffering with Silero VAD."""

import logging
from collections import deque
from enum import Enum, auto
from pathlib import Path

import numpy as np
import torch

from src.config import Config

logger = logging.getLogger(__name__)


class VADState(Enum):
    SILENCE = auto()
    SPEECH = auto()


class VADBuffer:
    """Buffers audio based on Silero VAD and emits speech segments.

    Silero VAD requires fixed-size windows (512 samples at 16 kHz or 256 at
    8 kHz). This class accepts arbitrarily-sized input chunks, splits them
    internally, and returns a complete speech segment once the utterance ends.
    """

    _model_cache = None
    _utils_cache = None

    def __init__(
        self,
        sample_rate: int = Config.SAMPLE_RATE,
        threshold: float = 0.5,
        min_speech_duration_ms: int = 250,
        min_silence_duration_ms: int = 400,
        padding_ms: int = 200,
        energy_threshold: float = 0.015,
    ):
        self.sample_rate = sample_rate
        self.threshold = threshold
        self._energy_threshold = energy_threshold
        self.min_speech_samples = int(sample_rate * min_speech_duration_ms / 1000)
        self.min_silence_samples = int(sample_rate * min_silence_duration_ms / 1000)
        self.padding_samples = int(sample_rate * padding_ms / 1000)

        # Silero expects exactly 512 samples at 16 kHz (256 at 8 kHz).
        self._window_size = 512 if sample_rate == 16000 else 256

        self._state = VADState.SILENCE
        self._speech_buffer: deque[np.ndarray] = deque()
        self._input_buffer: np.ndarray = np.array([], dtype=np.float32)
        self._pre_speech_buffer: deque[np.ndarray] = deque(
            maxlen=int(self.padding_samples / self._window_size) + 1
        )
        self._speech_samples: int = 0
        self._silence_samples: int = 0
        self._model = None
        self._utils = None

    @property
    def window_size(self) -> int:
        """Return the VAD window size in samples."""
        return self._window_size

    @property
    def speaking(self) -> bool:
        """Return True if VAD currently considers the input to be speech."""
        return self._state == VADState.SPEECH

    @property
    def model(self):
        """Lazy-load and cache the Silero VAD model."""
        if self._model is None:
            loaded_model, loaded_utils = self._load_model()
            if loaded_model is None:
                self._model = None
                self._utils = None
                self._get_speech_timestamps = None
            else:
                self._model = loaded_model
                self._utils = loaded_utils
                self._get_speech_timestamps = self._utils[0]
        return self._model

    def _load_model(self):
        logger.info("Loading Silero VAD model")
        if VADBuffer._model_cache is not None:
            logger.debug("Reusing cached Silero VAD model")
            return VADBuffer._model_cache, VADBuffer._utils_cache

        # Try loading cached JIT directly to avoid torch.hub network stalls
        jit_path = (
            Path.home()
            / ".cache/torch/hub/snakers4_silero-vad_master/src/silero_vad/data/silero_vad.jit"
        )
        try:
            if jit_path.exists():
                logger.info("Loading cached Silero VAD JIT from %s", jit_path)
                model = torch.jit.load(str(jit_path), map_location="cpu")
                # Provide a minimal get_speech_timestamps placeholder for callers
                utils = [lambda *args, **kwargs: []]
                VADBuffer._model_cache = model
                VADBuffer._utils_cache = utils
                return model, utils
        except Exception as exc:
            logger.warning("Failed to load cached Silero JIT, falling back to torch.hub: %s", exc)

        try:
            logger.info("Downloading/loading Silero VAD model for the first time")
            model, utils = torch.hub.load(
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                force_reload=False,
                onnx=False,
                trust_repo=True,
            )
        except Exception as exc:
            logger.error("Failed to load Silero VAD, using energy fallback: %s", exc)
            return None, None

        VADBuffer._model_cache = model
        VADBuffer._utils_cache = utils
        return model, utils

    def _is_speech(self, audio: np.ndarray) -> bool:
        """Return True if a single VAD window contains speech."""
        if self.model is None:
            return self._energy_is_speech(audio)
        tensor = torch.from_numpy(audio.squeeze().astype(np.float32))
        # Guard against callers passing larger chunks.
        if tensor.shape[-1] != self._window_size:
            tensor = tensor[: self._window_size]
        if self.sample_rate != 16000:
            tensor = self._resample(tensor)
        with torch.no_grad():
            speech_prob = self.model(tensor, self.sample_rate).item()
        return speech_prob >= self.threshold

    def _energy_is_speech(self, audio: np.ndarray) -> bool:
        """Lightweight energy-based fallback when Silero VAD is unavailable."""
        samples = audio.astype(np.float64).reshape(-1)
        rms = float(np.sqrt(np.mean(samples * samples)))
        return rms > self._energy_threshold

    @staticmethod
    def _resample(
        tensor: torch.Tensor,
        orig_sr: int = 16000,
        target_sr: int = 16000,
    ) -> torch.Tensor:
        """Simple resampling if needed (placeholder; most inputs are already 16kHz)."""
        if orig_sr == target_sr:
            return tensor
        # Use torchaudio if available, otherwise naive interpolation
        try:
            import torchaudio.functional as F

            return F.resample(tensor, orig_freq=orig_sr, new_freq=target_sr)
        except Exception:
            ratio = target_sr / orig_sr
            target_len = int(len(tensor) * ratio)
            return torch.nn.functional.interpolate(
                tensor.unsqueeze(0).unsqueeze(0),
                size=target_len,
                mode="linear",
                align_corners=False,
            ).squeeze()

    def process(self, chunk: np.ndarray) -> np.ndarray | None:
        """Process an arbitrary-sized audio chunk.

        Returns a complete speech segment as soon as VAD detects a finished
        utterance, otherwise returns None.
        """
        chunk = chunk.reshape(-1)
        self._input_buffer = np.concatenate([self._input_buffer, chunk])

        segment = None
        while len(self._input_buffer) >= self._window_size:
            window = self._input_buffer[: self._window_size]
            self._input_buffer = self._input_buffer[self._window_size :]
            window_segment = self._process_window(window)
            if window_segment is not None:
                segment = window_segment
        return segment

    def _process_window(self, window: np.ndarray) -> np.ndarray | None:
        """Process one Silero-sized VAD window."""
        is_speech = self._is_speech(window)

        if self._state == VADState.SILENCE:
            self._pre_speech_buffer.append(window)
            if is_speech:
                self._state = VADState.SPEECH
                self._speech_buffer.clear()
                # Prepend recent padding windows for a natural speech start.
                pad_samples = 0
                for w in self._pre_speech_buffer:
                    if pad_samples + len(w) > self.padding_samples:
                        w = w[self.padding_samples - pad_samples :]
                    self._speech_buffer.append(w)
                    pad_samples += len(w)
                self._speech_buffer.append(window)
                self._speech_samples = sum(len(w) for w in self._speech_buffer)
                self._silence_samples = 0
            return None

        # State == SPEECH
        self._speech_buffer.append(window)
        if is_speech:
            self._speech_samples += len(window)
            self._silence_samples = 0
        else:
            self._silence_samples += len(window)

        if (
            self._silence_samples >= self.min_silence_samples
            and self._speech_samples >= self.min_speech_samples
        ):
            return self._flush()

        # Safety flush for very long utterances
        if self._speech_samples >= self.sample_rate * 30:
            return self._flush()

        return None

    def _flush(self) -> np.ndarray:
        """Flush buffered speech into a single segment."""
        segment = np.concatenate(list(self._speech_buffer))
        self._speech_buffer.clear()
        self._state = VADState.SILENCE
        self._speech_samples = 0
        self._silence_samples = 0
        self._pre_speech_buffer.clear()
        logger.debug("Flushed speech segment: %.2fs", len(segment) / self.sample_rate)
        return segment

    def reset(self) -> None:
        """Clear internal buffers."""
        self._speech_buffer.clear()
        self._input_buffer = np.array([], dtype=np.float32)
        self._pre_speech_buffer.clear()
        self._state = VADState.SILENCE
        self._speech_samples = 0
        self._silence_samples = 0
        # Note: we do not clear the cached VAD model.
