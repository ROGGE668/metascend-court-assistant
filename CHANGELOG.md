# 变更日志

## [0.2.0] - 2026-06-20

### Phase 2：说话人分离与角色绑定

+ 新增 `src/diarization/embedding.py`：pyannote 与 mock 声纹嵌入后端
+ 新增 `src/diarization/clustering.py`：在线余弦相似度聚类
+ 新增 `src/diarization/role_binding.py`：法官 / 对方 / 己方 / 证人 / 未知 角色绑定
+ 新增 `src/diarization/engine.py`：统一的 diarization 流程
+ 修复 VAD 对 Silero 512 样本窗口的要求，支持任意长度输入块
+ `src/pipeline.py` 接入 diarization，字幕前显示 `[角色]` 前缀
+ 新增 `tests/test_diarization.py`、`tests/test_integration.py`

### Phase 3：法律大脑

+ 新增 `src/legal/intent_extractor.py`：基于关键词的案由、主张、证据、异议抽取
+ 新增 `src/legal/knowledge_base.py`：本地 ChromaDB + sentence-transformers 向量检索
+ 新增 `src/legal/strategy_generator.py`：规则模板 + RAG + Ollama LLM 策略生成
+ 新增 `src/legal/risk_filter.py`：高风险 / 情绪化建议过滤
+ 新增 `src/legal/llm_client.py`：Ollama 本地大模型客户端
+ 新增 `src/legal/legal_assistant.py`：法律模块门面
+ 新增示例法条库 `data/knowledge_base/` 与策略模板 `data/templates/strategies.yaml`
+ `src/pipeline.py` 接入法律建议，UI 显示 `【建议】...`
+ 新增 `tests/test_legal.py`

### Phase 4：TTS 输出与闪避

+ 新增 `src/tts/engine.py`：基于 macOS `say` 的本地语音合成，支持音量调节与打断
+ 新增 VAD `speaking` 属性，用于 TTS 闪避
+ `src/pipeline.py` 在生成法律建议后，可选通过耳机朗读
+ 新增 `tests/test_tts.py`

### Phase 5：测试、打包与文档

+ 新增 `src/utils/encryption.py`：基于 AES-256-GCM + PBKDF2 的加密/解密
+ 新增 `src/utils/recording_store.py`：加密录音本地存储（WAV -> 加密 .enc）
+ 新增 `src/utils/encrypted_log.py`：AES-256-GCM 加密日志 Handler
+ `src/pipeline.py` 接入可选加密录音（`ENABLE_RECORDING=true`）
+ `src/config.py` 支持开启加密日志（`ENABLE_ENCRYPTED_LOGS=true`）
+ 新增 `scripts/run_mvp.sh`：一键启动桌面流程
+ 新增 `scripts/build_app.sh`：测试 + lint + 构建 macOS 启动器
+ 新增 `tests/test_pipeline.py`、`tests/test_encryption.py`、`tests/test_recording_store.py`
+ 更新 `README.md`、`AGENTS.md`、`.env.example`、`pyproject.toml`
+ 全量快速测试通过（`pytest -m "not slow"`）

### UI 与独立 App 优化

+ 重构 `src/ui/subtitle_window.py`：
  + UI 运行于主线程，解决 macOS 上窗口可能无法渲染的问题
  + 现代化暗色主题（slate / blue 调色板）、1px 边框、圆角视觉
  + 状态指示灯呼吸动画，实时反馈运行状态
  + 标题栏新增静音、最小化、关闭按钮
  + 支持拖拽移动、`M` 静音、`Q` / `Esc` 退出
+ 重构 `src/pipeline.py`：
  + ASR 模型加载与音频采集移至后台线程，主线程专职 UI
  + 启动时立即打印 `Starting Metascend Court Assistant MVP`
