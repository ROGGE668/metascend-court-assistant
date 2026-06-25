"""Tests for audio capture and VAD modules."""

from unittest.mock import patch

import numpy as np
import pytest
import torch

from src.audio.capture import AudioCapture
from src.audio.vad import VADBuffer, VADState


def test_list_devices():
    devices = AudioCapture.list_devices()
    assert isinstance(devices, list)
    if not devices:
        pytest.skip("No audio devices available in this environment")


def test_vad_buffer_silence():
    vad = VADBuffer()
    silence = np.zeros(1600, dtype=np.float32)
    with patch.object(vad, "_is_speech", return_value=False):
        result = vad.process(silence)
    assert result is None
    assert vad._state == VADState.SILENCE


def test_vad_buffer_resets():
    vad = VADBuffer()
    vad._state = VADState.SPEECH
    vad._speech_buffer.append(np.zeros(512, dtype=np.float32))
    vad.reset()
    assert vad._state == VADState.SILENCE
    assert len(vad._speech_buffer) == 0


@pytest.mark.slow
def test_vad_speech_prob_range():
    vad = VADBuffer()
    window = torch.zeros(vad.window_size)
    prob = vad.model(VADBuffer._resample(window, 16000, 16000), 16000).item()
    assert 0.0 <= prob <= 1.0


def test_audio_capture_config():
    capture = AudioCapture(sample_rate=16000, channels=1, chunk_duration_ms=100)
    assert capture.sample_rate == 16000
    assert capture.channels == 1
    assert capture.chunk_samples == 1600


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
