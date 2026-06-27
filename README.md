# Metascend 庭审助手

本地优先的 macOS 案件工作台。当前前端与桌面壳已切换为 **Tauri 2 + React/TypeScript**，后端已全面迁移为 **Rust**；旧版 Python 后端、Python/Tk UI 与独立 `.app` 打包产物不再维护并已从仓库删除。

## 当前状态

**Phase A 已完成**：后端 Rust 化，数据层（案件、证据、知识库、设置）由 Rust 直接处理。

- [x] 案件管理（Rust JSON 持久化）
- [x] 证据导入与管理（Rust 文件系统）
- [x] 知识库文档列表与内容查看（Rust 本地文件）
- [x] 设置持久化（Rust JSON）
- [ ] 庭审实时辅助（等待 Rust AI Phase B-D）
- [ ] 声纹校准（等待 Rust AI Phase C）
- [ ] 法律策略 / 聊天（等待 Rust AI Phase D）
- [ ] 语音合成 TTS（等待 Rust AI Phase E）

## 运行环境

- macOS 14+
- Apple Silicon MacBook Air / Pro（M1-M5），16GB 内存及以上
- 后端：Rust（Tauri 2），不再依赖 Python 运行时

## 安装

```bash
cd frontend
npm install
```

## 开发启动

```bash
cd frontend
npm run tauri dev
```

## 打包为可直接打开的 macOS 应用

```bash
cd frontend
CI=true npm run tauri build
```

或使用封装脚本：

```bash
./scripts/build_app.sh
```

构建产物位于 `frontend/src-tauri/target/release/bundle/macos/Metascend Court Assistant.app`。

## 故障排查

**前端无法启动或显示异常**

请重新安装前端依赖并重启开发服务器：

```bash
cd frontend
rm -rf node_modules
npm install
npm run tauri dev
```

如仍异常，请确认：

- Node/NPM 可用：`node -v` / `npm -v`
- Rust 工具链可用：`cargo --version`
- 前端终端输出不含 `TS` / `vite` / `cargo` 启动报错

## 开发文档

- [Architecture](/docs/architecture.md)
- [Backend Tech Spec](/docs/tech-spec-backend.md)
- [Phase Guides](/docs/guides/)
- [Frontend README](/frontend/README.md)
- [Deployment Guide](/docs/deployment-guide.md)
- [User Manual](/docs/user-manual.md)
- [Privacy & Security](/docs/privacy-security.md)

## 测试

```bash
cd frontend/src-tauri
cargo test
```

## 免责声明

本系统输出仅供参考，不构成法律意见。用户对庭上陈述与决策负有最终责任。所有 UI 输出均包含免责提示。