+ 修复 `scripts/build_standalone_app.sh`：
  + 移除重复的 `APP_ROOT` 定义
  + 启动脚本立即回显 `Launching Metascend Court Assistant...`
  + 强制设置 `PYTHONUNBUFFERED=1` 与 `PYTHONIOENCODING=utf-8`
+ 新增 `scripts/generate_icon.py`：生成 macOS `.icns` 图标
+ App bundle 包含自定义图标 `assets/AppIcon.icns` 并在 `Info.plist` 中注册
+ 通过 `tests/test_macos_app.py` 验证 `.app` 可正常启动且无异常

### Standalone macOS App

+ 新增 `scripts/build_standalone_app.sh`：构建完全独立的 macOS `.app`，内含 Python 运行时、所有 Python 依赖与本地模型缓存
+ 使用 `uv` 托管的 Python 3.11 副本，通过 `--system --break-system-packages` 安装锁定依赖到 App 内部
+ 启动器设置 `PYTHONHOME` / `PYTHONPATH`，并将运行时缓存重定向到 `~/Library/Caches/com.metascend.court-assistant/`
+ 通过 `tests/test_macos_app.py` 验证 `.app` 可正常启动且无异常
+ 已构建出 `dist/Metascend Court Assistant.app`，支持 Finder 双击打开

### 技术栈迁移

+ 前端与桌面壳切换为 **Tauri 2 + React/TypeScript**，停止维护旧版 Python/Tk 与 `pywebview` 路线
+ 删除旧版 macOS `.app` 打包脚本与相关产物，避免继续沿旧路线分发

## [0.1.0] - 2026-06-20

### 已实现

+ Phase 0：项目骨架搭建
+   - Python 3.11 + uv 虚拟环境
+   - 项目目录结构：`src/`, `tests/`, `docs/`, `scripts/`, `data/`
+   - `AGENTS.md`、`README.md`、`.env.example`
+ Phase 1 MVP：实时语音识别 + 桌面字幕
+   - `src/audio/capture.py` 麦克风采集
+   - `src/audio/vad.py` Silero VAD 语音分割
+   - `src/asr/engine.py` faster-whisper 本地 ASR
+   - `src/ui/subtitle_window.py` tkinter 字幕浮窗
+   - `src/pipeline.py` 主流程编排
+   - `scripts/download_models.py` 模型预下载
+ 测试与代码质量
+   - `tests/test_audio.py`、`tests/test_asr.py`、`tests/conftest.py`
+   - ruff + black 代码规范
+   - 快速测试通过，慢测试（模型加载）可选
+ 开发文档
+   - `docs/architecture.md`
+   - `docs/phase2-diarization.md`
+   - `docs/phase3-legal-brain.md`
+   - `docs/phase4-tts.md`
+   - `docs/phase5-test-deploy.md`
+   - `docs/api-interfaces.md`
+   - `docs/knowledge-base.md`
+   - `docs/privacy-security.md`
+   - `docs/model-card.md`
+   - `docs/user-manual.md`
+   - `docs/deployment-guide.md`

## 版本规划

+ 1.0.0：完成稳定版与试点（需合规与律师监督）
# 变更日志

> 以下历史记录保留原始路径快照。规范化迁移后，推荐使用新路径：
> - `scripts/build_app.sh` -> `scripts/installers/build_app.sh`
> - `scripts/build_standalone_app.sh` -> `scripts/installers/build_standalone_app.sh`
> - `scripts/run_mvp.sh` -> `scripts/installers/run_mvp.sh`
> - `scripts/generate_icon.py` -> `scripts/installers/generate_icon.py`
> - `docs/phase2-diarization.md` -> `docs/guides/phase2-diarization.md`
> - `docs/phase3-legal-brain.md` -> `docs/guides/phase3-legal-brain.md`
> - `docs/phase4-tts.md` -> `docs/guides/phase4-tts.md`
> - `docs/phase5-test-deploy.md` -> `docs/guides/phase5-test-deploy.md`
