"""Headless orchestration pipeline: audio -> VAD -> [diarization] -> ASR -> state.

This module no longer depends on pywebview.  It exposes a programmatic
`CourtAssistantPipeline` that the Tauri frontend drives through the
FastAPI server in `src.api_server`.
"""

from __future__ import annotations

import logging
import queue
import signal
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

import numpy as np

from src.asr.engine import ASREngine
from src.audio.capture import AudioCapture
from src.audio.vad import VADBuffer
from src.case_archive import CaseArchive, CaseFile
from src.config import Config, configure_logging
from src.data_types import Role, Status, TranscriptLine
from src.diarization.engine import DiarizationEngine
from src.legal import LegalAssistant
from src.tts import TTSEngine
from src.utils.helpers import MovingAverage, current_time_ms
from src.utils.recording_store import RecordingStore

logger = logging.getLogger(__name__)


@dataclass
class PipelineState:
    """In-memory state exposed to the API and frontend.

    This replaces the old pywebview UI callbacks with plain data.
    """

    message: str = ""
    status: Status = Status.IDLE
    service_status: dict[str, str] = field(default_factory=dict)
    suggestion: str = ""
    suggestion_laws: list[str] = field(default_factory=list)
    latency: str = ""
    chat_messages: list[dict] = field(default_factory=list)

    # Realtime transcript exposed to the frontend separately from status messages.
    last_transcript: str = ""
    transcript_log: list[str] = field(default_factory=list)

    is_muted: bool = False
    running: bool = False
    courtroom_running: bool = False
    active_case_id: str | None = None
    active_case_title: str = ""

    def update(self, message: str, status: Status | None = None) -> None:
        self.message = message
        if status is not None:
            self.status = status

    def set_service_status(self, name: str, state: str) -> None:
        self.service_status[name] = state

    def update_suggestion(self, text: str, laws: list[str]) -> None:
        self.suggestion = text
        self.suggestion_laws = laws

    def set_latency(self, text: str) -> None:
        self.latency = text

    def set_status(self, status: Status) -> None:
        self.status = status

    def add_chat_message(self, sender: str, text: str, ref: str) -> None:
        self.chat_messages.append(
            {
                "sender": sender,
                "text": text,
                "ref": ref,
                "time": datetime.now(timezone.utc).isoformat(),
            }
        )

    def start(self) -> None:
        """No-op hook kept for interface parity."""

    def run(self, on_tick=None, tick_ms: int = 200) -> None:
        """Headless main loop used when running the pipeline standalone."""
        while True:
            if on_tick is not None and not on_tick():
                break
            time.sleep(tick_ms / 1000)

    def stop(self) -> None:
        """No-op hook kept for interface parity."""


