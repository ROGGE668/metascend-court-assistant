"""Main orchestration pipeline: audio -> VAD -> [diarization] -> ASR -> UI.

The pywebview UI runs on the main thread and uses the native WebKit engine;
all heavy work (ASR model loading, audio capture, inference) happens on
background threads.
"""

import logging
import queue
import signal
import sys
import threading

import numpy as np

from src.asr.engine import ASREngine
from src.audio.capture import AudioCapture
from src.audio.vad import VADBuffer
from src.case_archive import CaseArchive, CaseFile
from src.config import Config, configure_logging
from src.data_types import Role, TranscriptLine
from src.diarization.engine import DiarizationEngine
from src.legal import LegalAssistant
from src.tts import TTSEngine
from src.ui.subtitle_window import SubtitleWindow
from src.ui.types import Status
from src.ui.webview_window import WebviewWindow
from src.utils.helpers import MovingAverage, current_time_ms
from src.utils.recording_store import RecordingStore

logger = logging.getLogger(__name__)


class CourtAssistantPipeline:
    """End-to-end local pipeline for the courtroom assistant MVP."""

    def __init__(
        self,
        enable_diarization: bool | None = None,
        enable_legal: bool | None = None,
        enable_tts: bool | None = None,
        enable_recording: bool | None = None,
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
        self._vad = VADBuffer()
        self._asr = ASREngine()
        self._case_archive = CaseArchive()
        self._active_case: CaseFile | None = None
        if WebviewWindow.is_available():
            self._ui = WebviewWindow()
        else:
            logger.warning("pywebview not available; falling back to Tkinter UI")
            self._ui = SubtitleWindow()
        self._ui_queue: queue.Queue[tuple[str, Status]] = queue.Queue()
        self._capture_thread: threading.Thread | None = None
        self._latency_ma = MovingAverage(window=10)

        self._courtroom_running = False

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

    def calibrate_role(self, role: Role, audio) -> bool:
        """Calibrate a courtroom role using a voice sample."""
        if self._diarization is None:
            logger.warning("Diarization is disabled; cannot calibrate role %s", role.value)
            return False
        self._diarization.calibrate(role, audio)
        logger.info("Calibrated role %s", role.value)
        return True

    def toggle_courtroom(self, running: bool) -> None:
        """Start or pause realtime courtroom assistance."""
        self._courtroom_running = running
        if running:
            self._ui.set_status(Status.LISTENING)
            self._ui.update("庭审已开始，请开始说话", Status.LISTENING)
            logger.info("Courtroom assistance started")
        else:
            self._ui.set_status(Status.IDLE)
            self._ui.update("庭审已暂停，点击开始庭审继续", Status.IDLE)
            logger.info("Courtroom assistance paused")

    def _push_service_status(self) -> None:
        """Reflect current module states in the realtime service cards."""
        asr_state = "运行中" if self._asr.is_loaded else "初始化中"
        self._ui.set_service_status("语音识别 ASR", asr_state)

        if self._diarization is not None:
            self._ui.set_service_status("说话人分离", "已启用")
        else:
            self._ui.set_service_status("说话人分离", "未启用")

        if self._legal is not None:
            has_case = self._active_case is not None
            self._ui.set_service_status("法律策略引擎", "已加载" if has_case else "等待案件")
        else:
            self._ui.set_service_status("法律策略引擎", "未启用")

        if self._tts is not None:
            self._ui.set_service_status("语音合成 TTS", "就绪")
        else:
            self._ui.set_service_status("语音合成 TTS", "未启用")

    def _on_chat_send(self, text: str) -> None:
        """Handle a Chat-mode legal question using local rule/RAG fallback."""
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
            self._ui.add_chat_message("AI", response, ref)
        except Exception:
            logger.exception("Chat legal suggestion failed")
            self._ui.add_chat_message(
                "AI",
                "当前无法调用法律助手，请检查本地环境或稍后重试。",
                "仅供参考，不构成法律意见",
            )

    def _on_signal(self, _signum, _frame) -> None:
        logger.info("Shutdown signal received")
        self._shutdown_event.set()

    def _tick(self) -> bool:
        """Periodic callback from the UI main loop."""
        return not self._shutdown_event.is_set()

    @staticmethod
    def _format_transcript_line(line: TranscriptLine) -> str:
        """Format a transcript line with speaker/role prefix."""
        label = line.role.value if line.role != Role.UNKNOWN else line.speaker_id
        return f"[{label}] {line.text}"

    def _process_speech_segment(self, audio: np.ndarray) -> None:
        """Run ASR (with optional diarization) and update the UI."""
        self._ui.update("[识别中...]", Status.PROCESSING)
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
                self._ui.update("[未识别到语音]", Status.LISTENING)
                return

            transcript = "\n".join(self._format_transcript_line(line) for line in lines)
            self._ui.update(transcript, Status.LISTENING)

            strategy = None
            if self._legal is not None:
                transcript_text = " ".join(line.text for line in lines if line.text)
                self._ui.update_suggestion("法律策略分析中...", [])
                self._ui.set_status(Status.PROCESSING)
                strategy = self._legal.suggest(transcript_text)
                if strategy.text:
                    self._ui.update_suggestion(strategy.text, strategy.referenced_laws)
                else:
                    self._ui.update_suggestion("暂无可识别的应对策略", [])
                self._ui.set_status(Status.LISTENING)

            if (
                self._tts is not None
                and strategy is not None
                and strategy.text
                and not self._ui.is_muted
            ):
                threading.Thread(
                    target=self._tts.speak,
                    args=(strategy.text, lambda: self._vad.speaking),
                    daemon=True,
                ).start()

            latency_text = f"识别耗时 {latency_ms}ms，平均 {self._latency_ma.average:.0f}ms"
            self._ui.set_latency(latency_text)
            logger.info("Transcribed: %s (latency=%dms)", latency_text, latency_ms)
        except Exception as e:
            logger.exception("ASR/diarization failed")
            self._ui.update(f"[识别失败: {e}]", Status.ERROR)
            self._ui.update_suggestion("语音识别或策略生成失败，请检查本地模型状态", [])

    def _capture_loop(self) -> None:
        """Continuously capture audio and feed VAD."""
        logger.info("Audio processing thread started")
        try:
            while not self._shutdown_event.is_set():
                chunk = self._audio.read_chunk(timeout=0.1)
                if chunk is None:
                    continue
                speech_segment = self._vad.process(chunk)
                if speech_segment is not None and len(speech_segment) > 0:
                    if self._recording_store is not None:
                        try:
                            self._recording_store.save(speech_segment)
                        except Exception:
                            logger.exception("Failed to save recording")
                    if not self._courtroom_running:
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
            self._asr.load()
            self._ui.update("模型加载完成，请点击「开始庭审」开始实时辅助", Status.LISTENING)
            logger.info("ASR model loaded; starting audio capture")

            self._audio.start()
            self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
            self._capture_thread.start()
            self._push_service_status()
        except Exception:
            logger.exception("Pipeline initialization failed")
            self._ui.update("初始化失败，请重启应用", Status.ERROR)
            self._ui.set_service_status("语音识别 ASR", "异常")
            self._shutdown_event.set()

    def start(self) -> None:
        """Start the UI on the main thread and background pipeline work."""
        signal.signal(signal.SIGINT, self._on_signal)
        signal.signal(signal.SIGTERM, self._on_signal)

        logger.info("Starting Metascend Court Assistant MVP")
        print("Starting Metascend Court Assistant MVP", flush=True)

        # Build UI on the main thread; returns immediately.
        self._ui.start()
        self._ui.update("正在加载语音识别模型...", Status.PROCESSING)

        # Wire up Chat-mode legal Q&A.
        self._ui.on_chat_send = self._on_chat_send

        # Wire up role voice calibration.
        self._ui.on_calibrate = self.calibrate_role

        # Wire up active case selection from UI.
        self._ui.on_set_active_case = self._on_set_active_case

        # Wire up courtroom start/pause from the realtime UI.
        self._ui.on_toggle_courtroom = self.toggle_courtroom

        # Ensure there is at least one case for immediate use.
        self._ensure_default_case()

        # Heavy initialization runs in the background so the window appears instantly.
        init_thread = threading.Thread(target=self._initialize_pipeline, daemon=True)
        init_thread.start()

        logger.info("Pipeline running. Press 'q' in subtitle window or Ctrl+C to exit.")

        # Block on the UI main loop.  _tick lets signals shut us down cleanly.
        self._ui.run(on_tick=self._tick, tick_ms=200)

        # UI closed or shutdown requested; clean up.
        self.stop()

    def _ensure_default_case(self) -> None:
        """Create a placeholder case if the archive is empty."""
        cases = self._case_archive.list_cases()
        if cases:
            self._on_set_active_case(cases[0]["case_id"])
        else:
            case = self._case_archive.create_case("默认案件", "other")
            self._on_set_active_case(case.case_id)

    def _on_set_active_case(self, case_id: str) -> None:
        """Load the selected case and propagate it to the legal assistant."""
        case = self._case_archive.load(case_id)
        if case is None:
            logger.warning("Active case %s not found", case_id)
            return
        self._active_case = case
        if self._legal is not None:
            self._legal.set_case(case)
        if self._chat_legal is not None:
            self._chat_legal.set_case(case)
        logger.info("Active case set: %s (%s)", case.case_id, case.title)
        self._push_service_status()

    def stop(self) -> None:
        """Gracefully stop all components."""
        logger.info("Stopping pipeline")
        self._shutdown_event.set()
        self._audio.stop()
        self._ui.stop()
        if self._capture_thread is not None and self._capture_thread.is_alive():
            self._capture_thread.join(timeout=2.0)
        self._asr.unload()
        if self._diarization is not None:
            self._diarization.reset()
        logger.info("Pipeline stopped. Average ASR latency: %.0fms", self._latency_ma.average)


def main() -> int:
    configure_logging()
    print("Starting Metascend Court Assistant MVP", flush=True)
    pipeline = CourtAssistantPipeline()
    pipeline.start()
    return 0


if __name__ == "__main__":
    sys.exit(main())
