"""Low-latency audio capture using sounddevice."""

import logging
import queue
from threading import Event

import numpy as np
import sounddevice as sd

from src.config import Config

logger = logging.getLogger(__name__)


class AudioCapture:
    """Captures microphone audio into a thread-safe queue."""

    def __init__(
        self,
        sample_rate: int = Config.SAMPLE_RATE,
        channels: int = Config.CHANNELS,
        chunk_duration_ms: int = Config.CHUNK_DURATION_MS,
        device: int | str | None = None,
    ):
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_samples = int(sample_rate * chunk_duration_ms / 1000)
        self.device = device
        self._queue: queue.Queue[np.ndarray] = queue.Queue()
        self._stop_event = Event()
        self._stream: sd.InputStream | None = None

    def _callback(self, indata: np.ndarray, frames: int, _time_info, _status) -> None:
        if _status:
            logger.debug("Audio status: %s", _status)
        # sounddevice gives float32 in [-1, 1]
        if self.channels == 1 and indata.ndim > 1:
            indata = indata.mean(axis=1, keepdims=True)
        self._queue.put(indata.copy())

    def start(self) -> None:
        """Start the input stream."""
        logger.info(
            "Starting audio capture: rate=%d, channels=%d, chunk_samples=%d",
            self.sample_rate,
            self.channels,
            self.chunk_samples,
        )
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            blocksize=self.chunk_samples,
            device=self.device,
            dtype=np.float32,
            callback=self._callback,
        )
        self._stream.start()

    def stop(self) -> None:
        """Stop the input stream and drain the queue."""
        logger.info("Stopping audio capture")
        self._stop_event.set()
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def read_chunk(self, timeout: float = 0.1) -> np.ndarray | None:
        """Read a single audio chunk. Returns None if stopped or timeout."""
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    @property
    def is_active(self) -> bool:
        return self._stream is not None and self._stream.active

    @staticmethod
    def list_devices() -> list[dict]:
        """Return a list of input devices."""
        devices = []
        for idx, dev in enumerate(sd.query_devices()):
            if dev["max_input_channels"] > 0:
                devices.append(
                    {
                        "index": idx,
                        "name": dev["name"],
                        "channels": dev["max_input_channels"],
                        "default_samplerate": dev["default_samplerate"],
                    }
                )
        return devices
