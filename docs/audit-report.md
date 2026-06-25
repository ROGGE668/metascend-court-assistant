# 项目审计报告

**审计日期：** 2026-06-25  
**审计范围：** 前后端代码匹配、功能实现程度、项目目标达成、问题分析与改进措施  

---

## 1. 整体架构总览

| 层 | 技术栈 | 状态 |
|---|---|---|
| **前端 UI** | Tauri 2 + React/TypeScript + Tailwind | ✅ 界面完整，所有页面可交互 |
| **Rust 桥接层** | Tauri CLI + lib.rs | ⚠️ 仅有 5 个命令，其中 4 个未被前端调用 |
| **Python 后端** | `uv` + faster-whisper + pyannote + ChromaDB | ✅ 模块结构完整，但无 Tauri 连接入口 |
| **数据层** | 本地 JSON 文件 + 本地磁盘文件 | ✅ 基础 CRUD 已实现 |

---

## 2. 前后端功能匹配矩阵

### 2.1 WorkPage（庭审实时辅助）

| 前端功能 | 后端实现 | 匹配情况 |
|---|---|---|
| ASR 状态显示 | `ASREngine` (119行, faster-whisper) | ❌ 前端硬编码 `初始化中`，后端未连接 |
| 说话人分离状态 | `DiarizationEngine` (78行, pyannote) | ❌ 未连接 |
| 法律策略引擎状态 | `LegalAssistant` (25行, 规则引擎+LLM) | ❌ 未连接 |
| TTS 状态 | `TTSEngine` (115行, MeloTTS) | ❌ 未连接 |
| "开始庭审"按钮 | `AudioCapture` (98行, sounddevice) | ❌ 仅切换本地 `running` 状态 |
| 实时转写 | `ASREngine.transcribe_segment()` | ❌ 展示硬编码占位文本 |
| 法律提示 + 应对建议 | `LegalAssistant.analyze_and_generate()` | ❌ 展示硬编码占位文本 |
| 声纹校准录制 | `RoleBinding.calibrate()` + `AudioCapture` | ❌ 按钮无实际作用 |

**结论：WorkPage 所有功能均为 UI 演示，无后端数据流。**

### 2.2 CasePage（案件档案管理）

| 前端功能 | 后端实现 | 匹配情况 |
|---|---|---|
| 案件列表 | `CaseArchive.list_cases()` | ⚠️ 前端使用 `mockCases` 硬编码数组 |
| 案件详情 | `CaseArchive.get_case()` | ⚠️ 未连接 |
| 证据文件列表 | `EvidenceStore.list_evidence()` | ⚠️ 前端使用 `mockEvidence` 硬编码数组 |
| "新建案件"按钮 | `CaseArchive.create_case()` | ❌ 按钮无实际作用 |
| "导入证据"按钮 | `EvidenceStore.import_file()` | ❌ 按钮无实际作用 |
| "查看"/"删除"证据 | `EvidenceStore.get_file()` / `EvidenceStore.delete_evidence()` | ❌ 按钮无实际作用 |

**结论：CasePage 数据为 Mock，后端 CRUD 已实现但未连接。**

### 2.3 ChatPage（庭后分析）

| 前端功能 | 后端实现 | 匹配情况 |
|---|---|---|
| 智能问答 | 无独立问答模块（依赖 `LegalAssistant`） | ❌ 只有 UI 输入框和按钮 |
| 历史会话 | `EncryptedLogStore` | ❌ 显示硬编码 "暂无历史会话" |
| 策略报告 | `StrategyGenerator` | ❌ 显示硬编码 "暂无策略报告" |
| "发送"按钮 | 无后端端点 | ❌ 按钮无实际作用 |

**结论：ChatPage 仅为页面框架，无实际交互能力。**

### 2.4 KnowledgePage（本地向量知识库）

| 前端功能 | 后端实现 | 匹配情况 |
|---|---|---|
| 知识库概览（文档数/向量/分类） | `KnowledgeBase` (法律知识库) | ❌ 前端硬编码 `5` / `2,535` 等数字 |
| 文档列表 + 状态 | `KnowledgeBase.list_documents()` | ❌ 前端使用 `docs` 硬编码数组 |
| 分类筛选 | 无（纯前端分类） | ⚠️ 仅 UI 切换视觉效果 |
| "批量导入" | `KnowledgeBase.import_documents()` | ❌ 按钮无作用 |
| "添加文档" | 同上 | ❌ 按钮无作用 |
| "详情"按钮 | 无实现 | ❌ 按钮无作用 |
| 搜索输入框 | 无搜索实现 | ❌ 输入框不可操作 |

**结论：KnowledgePage 为完整 UI 原型，无任何后端数据或操作绑定。**

### 2.5 SettingsPage（设置）

| 前端功能 | 后端实现 | 匹配情况 |
|---|---|---|
| 功能开关（说话人分离等） | `Config` 类 + `.env` | ❌ 开关仅改变本地 `toggles` 状态 |
| "保存设置"按钮 | `Config.save()` (不存在) | ❌ 按钮无作用 |
| 版本信息 | 硬编码 | ⚠️ 显示固定版本号 |
| "检查更新"按钮 | 无 | ❌ 按钮无作用 |
| 系统日志 | `EncryptedLogStore` | ⚠️ 自检日志通过 `healthLog` 显示，但日志存储未连接 |

**结论：SettingsPage 开关无实际效果，配置持久化不存在。**

### 2.6 App.tsx（全局框架）

