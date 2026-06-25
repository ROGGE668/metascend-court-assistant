"""Tests for the ASR engine."""

import numpy as np
import pytest

from src.asr.engine import ASREngine
from src.config import Config

# Use a tiny model for slow tests to keep CI/model-download times reasonable.
_TEST_MODEL_SIZE = "tiny"


def test_asr_default_config():
    engine = ASREngine(model_size=_TEST_MODEL_SIZE)
    assert engine.model_size == _TEST_MODEL_SIZE
    assert engine.language == Config.ASR_LANGUAGE


@pytest.mark.slow
def test_asr_loads_model():
    engine = ASREngine(model_size=_TEST_MODEL_SIZE, cache_dir=Config.MODEL_CACHE_DIR)
    engine.load()
    assert engine.is_loaded
    engine.unload()
    assert not engine.is_loaded


@pytest.mark.slow
def test_asr_transcribe_silence():
    engine = ASREngine(model_size=_TEST_MODEL_SIZE, cache_dir=Config.MODEL_CACHE_DIR)
    silence = np.zeros(16000, dtype=np.float32)  # 1 second silence
    text = engine.transcribe(silence)
    assert isinstance(text, str)
    engine.unload()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