class CourtAssistantPipeline:
    """End-to-end local pipeline for the courtroom assistant MVP."""

    def __init__(
        self,
        enable_diarization: bool | None = None,
        enable_legal: bool | None = None,
        enable_tts: bool | None = None,
        enable_recording: bool | None = None,
        lazy_init: bool = True,
    ):
        if enable_diarization is None:
            enable_diarization = Config.ENABLE_DIARIZATION
        if enable_legal is None:
            enable_legal = Config.ENABLE_LEGAL_ASSISTANT
        if enable_tts is None:
            enable_tts = Config.ENABLE_TTS
        if enable_recording is None:
            enable_recording = Config.ENABLE_RECORDING

        self._shutdown_event = threading.Event()
        self._audio = AudioCapture()

        # Voice calibration uses the same microphone stream as VAD/courtroom.
        self._calibration_lock = threading.Lock()
        self._calibration_role: Role | None = None
        self._calibration_buffer: list[np.ndarray] = []

        self._vad = VADBuffer()
        self._asr = ASREngine()
        self._case_archive = CaseArchive()
        self._active_case: CaseFile | None = None
        self._state = PipelineState()
        self._ui_queue: queue.Queue[tuple[str, Status]] = queue.Queue()
        self._capture_thread: threading.Thread | None = None
        self._latency_ma = MovingAverage(window=10)

        self._diarization: DiarizationEngine | None = None
        if enable_diarization:
            self._diarization = DiarizationEngine(
                backend=Config.DIARIZATION_BACKEND,
                similarity_threshold=Config.DIARIZATION_SIMILARITY_THRESHOLD,
                role_threshold=Config.DIARIZATION_ROLE_THRESHOLD,
                max_speakers=Config.DIARIZATION_MAX_SPEAKERS,
            )
            logger.info("Diarization enabled (backend=%s)", Config.DIARIZATION_BACKEND)

        self._legal: LegalAssistant | None = None
        if enable_legal:
            self._legal = LegalAssistant(case=self._active_case)
            logger.info("Legal assistant enabled")

        self._tts: TTSEngine | None = None
        if enable_tts:
            self._tts = TTSEngine(
                backend=Config.TTS_BACKEND,
                voice=Config.TTS_VOICE,
                volume=Config.TTS_VOLUME,
            )
            logger.info("TTS enabled (backend=%s)", Config.TTS_BACKEND)

        self._recording_store: RecordingStore | None = None
        if enable_recording:
            self._recording_store = RecordingStore(password=Config.RECORDING_PASSWORD)
            logger.info("Encrypted recording enabled")

        self._chat_legal: LegalAssistant | None = None

        self._ensure_default_case()
        if not lazy_init:
            self._initialize_pipeline()

    # ------------------------------------------------------------------ #
    # Public API for the Tauri frontend
    # ------------------------------------------------------------------ #
    @property
    def state(self) -> PipelineState:
        return self._state

    def get_status(self) -> dict:
        """Return a JSON-friendly status snapshot."""
        return {
            "message": self._state.message,
            "status": self._state.status.value,
            "service_status": self._state.service_status,
            "latency": self._state.latency,
            "courtroom_running": self._state.courtroom_running,
            "active_case": (
                {"case_id": self._active_case.case_id, "title": self._active_case.title}
                if self._active_case
                else None
            ),
        }

    def get_transcript(self) -> str:
        return self._state.last_transcript

    def get_suggestion(self) -> dict:
        return {"text": self._state.suggestion, "laws": self._state.suggestion_laws}

    def get_chat_messages(self) -> list[dict]:
        return self._state.chat_messages

    def toggle_courtroom(self, running: bool | None = None) -> bool:
        """Start or pause realtime courtroom assistance."""
        if running is None:
            running = not self._state.courtroom_running
        self._state.courtroom_running = running
        if running:
            self._state.update("庭审已开始，请开始说话", Status.LISTENING)
            logger.info("Courtroom assistance started")
        else:
            self._state.update("庭审已暂停，点击开始庭审继续", Status.IDLE)
            logger.info("Courtroom assistance paused")
        self._push_service_status()
        return running

    def set_active_case(self, case_id: str) -> bool:
        """Load the selected case and propagate it to the legal assistant."""
        case = self._case_archive.load(case_id)
        if case is None:
            logger.warning("Active case %s not found", case_id)
            return False
        self._active_case = case
        if self._legal is not None:
            self._legal.set_case(case)
        if self._chat_legal is not None:
            self._chat_legal.set_case(case)
        self._state.active_case_id = case.case_id
        self._state.active_case_title = case.title
        logger.info("Active case set: %s (%s)", case.case_id, case.title)
        self._push_service_status()
        return True

    def chat_ask(self, text: str) -> dict:
        """Answer a legal question using the local assistant."""
        try:
            if self._chat_legal is None:
                self._chat_legal = LegalAssistant(case=self._active_case)
            if self._chat_legal.case != self._active_case:
                self._chat_legal.set_case(self._active_case)
            strategy = self._chat_legal.suggest(text)
            response = strategy.text or "暂无明确建议，请补充事实细节。"
            ref = (
                "参考：" + " · ".join(strategy.referenced_laws)
                if strategy.referenced_laws
                else "参考：本地规则模板 / 内置法条"
            )
            self._state.add_chat_message("AI", response, ref)
            return {"sender": "AI", "text": response, "ref": ref}
        except Exception:
            logger.exception("Chat legal suggestion failed")
            error_text = "当前无法调用法律助手，请检查本地环境或稍后重试。"
            self._state.add_chat_message("AI", error_text, "仅供参考，不构成法律意见")
            return {"sender": "AI", "text": error_text, "ref": "仅供参考，不构成法律意见"}

    # ------------------------------------------------------------------ #
    # Voice calibration
    # ------------------------------------------------------------------ #
    def calibrate_role(
        self,
        role: Role,
        audio: np.ndarray | None = None,
        duration_sec: int = 5,
    ) -> bool:
        """Calibrate a courtroom role using a voice sample.

        If ``audio`` is provided it is used directly; otherwise a sample of
        ``duration_sec`` seconds is recorded from the live microphone stream
        that the pipeline already owns.
        """
        if self._diarization is None:
            logger.warning("Diarization is disabled; cannot calibrate role %s", role.value)
            return False
        try:
            if audio is not None:
                self._diarization.calibrate(role, audio)
                logger.info("Calibrated role %s from provided audio", role.value)
                return True

            with self._calibration_lock:
                self._calibration_role = role
                self._calibration_buffer.clear()
            logger.info("Recording calibration sample for role %s", role.value)
            time.sleep(duration_sec)
            with self._calibration_lock:
                self._calibration_role = None
                samples = self._calibration_buffer
                self._calibration_buffer = []
            if not samples:
                logger.warning("No audio captured during calibration for role %s", role.value)
                return False
            calibration_audio = np.concatenate(samples)
            self._diarization.calibrate(role, calibration_audio)
            logger.info(
                "Calibrated role %s from %d chunks (%.2fs)",
                role.value,
                len(samples),
                len(calibration_audio) / self._audio.sample_rate,
            )
            return True
        except Exception:
            logger.exception("Role calibration failed")
            with self._calibration_lock:
                self._calibration_role = None
            return False

    # ------------------------------------------------------------------ #
    # Internal realtime loop
    # ------------------------------------------------------------------ #
    def _push_service_status(self) -> None:
        """Reflect current module states in the realtime service cards."""
        asr_state = "运行中" if self._asr.is_loaded else "初始化中"
        self._state.set_service_status("语音识别 ASR", asr_state)

        if self._diarization is not None:
            self._state.set_service_status("说话人分离", "已启用")
        else:
            self._state.set_service_status("说话人分离", "未启用")

        if self._legal is not None:
            has_case = self._active_case is not None
            self._state.set_service_status("法律策略引擎", "已加载" if has_case else "等待案件")
        else:
            self._state.set_service_status("法律策略引擎", "未启用")

        if self._tts is not None:
            self._state.set_service_status("语音合成 TTS", "就绪")
        else:
            self._state.set_service_status("语音合成 TTS", "未启用")

    def _on_signal(self, _signum, _frame) -> None:
        logger.info("Shutdown signal received")
        self._shutdown_event.set()

    def _tick(self) -> bool:
        """Periodic callback from the headless main loop."""
        return not self._shutdown_event.is_set()

    @staticmethod
    def _format_transcript_line(line: TranscriptLine) -> str:
        """Format a transcript line with speaker/role prefix."""
        label = line.role.value if line.role != Role.UNKNOWN else line.speaker_id
        return f"[{label}] {line.text}"

    def _process_speech_segment(self, audio: np.ndarray) -> None:
        """Run ASR (with optional diarization) and update state."""
        self._state.update("[识别中...]", Status.PROCESSING)
        start_ms = current_time_ms()
        try:
            lines: list[TranscriptLine] = []
            if self._diarization is not None:
                speaker_segments = self._diarization.process(audio)
                for seg in speaker_segments:
                    line = self._asr.transcribe_segment(seg)
                    if line.text:
                        lines.append(line)
            else:
                text = self._asr.transcribe(audio)
                if text:
                    lines.append(
                        TranscriptLine(
                            text=text,
                            start_ms=0,
                            end_ms=0,
                            speaker_id="SPEAKER_00",
                            role=Role.UNKNOWN,
                        )
                    )

            latency_ms = current_time_ms() - start_ms
            self._latency_ma.add(latency_ms)

            if not lines:
                self._state.update("[未识别到语音]", Status.LISTENING)
                return

            transcript = "\n".join(self._format_transcript_line(line) for line in lines)
            self._state.update(transcript, Status.LISTENING)

            self._state.last_transcript = transcript
            self._state.transcript_log.append(transcript)
            # Keep the in-memory log bounded so it does not grow forever.
            max_log = Config.UI_MAX_LINES * 2
            if len(self._state.transcript_log) > max_log:
                self._state.transcript_log = self._state.transcript_log[-max_log:]

            strategy = None
            if self._legal is not None:
                transcript_text = " ".join(line.text for line in lines if line.text)
                self._state.update_suggestion("法律策略分析中...", [])
                self._state.set_status(Status.PROCESSING)
                strategy = self._legal.suggest(transcript_text)
                if strategy.text:
                    self._state.update_suggestion(strategy.text, strategy.referenced_laws)
                else:
                    self._state.update_suggestion("暂无可识别的应对策略", [])
                self._state.set_status(Status.LISTENING)

            if (
                self._tts is not None
                and strategy is not None
                and strategy.text
                and not self._state.is_muted
            ):
                threading.Thread(
                    target=self._tts.speak,
                    args=(strategy.text, lambda: self._vad.speaking),
                    daemon=True,
                ).start()

            latency_text = f"识别耗时 {latency_ms}ms，平均 {self._latency_ma.average:.0f}ms"
            self._state.set_latency(latency_text)
            logger.info("Transcribed: %s (latency=%dms)", latency_text, latency_ms)
        except Exception as e:
            logger.exception("ASR/diarization failed")
            self._state.update(f"[识别失败: {e}]", Status.ERROR)
            self._state.update_suggestion("语音识别或策略生成失败，请检查本地模型状态", [])

    def _capture_loop(self) -> None:
        """Continuously capture audio and feed VAD."""
        logger.info("Audio processing thread started")
        try:
            while not self._shutdown_event.is_set():
                chunk = self._audio.read_chunk(timeout=0.1)
                if chunk is None:
                    continue
                with self._calibration_lock:
                    if self._calibration_role is not None:
                        self._calibration_buffer.append(chunk.copy())
                        continue
                speech_segment = self._vad.process(chunk)
                if speech_segment is not None and len(speech_segment) > 0:
                    if self._recording_store is not None:
                        try:
                            self._recording_store.save(speech_segment)
                        except Exception:
                            logger.exception("Failed to save recording")
                    if not self._state.courtroom_running:
                        continue
                    self._process_speech_segment(speech_segment)
        except Exception:
            logger.exception("Audio processing thread crashed")
        finally:
            self._audio.stop()

    def _initialize_pipeline(self) -> None:
        """Load ASR model and start audio capture on a background thread."""
        try:
            logger.info("Loading ASR model...")
            self._state.update("正在加载语音识别模型...", Status.PROCESSING)
            self._asr.load()
            self._state.update("模型加载完成，请点击「开始庭审」开始实时辅助", Status.LISTENING)
            logger.info("ASR model loaded; starting audio capture")

            self._audio.start()
            self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
            self._capture_thread.start()
            self._push_service_status()
        except Exception:
            logger.exception("Pipeline initialization failed")
            self._state.update("初始化失败，请重启应用", Status.ERROR)
            self._state.set_service_status("语音识别 ASR", "异常")
            self._shutdown_event.set()

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    def start(self) -> None:
        """Start background pipeline work (non-blocking).

        The old pywebview main loop has been replaced by the headless
        `_tick` loop in `run()`.  The FastAPI server calls this method
        during startup and then serves requests on its own thread.
        """
        signal.signal(signal.SIGINT, self._on_signal)
        signal.signal(signal.SIGTERM, self._on_signal)

        logger.info("Starting Metascend Court Assistant MVP")
        print("Starting Metascend Court Assistant MVP", flush=True)

        self._state.start()
        self._state.update("正在加载语音识别模型...", Status.PROCESSING)

        init_thread = threading.Thread(target=self._initialize_pipeline, daemon=True)
        init_thread.start()
        logger.info("Pipeline initialized in background")

    def run(self) -> None:
        """Block on the headless main loop until shutdown."""
        self._state.run(on_tick=self._tick, tick_ms=200)
        self.stop()

    def _ensure_default_case(self) -> None:
        """Create a placeholder case if the archive is empty."""
        cases = self._case_archive.list_cases()
        if cases:
            self.set_active_case(cases[0]["case_id"])
        else:
            case = self._case_archive.create_case("默认案件", "other")
            self.set_active_case(case.case_id)

    def stop(self) -> None:
        """Gracefully stop all components."""
        logger.info("Stopping pipeline")
        self._shutdown_event.set()
        self._audio.stop()
        self._state.stop()
        if self._capture_thread is not None and self._capture_thread.is_alive():
            self._capture_thread.join(timeout=2.0)
        self._asr.unload()
        if self._diarization is not None:
            self._diarization.reset()
        logger.info("Pipeline stopped. Average ASR latency: %.0fms", self._latency_ma.average)


def main() -> int:
    configure_logging()
    print("Starting Metascend Court Assistant MVP", flush=True)
    pipeline = CourtAssistantPipeline(lazy_init=False)
    pipeline.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
