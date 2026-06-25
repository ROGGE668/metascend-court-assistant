"""Tests for the TTS engine."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.tts.engine import TTSEngine


def _fake_wave(nframes=2205, nchannels=1):
    """Return a fake wave file-like object with 0.1s of silence."""
    raw = np.zeros(nframes * nchannels, dtype=np.int16).tobytes()
    fake = MagicMock()
    fake.getnchannels.return_value = nchannels
    fake.getsampwidth.return_value = 2
    fake.getframerate.return_value = 22050
    fake.getnframes.return_value = nframes
    fake.readframes.return_value = raw
    fake.__enter__.return_value = fake
    fake.__exit__.return_value = False
    return fake


def test_tts_synthesize_returns_audio():
    engine = TTSEngine(backend="system", voice="Ting-Ting")
    fake_wave = _fake_wave()
    with (
        patch("src.tts.engine.subprocess.run") as mock_run,
        patch("src.tts.engine.wave.open", return_value=fake_wave),
        patch("src.tts.engine.os.remove"),
    ):
        audio = engine.synthesize("你好")
    assert isinstance(audio, np.ndarray)
    assert len(audio) > 0
    assert abs(audio.max()) <= 1.0
    mock_run.assert_called_once()


def test_tts_speak_uses_sounddevice():
    engine = TTSEngine(backend="system", voice="Ting-Ting")
    fake_wave = _fake_wave()
    with (
        patch("src.tts.engine.subprocess.run"),
        patch("src.tts.engine.wave.open", return_value=fake_wave),
        patch("src.tts.engine.os.remove"),
        patch("src.tts.engine.sd.play") as mock_play,
        patch("src.tts.engine.sd.get_stream") as mock_stream,
        patch("src.tts.engine.sd.wait"),
    ):
        mock_stream.return_value = MagicMock(active=False)
        engine.speak("你好")
    mock_play.assert_called_once()


def test_tts_ducking_stops_playback():
    engine = TTSEngine(backend="system", voice="Ting-Ting")
    fake_wave = _fake_wave()
    with (
        patch("src.tts.engine.subprocess.run"),
        patch("src.tts.engine.wave.open", return_value=fake_wave),
        patch("src.tts.engine.os.remove"),
        patch("src.tts.engine.sd.play") as mock_play,
        patch("src.tts.engine.sd.get_stream") as mock_stream,
        patch("src.tts.engine.sd.stop") as mock_stop,
        patch("src.tts.engine.sd.wait"),
    ):
        mock_stream.return_value = MagicMock(active=True)
        # Duck immediately
        engine.speak("你好", ducking_callback=lambda: True)
    mock_play.assert_called_once()
    mock_stop.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
