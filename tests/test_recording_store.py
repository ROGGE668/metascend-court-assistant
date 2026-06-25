"""Tests for encrypted recording storage."""

import numpy as np
import pytest

from src.utils.recording_store import RecordingStore


def test_save_and_load_recording(tmp_path):
    store = RecordingStore(data_dir=tmp_path, password="test-password")
    audio = np.sin(2 * np.pi * 440 * np.linspace(0, 0.1, 1600)).astype(np.float32)
    path = store.save(audio, prefix="test")
    assert path.exists()
    loaded = store.load(path)
    # PCM round-trip loses a little precision; tolerate 1e-3.
    assert np.allclose(audio, loaded, atol=1e-3)


def test_list_recordings(tmp_path):
    store = RecordingStore(data_dir=tmp_path, password="test-password")
    store.save(np.zeros(1600, dtype=np.float32), prefix="a")
    store.save(np.zeros(1600, dtype=np.float32), prefix="b")
    files = store.list_recordings()
    assert len(files) == 2
    assert all(f.suffix == ".enc" for f in files)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
