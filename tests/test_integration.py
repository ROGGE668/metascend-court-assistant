"""Integration tests across completed phases."""

import numpy as np
import pytest

from src.audio.vad import VADBuffer
from src.data_types import Role
from src.diarization.engine import DiarizationEngine


def _sine_wave(freq: float, duration: float = 1.0) -> np.ndarray:
    t = np.linspace(0, duration, int(16000 * duration), endpoint=False)
    return np.sin(2 * np.pi * freq * t).astype(np.float32) * 0.3


class _MockASR:
    def transcribe(self, audio: np.ndarray) -> str:
        return "mock transcription"


def test_vad_diarization_asr_flow():
    vad = VADBuffer()
    # Use an energy-based stub so that pure-tone "speech" reliably triggers VAD
    # without depending on Silero's speech-specific training.
    vad._is_speech = lambda chunk: float(np.mean(chunk**2)) > 1e-4  # type: ignore[method-assign]

    diarization = DiarizationEngine(backend="mock")
    diarization.calibrate(Role.JUDGE, _sine_wave(250, 0.5))
    diarization.calibrate(Role.OPPONENT, _sine_wave(750, 0.5))
    asr = _MockASR()

    audio = np.concatenate([_sine_wave(250, 1.0), np.zeros(8000, dtype=np.float32)])
    speech = None
    for i in range(0, len(audio), 1600):
        chunk = audio[i : i + 1600]
        if len(chunk) < 1600:
            break
        speech = vad.process(chunk)
        if speech is not None:
            break

    assert speech is not None
    segments = diarization.process(speech)
    assert len(segments) == 1
    assert segments[0].role == Role.JUDGE
    text = asr.transcribe(segments[0].audio)
    assert text == "mock transcription"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
