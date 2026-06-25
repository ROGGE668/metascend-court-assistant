# Phase 4: 语音合成输出与隐蔽交互

## 目标

将 Phase 3 生成的策略文本通过蓝牙耳机/骨传导耳机低延迟播报给用户，并在用户说话时自动压低或暂停（闪避）。

## 技术选型

- **TTS 引擎**: `MeloTTS` 量化版或 `ChatTTS` 量化版
- **音频输出**: `sounddevice` OutputStream
- **闪避逻辑**: 结合 VAD 检测用户语音，自动压低 TTS 音量或暂停
- **硬件**: 普通蓝牙耳机或骨传导耳机；MVP 阶段不绑定特定硬件

## 模块设计

新增 `src/tts/`：

```
src/tts/
├── __init__.py
├── engine.py          # TTS 引擎封装
├── player.py          # 流式音频播放
└── ducker.py          # 音频闪避
```

## 核心接口

```python
class TTSEngine:
    def __init__(self, model_name: str = "melo-zh-cn", device: str = "auto"): ...
    def synthesize(self, text: str) -> np.ndarray: ...
    def synthesize_stream(self, text: str) -> Iterator[np.ndarray]: ...

class TTSPlayer:
    def __init__(self, sample_rate: int = 24000): ...
    def play(self, audio: np.ndarray) -> None: ...
    def stop(self) -> None: ...
    def is_playing(self) -> bool: ...

class AudioDucker:
    def __init__(self, vad_buffer: VADBuffer, attenuation_db: float = 12.0): ...
    def process(self, tts_chunk: np.ndarray, user_is_speaking: bool) -> np.ndarray: ...
```

## 数据流

```
LegalEngine 生成策略文本 -> TTSEngine.synthesize_stream()
-> TTSPlayer.play() + AudioDucker.process()
-> 蓝牙耳机/骨传导耳机
```

## 闪避策略

- **Level 1**: 检测到用户开始说话，将 TTS 音量衰减 12dB。
- **Level 2**: 用户持续说话超过 500ms，暂停 TTS，记录播放位置。
- **Level 3**: 用户停止说话 800ms 后，从暂停位置恢复播放。
- 提供用户可配置的“不闪避”模式。

## 隐蔽模式

- 一键静音：空格 / 耳机触控 / 系统快捷键。
- 纯黑屏模式：UI 只保留一个极小的状态指示灯。
- 日志与录音默认不显示，需密码/生物识别解锁。

## 性能目标

- TTS 首包延迟 < 300ms
- 端到端“策略生成 -> 耳机出声” < 4s
- 闪避响应延迟 < 200ms

## 实现步骤

1. 调研并选定中文本地 TTS 模型（MeloTTS 优先，轻量）。
2. 实现 `engine.py`，封装 TTS 推理。
3. 实现 `player.py`，流式播放音频。
4. 实现 `ducker.py`，基于 VAD 的闪避。
5. 在 `src/pipeline.py` 中接入 TTS 分支（可选开关）。
6. 增加 UI 控制：TTS 开关、音量、闪避级别。
7. 增加隐蔽模式快捷键。
8. 测试：安静环境和背景音乐下的可懂度、延迟。

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| TTS 模型占用显存/内存 | 独立进程；按需加载；长文本分段合成 |
| 耳机延迟高 | 优先支持低延迟编解码耳机；提供有线耳机回退 |
| TTS 被旁人听到 | 默认较低音量；骨传导耳机定向传播；一键静音 |
| 闪避过于敏感 | 可配置阈值；结合说话人角色判断 |

## 测试计划

- TTS 合成速度测试。
- 闪避响应测试（用户说话 -> TTS 暂停时间）。
- 耳机播放可懂度测试（安静/噪声环境）。
- 一键静音响应测试。

## 依赖

- `MeloTTS` 或 `ChatTTS`（待确定具体包名）
- `sounddevice`（已引入）
