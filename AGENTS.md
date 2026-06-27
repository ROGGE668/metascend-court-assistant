# Metascend 庭审助手 - Agent Context

## Project Mission
以 **本地优先** 方式构建 **macOS 案件工作台**，面向普通人提供本地案件辅助。当前版本完整运行在 MacBook Air/Pro（M1-M5，16GB+）上，默认无云端依赖。

## Current Repo Layout
- `frontend/src-tauri/src/`: Rust 后端（Tauri 命令、数据持久化、AI stub）
- `frontend/src/`: Tauri 2 + React/TypeScript 桌面壳与 macOS 风格 UI
- `scripts/build_app.sh`: Tauri macOS `.app` 打包脚本
- `docs/`: 用户、部署、架构与阶段指南文档
- `docs/guides/`: 分阶段实现指南
- `design/`: UI 设计资产与浏览器 fixture 页面
- `data/`: 本地案件、证据、知识库、录音、模板、用户数据

## 当前阶段
**Phase A（进行中）**：后端已全面 Rust 化。
- Rust 直接处理案件、证据、知识库、设置等数据 API。
- 庭审实时辅助、声纹校准、法律聊天等 AI 功能已移除 Python 后端，当前以 stub 形式保留接口，后续按 Phase B-E 逐步以 Rust 原生实现。

前端已切换为 **Tauri 2 + React/TypeScript**；旧版 Python/Tk、`pywebview` 桌面 UI 与 Python 后端源码已不再维护并已从仓库删除。

All reasoning is local. No cloud APIs are used by default.

## Architecture Constraints
- 后端唯一运行时：Tauri Rust（`frontend/src-tauri/src/`）
- 数据持久化：本地 JSON + 文件系统
- 前端：Tauri 2 + React/TypeScript on macOS
- 默认无云端依赖；后续 AI 能力通过 Rust crate / ONNX 本地实现
- 配置通过 `frontend/src-tauri` 的 Rust 设置存储管理

## Key Directories
- `frontend/src-tauri/src/`: Rust 后端（cases/evidence/knowledge/settings/ai_stub）
- `frontend/src/`: Tauri app shell、页面、样式
- `scripts/build_app.sh`: Tauri `.app` 构建脚本
- `docs/`: 架构、部署、隐私、用户手册
- `docs/guides/`: 分阶段实现指南
- `design/`: UI 设计参考与 fixture 浏览器页面
- `data/`: 本地知识库、模板、录音（保留用户数据，兼容 Rust 数据层）

## Commands
- `cd frontend && npm run dev` — 前端开发服务器
- `cd frontend && npm run tauri dev` — Tauri 开发模式（Rust 后端热重载）
- `cd frontend && CI=true npm run tauri build` — 生产打包为 macOS `.app`
- `./scripts/build_app.sh` — 封装好的打包脚本
- `cd frontend/src-tauri && cargo test` — Rust 单元测试

## Rules
1. Never add cloud-only APIs or services.
2. Keep dependencies minimal for each phase.
3. 数据文件必须可迁移、可版本控制或明确排除。
4. Rust 公共函数与模块需添加中文或英文 docstring。
5. 所有 UI 输出必须包含法律免责声明。
6. 优先使用标准库与成熟 crate；新增 AI 依赖必须有明确的本地模型路径。
7. 不在 Rust 后端中残留 Python 调用或网络模型下载。
8. 保持前端 `invoke` 命令签名稳定，AI 功能降级时返回明确的提示信息。

## Legal Disclaimer
All outputs from this system are **reference suggestions only**, not legal advice. Users must retain final decision-making authority. Include a disclaimer in all UI outputs.