| 前端功能 | 后端实现 | 匹配情况 |
|---|---|---|
| 自检状态（服务正常/异常） | Rust `local_backend_status` | ✅ 唯一真连接，通过 Tauri IPC 调用 |
| 页面路由 | 纯前端 | ✅ 正常 |

---

## 3. 关键问题定位

### 🔴 严重问题

| # | 问题 | 影响 | 位置 |
|---|---|---|---|
| P1 | **Python 后端与 Tauri 前端完全脱节** | 所有页面均为"空壳"，无实际功能 | 全局 |
| P2 | `pipeline.py` 依赖已废弃的 `pywebview` UI | 后端无法直接与 Tauri 通信 | `src/pipeline.py:35` |
| P3 | Tauri Rust 层仅有 5 个命令，无 Python 调用入口 | Python 进程未被 Tauri 启动或管理 | `frontend/src-tauri/src/lib.rs` |
| P4 | 无通信协议定义（无 REST / IPC / stdin/stdout） | 前后端之间隔着一堵墙 | 全局 |

### 🟡 中等问题

| # | 问题 | 影响 | 位置 |
|---|---|---|---|
| P5 | 所有页面数据均为 `mock*` 硬编码数组 | 无真实数据驱动 | 所有 `pages/*.tsx` |
| P6 | `EvidencePage.tsx` / `UsersPage.tsx` 无前端引用 | 死代码，页面无法通过路由访问 | `App.tsx` 路由定义 |
| P7 | `src/ui/` 目录为空（`__pycache__` 仅缓存） | pywebview UI 已废弃但目录遗留 | `src/ui/` |
| P8 | 模型下载脚本 `download_models.py` 未适配前端 | 需要手动触发，无 UI 进度反馈 | `scripts/download_models.py` |

### 🟢 轻微问题

| # | 问题 | 位置 |
|---|---|---|
| P9 | Rust `lib.rs` 中 `Manager` 导入未使用（编译警告） | `frontend/src-tauri/src/lib.rs:3` |
| P10 | 多个页面包含未使用的 `useState/useEffect` 导入 | 各 `*.tsx` 文件 |
| P11 | `.env.example` 与 `.env` 内容可能不同步 | `.env`, `.env.example` |

---

## 4. 前后端实现匹配总评

| 评估维度 | 评分 | 说明 |
|---|---|---|
| **前端 UI 完整性** | ⭐⭐⭐⭐⭐ | 所有页面结构、路由、交互视觉完整 |
| **后端模块完整性** | ⭐⭐⭐⭐ | ASR/Diarization/Legal/TTS/Archive 均有真实代码 |
| **前后端集成度** | ⭐ | 仅有健康检查 1 个 IPC 调用 |
| **数据真实性** | ⭐⭐⭐⭐ | 后端 CRUD 真实、前端全部 Mock |
| **测试覆盖** | ⭐⭐⭐ | 17 个测试文件，但无集成测试 |
| **项目目标达成** | ⭐⭐ | UI 达到设计目标，但功能远未达到 |

---

## 5. 改进措施

### 必须解决（优先级 P1-P3）

1. **建立 Tauri ↔ Python 通信桥**
   - 方案：Tauri 通过 `sidecar` 启动 Python 进程，通过 `stdin/stdout` JSON 通信
   - 或：Python 启动轻量 HTTP 服务器（如 FastAPI），Tauri 通过 `localhost` 调用

2. **废弃 pywebview 管道，重构 pipeline.py**
   - 移除 `WebviewWindow` / `SubtitleWindow` 依赖
   - 暴露 `CourtAssistantPipeline` 为 HTTP 或 WebSocket 服务

### 推荐解决（优先级 P4-P6）

3. **前端页面接入真实后端数据**
   - WorkPage: `invoke('start_listening')` → Python ASR pipeline
   - CasePage: `invoke('list_cases')` → Python CaseArchive
   - KnowledgePage: `invoke('list_documents')` → Python KnowledgeBase

4. **删除 / 合并无用页面**
   - `EvidencePage.tsx` → 合并到 CasePage（已实现）
   - `UsersPage.tsx` → 删除（用户已移除）

5. **添加 Tauri 命令通知 Python 后端**
   - `start_audio_capture`
   - `stop_audio_capture`
   - `get_transcript`
   - `list_cases` / `create_case`
   - `search_knowledge`

### 建议解决（优先级 P7-P11）

6. 清理 Rust 编译警告
7. 更新 `.env.example` 与 `.env` 同步
8. 添加集成测试（Tauri → Python 端到端）

---

## 6. 审查总结

- **假设:** Python 后端代码质量可靠可以作为真实引擎；Tauri 前端 Mock 数据需要全部替换为真实数据流
- **检查项:**
  - [x] 正确性 — 项目 UI 正确运行，但前后端集成严重缺失
  - [x] 简洁性 — 无过度设计，但存在废弃代码（pywebview / EvidencePage / UsersPage）
  - [x] 最小改动 — 当前为原型阶段，需做架构调整而非微观修改
  - [x] 风格一致 — 前后端命名风格分离（Rust/Python/TypeScript 各有一套）
  - [x] 安全 — 目前无数据泄露风险（因为无数据传输）
  - [x] 验证 — 已对所有前端页面和后端模块逐一核对

- **遗留问题:** 无通信桥是项目继续推进的最大的障碍
- **信心:** 中 — 页面 UI 和 Python 后端各自质量可靠，但集成方案需要重新设计
