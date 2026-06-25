"""Encrypted local storage for VAD speech segments."""

import io
import logging
import wave
from pathlib import Path

import numpy as np

from src.config import Config
from src.utils.encryption import AESCipher
from src.utils.helpers import current_time_ms

logger = logging.getLogger(__name__)


class RecordingStore:
    """Save and load encrypted audio recordings under ``data/recordings/``."""

    def __init__(
        self,
        data_dir: Path | None = None,
        password: str | None = None,
        sample_rate: int = Config.SAMPLE_RATE,
    ):
        self.sample_rate = sample_rate
        self.dir = (data_dir or Config.DATA_DIR) / "recordings"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.cipher = AESCipher(password)

    def save(self, audio: np.ndarray, prefix: str = "segment") -> Path:
        """Encrypt and persist an audio segment; return the file path."""
        wav_bytes = self._to_wav_bytes(audio)
        encrypted = self.cipher.encrypt(wav_bytes)
        filename = f"{prefix}_{current_time_ms()}.enc"
        path = self.dir / filename
        path.write_bytes(encrypted)
        logger.info("Saved encrypted recording: %s", path)
        return path

    def load(self, path: Path) -> np.ndarray:
        """Decrypt and return an audio segment."""
        encrypted = path.read_bytes()
        wav_bytes = self.cipher.decrypt(encrypted)
        return self._from_wav_bytes(wav_bytes)

    def list_recordings(self) -> list[Path]:
        """Return all encrypted recording files."""
        return sorted(self.dir.glob("*.enc"))

    def _to_wav_bytes(self, audio: np.ndarray) -> bytes:
        """Pack a float32 [-1, 1] mono array into in-memory WAV bytes."""
        audio = audio.astype(np.float32).reshape(-1)
        clipped = np.clip(audio, -1.0, 1.0)
        pcm = (clipped * 32767.0).astype(np.int16)

        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(pcm.tobytes())
        return buffer.getvalue()

    def _from_wav_bytes(self, wav_bytes: bytes) -> np.ndarray:
        """Read WAV bytes back into a float32 mono array."""
        buffer = io.BytesIO(wav_bytes)
        with wave.open(buffer, "rb") as wf:
            nchannels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            nframes = wf.getnframes()
            raw = wf.readframes(nframes)

        dtype = np.int16 if sampwidth == 2 else np.int8
        pcm = np.frombuffer(raw, dtype=dtype).astype(np.float32)
        if nchannels == 2:
            pcm = pcm.reshape(-1, 2).mean(axis=1)
        return pcm / 32768.0
