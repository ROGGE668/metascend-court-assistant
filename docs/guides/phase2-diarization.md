# Phase 2: 说话人分离与角色绑定

## 目标

在 Phase 1 实时转写的基础上，为每一句话自动标注说话人角色：法官、对方当事人/律师、己方（用户）、证人、其他。MVP 阶段先支持 2-4 人场景。

## 技术选型

- **嵌入模型**: `pyannote.audio` 3.1 的 `wespeaker-voxceleb-resnet34-LM`
- **分割模型**: `pyannote/segmentation-3.0`
- **聚类**: 在线谱聚类 + 滑动窗口，无需预先知道说话人数
- **角色绑定**: 开庭前 5 秒声纹采样，由用户点选“这是法官 / 这是我 / 这是对方”

## 模块设计

新增 `src/diarization/`：

```
src/diarization/
├── __init__.py
├── embedding.py       # 声纹嵌入提取
├── segmentation.py    # 语音分割（按说话人转换点切分）
├── clustering.py      # 在线聚类，维护 speaker_id -> embedding 映射
├── role_binding.py    # 角色校准与绑定
└── engine.py          # DiarizationEngine 对外接口
```

## 核心接口

```python
class SpeakerSegment:
    start_sample: int
    end_sample: int
    speaker_id: str          # 聚类后的 ID，如 "SPEAKER_00"
    role: Role | None        # 绑定后的角色
    audio: np.ndarray

class DiarizationEngine:
    def __init__(self, sample_rate=16000, max_speakers=4): ...
    def calibrate(self, role: Role, audio: np.ndarray) -> None: ...
    def process(self, audio: np.ndarray) -> list[SpeakerSegment]: ...
    def reset(self) -> None: ...
```

## 数据流改动

```
VAD 输出语音片段 -> DiarizationEngine.process() -> 多个 SpeakerSegment
-> 对每个 segment 调用 ASR -> UI 显示 "[法官] xxxx"
```

## 在线聚类策略

1. 维护一个 `speaker_centroids: dict[str, np.ndarray]`。
2. 新片段提取 embedding 后，与现有 centroids 做余弦相似度比较。
3. 若最大相似度 > 0.65，归入该 speaker；否则新建 speaker。
4. 每次归属后更新该 centroid 为指数移动平均。
5. 当 speaker 数超过 `max_speakers` 时，合并最近最少说话的 speaker。

## 角色校准流程

1. UI 显示“请法官说 5 秒钟话”，用户点击按钮开始采样。
2. 同样流程采样“我方”“对方”“证人”（可选）。
3. 将采样音频的 embedding 与 `Role.JUDGE / Role.SELF / Role.OPPONENT / Role.WITNESS` 绑定。
4. 后续识别中，将 speaker_id 映射到最近的角色 embedding。

## 性能目标

- 说话人切换检测延迟 < 500ms
- 3 人场景识别准确率 > 85%
- 单个 2 秒语音片段的 diarization 耗时 < 200ms（M3/M4/M5）

## 实现步骤

1. 实现 `embedding.py`，封装 pyannote 嵌入提取。
2. 实现 `segmentation.py`，按说话人转换点切分片段。
3. 实现 `clustering.py`，在线谱聚类 + EMA centroid 更新。
4. 实现 `role_binding.py`，校准采样与角色映射。
5. 实现 `engine.py`，组合以上模块。
6. 修改 `src/pipeline.py`，在 VAD 后插入 DiarizationEngine。
7. 修改 `src/ui/subtitle_window.py`，支持显示 `[角色] 文本`。
8. 单元测试：模拟多说话人音频，验证聚类和角色绑定。

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| pyannote 在 Apple Silicon 推理慢 | 使用 `torch.compile` / MPS / int8 量化；缩短分析窗口 |
| 多人同时说话难以区分 | 先标记为重叠语音，待后续分离；或降级为“未知” |
| 法庭噪声影响声纹 | 先用 VAD 滤除非语音段，再提 embedding |
| 用户声音与证人相似 | 增加校准样本长度；允许庭中手动修正角色 |

## 测试计划

- 用两个不同说话人的本地录音测试聚类。
- 模拟“法官-用户-对方”三段语音，验证角色绑定。
- 测试说话人切换延迟。

## 依赖

- `pyannote.audio>=3.3.0`
- `speechbrain>=1.0.0`
- `scikit-learn`（已随 pyannote 引入）
