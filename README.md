# Metascend 庭审助手

本地优先的 macOS 案件工作台。当前前端与桌面壳已切换为 **Tauri 2 + React/TypeScript**；当前 macOS 交付已统一为 Tauri 2 原生应用；旧版 Python/Tk 与独立 `.app` 打包产物不再沿旧路线维护。

## 当前状态

**Phase 1-5 MVP 已完成**：

- [x] 音频采集 + Silero VAD
- [x] 说话人分离与角色绑定（Phase 2）
- [x] faster-whisper 本地 ASR
- [x] 法律意图抽取 + RAG + 规则策略（Phase 3）
- [x] 可选本地 LLM（Ollama）
- [x] 可选本地 TTS + 闪避（Phase 4）
- [x] 本地 macOS 案件工作台前端，含顶部状态灯、服务卡片、庭审实时辅助、庭后分析、证据管理、案件档案、设置与用户管理
- [ ] Tauri 2 原生 macOS `.app` 打包与分发

## 运行环境

- macOS 14+
- Apple Silicon MacBook Air / Pro（M1-M5），16GB 内存及以上
- Python 3.11 仅用于本地模型与推理后端开发；前端交付采用 Tauri 2
- 可选：Ollama，用于本地法律问答

## 安装

```bash
uv sync
uv run python scripts/download_models.py
```

国内环境可先设置 Hugging Face 镜像：

```bash
export HF_ENDPOINT=https://hf-mirror.com
uv run python scripts/download_models.py
```

## 启动

```bash
uv run python -m src.pipeline
```

## 打包为可直接打开的 macOS 应用

优先使用完整独立包：

离线网页预览：

```bash
open demo/index.html
```

如需继续本地模型与推理后端开发，仍可通过 Python 后端接口联调；Tauri 桌面壳与原生 `.app` 打包将在后续阶段补齐。

## 故障排查

**前端无法启动或显示异常**

请重新安装前端依赖并重启开发服务器：

```bash
cd frontend
rm -rf node_modules
npm install
npm run dev
```

如仍异常，请确认：

- Node/NPM 可用：`node -v` / `npm -v`
- 前端终端输出不含 `TS` / `vite` 启动报错
- 若使用 Tauri，请确认 `cargo` / `tauri` CLI 可用

## 开发文档

- [Architecture](/docs/architecture.md)
- [Phase Guides](/docs/guides/phase2-diarization.md)
- [Frontend README](/frontend/README.md)
- [Deployment Guide](/docs/deployment-guide.md)
- [User Manual](/docs/user-manual.md)
- [Privacy & Security](/docs/privacy-security.md)

## 测试

```bash
uv run pytest tests/ -v          # fast tests
uv run pytest tests/ --run-slow  # include model-loading tests
```

## 免责声明

本系统输出仅供参考，不构成法律意见。用户对庭上陈述与决策负有最终责任。所有 UI 输出均包含免责提示。
