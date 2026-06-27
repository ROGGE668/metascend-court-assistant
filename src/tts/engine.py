"""Local text-to-speech engine with ducking support."""

import logging
import os
import subprocess
import tempfile
import threading
import time
import wave

import numpy as np
import sounddevice as sd

from src.config import Config

logger = logging.getLogger(__name__)


class TTSEngine:
    """Synthesize and play Chinese speech locally.

    The default "system" backend uses macOS ``say`` to generate a WAV file,
    which is then played through ``sounddevice``. Ducking allows the caller to
    interrupt playback when the user starts speaking.
    """

    def __init__(
        self,
        backend: str = Config.TTS_BACKEND,
        voice: str = Config.TTS_VOICE,
        volume: float = Config.TTS_VOLUME,
    ):
        self.backend = backend
        self.voice = voice
        self.volume = max(0.0, min(1.0, volume))
        self._stop_event = threading.Event()

    def synthesize(self, text: str) -> np.ndarray | None:
        """Return audio samples for the given text, or None on failure."""
        if self.backend == "system":
            return self._synthesize_system(text)
        logger.warning("Unsupported TTS backend: %s", self.backend)
        return None

    def _synthesize_system(self, text: str) -> np.ndarray | None:
        """Generate audio using macOS ``say``."""
        # Filter characters that ``say`` may mishandle.
        safe_text = text.replace(chr(10), " ").replace("\n", " ")
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            wav_path = tmp.name

        try:
            cmd = [
                "say",
                "-v",
                self.voice,
                "-o",
                wav_path,
                "--file-format",
                "WAVE",
                "--data-format",
                "lpcm16@22050",
                safe_text,
            ]
            subprocess.run(cmd, check=True, capture_output=True, text=True)

            with wave.open(wav_path, "rb") as wf:
                nchannels = wf.getnchannels()
                nframes = wf.getnframes()
                raw = wf.readframes(nframes)

            if not raw:
                return None

            audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            if nchannels == 2:
                audio = audio.reshape(-1, 2).mean(axis=1)
            audio *= self.volume
            return audio
        except Exception as e:
            logger.warning("System TTS synthesis failed: %s", e)
            return None
        finally:
            try:
                os.remove(wav_path)
            except Exception:
                pass

    def speak(self, text: str, ducking_callback=None) -> None:
        """Speak the text, stopping early if ``ducking_callback`` returns True."""
        audio = self.synthesize(text)
        if audio is None or len(audio) == 0:
            return

        self._stop_event.clear()
        try:
            sd.play(audio, samplerate=22050)
            stream = sd.get_stream()
            while stream.active and not self._stop_event.is_set():
                if ducking_callback is not None and ducking_callback():
                    logger.debug("TTS ducking triggered")
                    sd.stop()
                    break
                time.sleep(0.05)
            sd.wait()
        except Exception as e:
            logger.warning("TTS playback failed: %s", e)

    def stop(self) -> None:
        """Stop any active TTS playback."""
        self._stop_event.set()
        try:
            sd.stop()
        except Exception:
            pass
