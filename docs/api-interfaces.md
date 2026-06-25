# API 与模块接口契约

本文档定义 `src/` 各模块之间的数据结构与调用约定，确保 Phase 2-4 能独立开发并正确拼接。

## 核心数据结构

### AudioFrame

```python
@dataclass
class AudioFrame:
    samples: np.ndarray          # float32, [-1.0, 1.0], shape (n_samples,) 或 (n_samples, channels)
    sample_rate: int             # 默认 16000
    timestamp_ms: int            # 相对会话开始的毫秒时间戳
    source: str = "microphone"   # 可选：microphone / bluetooth / file
```

### SpeechSegment

VAD 输出的有效语音段。

```python
@dataclass
class SpeechSegment:
    audio: np.ndarray            # float32 mono, 16kHz
    start_ms: int                # 语音段开始时间
    end_ms: int                  # 语音段结束时间
    source: str = "microphone"
```

### SpeakerSegment

Phase 2 引入，包含说话人信息。

```python
from enum import Enum

class Role(Enum):
    JUDGE = "法官"
    SELF = "己方"
    OPPONENT = "对方"
    WITNESS = "证人"
    UNKNOWN = "未知"

@dataclass
class SpeakerSegment:
    audio: np.ndarray
    start_ms: int
    end_ms: int
    speaker_id: str              # 聚类后的 ID，如 "SPEAKER_00"
    role: Role                   # 绑定后的角色
```

### TranscriptLine

ASR 输出的一行转写。

```python
@dataclass
class TranscriptLine:
    text: str
    start_ms: int
    end_ms: int
    speaker_id: str
    role: Role
    confidence: float | None = None
```

### LegalIntent

Phase 3 引入，法律语义抽取结果。

```python
@dataclass
class LegalIntent:
    claim: str | None = None              # 诉讼请求/主张
    evidence: str | None = None           # 证据提及
    objection: bool = False               # 是否程序异议
    legal_ground: str | None = None       # 对方引用的法条
    case_type: str | None = None          # 案由：借贷/离婚/劳动/合同
    raw_text: str = ""                    # 原始转写文本
```

### Strategy

Phase 3 引入，生成的应答建议。

```python
@dataclass
class Strategy:
    text: str                             # 简短提示文本（<= 30 字）
    reasoning: str                        # 法律依据或推理
    risk_level: str                       # low / medium / high
    source: str                           # rule / rag / llm
    referenced_laws: list[str] = field(default_factory=list)
```

## 模块接口

### AudioCapture

```python
class AudioCapture:
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def read_chunk(self, timeout: float = 0.1) -> np.ndarray | None: ...
```

### VADBuffer

```python
class VADBuffer:
    def process(self, chunk: np.ndarray) -> np.ndarray | None: ...
    def reset(self) -> None: ...
```

### ASREngine

```python
class ASREngine:
    def load(self) -> None: ...
    def unload(self) -> None: ...
    def transcribe(self, audio: np.ndarray) -> str: ...
```

### DiarizationEngine（Phase 2）

```python
class DiarizationEngine:
    def calibrate(self, role: Role, audio: np.ndarray) -> None: ...
    def process(self, audio: np.ndarray) -> list[SpeakerSegment]: ...
    def reset(self) -> None: ...
```

### LegalEngine（Phase 3）

```python
class LegalEngine:
    def __init__(self, case_type: str, kb_path: Path): ...
    def extract_intent(self, text: str, role: Role) -> LegalIntent: ...
    def generate_strategy(self, intent: LegalIntent, context: list[str]) -> Strategy: ...
```

### TTSEngine / TTSPlayer（Phase 4）

```python
class TTSEngine:
    def synthesize(self, text: str) -> np.ndarray: ...
    def synthesize_stream(self, text: str) -> Iterator[np.ndarray]: ...

class TTSPlayer:
    def play(self, audio: np.ndarray) -> None: ...
    def stop(self) -> None: ...
    def is_playing(self) -> bool: ...
```

### SubtitleWindow（旧版 Python/Tk 路线，已弃用）

```python
class SubtitleWindow:
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def update(self, message: str, status: Status) -> None: ...
    def show_strategy(self, strategy: Strategy) -> None: ...   # Phase 3
```

该接口属于旧版桌面 UI。当前前端交付已切换为 **Tauri 2 + React/TypeScript**，不再沿 `SubtitleWindow` / `pywebview` 路线继续扩展。

## 跨线程通信

所有模块均不是线程安全的，跨线程调用通过 `queue.Queue` 传递不可变数据对象（上述 dataclass）。

主流程中的队列：
- `AudioCapture._queue`: `np.ndarray` -> 音频处理线程
- `pipeline._ui_queue`: `(message, status)` -> UI 线程
- Phase 3 后增加 `pipeline._strategy_queue`: `Strategy` -> UI 线程

## 错误处理

- 各模块抛出的异常应在 `pipeline.py` 的循环中捕获，并通过 UI 显示错误状态。
- 模型加载失败应降级：ASR 失败则显示“[ASR 失败]”，LLM 失败则只显示规则/模板策略。

## 扩展约定

- 新增模块时，优先使用 dataclass 定义输入输出。
- 避免在模块间直接传递裸 `np.ndarray` 以外的原始类型。
- 耗时操作（模型推理）应提供 `load()` / `unload()` 生命周期方法，便于内存管理。
