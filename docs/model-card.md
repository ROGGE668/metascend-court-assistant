# 模型清单与选型依据

## 总体策略

所有模型本地运行，优先选择开源、支持中文、可在 Apple Silicon 上高效推理的模型。模型按模块分阶段加载，支持 `load()` / `unload()` 生命周期管理。

## ASR: faster-whisper

+ **默认模型**: `Systran/faster-whisper-large-v3-turbo`
+ **备选**: `Systran/faster-whisper-base`（仅测试）
+ **大小**: 约 1.5GB（large-v3-turbo）/ 75MB（base）
+ **推理后端**: CTranslate2，支持 CPU / MPS / CUDA
+ **默认配置**: `compute_type=int8`, `beam_size=5`, `language=zh`
+ **选型理由**: 流式友好、中文准确率高、社区成熟、支持热词注入。

## VAD: Silero VAD

+ **模型**: `silero_vad` v5
+ **来源**: `snakers4/silero-vad`
+ **大小**: 约 2MB
+ **选型理由**: 轻量、无需训练、对中文语音效果好。

## Speaker Embedding / Diarization: pyannote.audio

+ **分割模型**: `pyannote/segmentation-3.0`
+ **嵌入模型**: `pyannote/wespeaker-voxceleb-resnet34-LM`
+ **大小**: 约 100-200MB
+ **选型理由**: 开源说话人分离框架标杆，支持预训练模型直接推理。

## Text Embedding: BGE

+ **模型**: `BAAI/bge-large-zh-v1.5`
+ **输出维度**: 1024
+ **大小**: 约 1.3GB（全精度）/ 量化后约 400MB
+ **选型理由**: 中文语义检索效果领先，适合法条/案例检索。

## LLM: Qwen / Llama

+ **默认**: `qwen2.5:7b`（通过 Ollama 加载 4-bit 量化版）
+ **备选**: `llama3.1:8b` 中文法律版
+ **大小**: 约 4-5GB（q4）
+ **选型理由**: Qwen 中文能力优于同尺寸 Llama；7B 在 16GB MacBook 上可跑。

## TTS: MeloTTS / ChatTTS

+ **候选**: `MeloTTS`（轻量，优先） / `ChatTTS`（更自然，更重）
+ **状态**: Phase 4 再最终确定
+ **要求**: 中文自然、首包延迟 < 300ms、支持流式

## 模型生命周期

+ 应用启动时仅加载 VAD 和 ASR。
+ Diarization 模型在首次进入 Phase 2 时按需加载。
+ BGE / LLM 在首次进入 Phase 3 时按需加载。
+ TTS 在 Phase 4 按需加载。
+ 内存不足时，优先卸载 LLM 和 TTS，保留 ASR/VAD。

## 许可证汇总

| 模型 | 许可证 |
|------|--------|
| faster-whisper | MIT |
| Silero VAD | CC BY 4.0 / 商业需授权 |
| pyannote.audio | MIT |
| BGE | MIT |
| Qwen2.5 | 阿里云 Qwen License |
| MeloTTS | MIT |

## 量化与加速

+ ASR: `int8` 量化，CPU/MPS 推理。
+ Embedding: 使用 `sentence-transformers` 的量化选项或 ONNX Runtime。
+ LLM: 通过 Ollama 加载 4-bit 量化模型。
+ Diarization: 尝试 `torch.compile` 和 MPS 后端加速。
