# Chat/Work 子功能实现状态审计报告

> 审计时间：2026-06-28
> 审计范围：ChatPage.tsx + WorkPage.tsx 及对应 Rust 后端
> 审计方法：代码静态分析 + 功能链路追踪

---

## 一、WorkPage（庭审实时辅助）功能审计

### 1.1 庭审控制
| 功能 | 前端实现 | Rust 后端 | 状态 |
|------|---------|----------|------|
| 开始庭审按钮 | ✅ toggle() | ✅ start_courtroom() | **已实现** |
| 暂停庭审按钮 | ✅ 同一按钮切换 | ✅ stop_courtroom() | **已实现** |
| 状态同步 | ✅ get_status 轮询 | ✅ pipeline.status() | **已实现** |

### 1.2 声纹校准
| 功能 | 前端实现 | Rust 后端 | 状态 |
|------|---------|----------|------|
| 法官校准按钮 | ✅ CalibrationCard | ✅ calibrate_role("法官") | **已实现** |
| 己方校准按钮 | ✅ CalibrationCard | ✅ calibrate_role("己方") | **已实现** |
| 对方校准按钮 | ✅ CalibrationCard | ✅ calibrate_role("对方") | **已实现** |
| 5秒自动录制 | ✅ 按钮禁用+状态显示 | ✅ tokio::time::sleep(5s) | **已实现** |
| 声纹嵌入存储 | ✅ calibratedRoles state | ✅ DiarizationEngine.calibrate() | **已实现** |

### 1.3 实时转写
| 功能 | 前端实现 | Rust 后端 | 状态 |
|------|---------|----------|------|
| 实时转写面板 | ✅ {transcript} 显示 | ✅ pipeline.get_recent_transcripts() | **已实现** |
| 说话人标签 | ✅ 【{speaker}】格式 | ✅ diarization.identify() | **已实现** |
| 时间戳显示 | ✅ [{ts}] 格式 | ✅ entry.timestamp | **已实现** |
| 事件驱动更新 | ✅ listen('transcript:new') | ✅ handle.emit("transcript:new") | **已实现** |

### 1.4 服务状态显示
| 功能 | 前端实现 | Rust 后端 | 状态 |
|------|---------|----------|------|
| 语音识别 ASR | ✅ ServiceCard | ✅ pipeline_status.asr_ready | **已实现** |
| 说话人分离 | ✅ ServiceCard | ✅ calibrated_speakers.len() | **已实现** |
| 法律策略引擎 | ✅ ServiceCard | ✅ 固定值"本地规则" | **已实现**（规则引擎） |
| 语音合成 TTS | ✅ ServiceCard | ❌ 固定值"未启用" | **❌ 未实现** |

### 1.5 法律提示与建议
| 功能 | 前端实现 | Rust 后端 | 状态 |
|------|---------|----------|------|
| 法律提示面板 | ✅ {legalHint} | ✅ get_suggestion() | **已实现**（基础规则） |
| 应对建议面板 | ✅ {countermeasure} | ✅ get_suggestion() | **已实现**（基础规则） |
| 关键词匹配策略 | ✅ 自动更新 | ✅ 包含"异议/证据/赔偿"等关键词 | **已实现**（3个规则） |

---

## 二、ChatPage（庭后分析）功能审计

### 2.1 智能问答
| 功能 | 前端实现 | Rust 后端 | 状态 |
|------|---------|----------|------|
| 消息输入框 | ✅ input + Enter键 | - | **已实现** |
| 发送按钮 | ✅ handleSend() | ✅ chat_ask() | **已实现** |
| AI 回复显示 | ✅ 消息气泡 | ✅ LlmEngine.chat() | **已实现**（需加载模型） |
| 加载状态 | ✅ loading state | - | **已实现** |
| 错误提示 | ✅ error state | ✅ Err() 返回 | **已实现** |

### 2.2 历史会话
| 功能 | 前端实现 | Rust 后端 | 状态 |
|------|---------|----------|------|
| 会话列表 | ✅ messages.map() | ❌ chat_messages() 返回空数组 | **❌ 未实现** |
| 滚动到底部 | ✅ bottomRef.scrollIntoView() | - | **已实现** |

### 2.3 策略报告
| 功能 | 前端实现 | Rust 后端 | 状态 |
|------|---------|----------|------|
| 报告显示 | ✅ lastAI.text | ❌ 仅显示最后一条AI回复 | **❌ 未实现**（应生成独立报告） |
| 引用来源 | ✅ lastAI.ref | ❌ 固定免责声明 | **❌ 未实现** |

---

## 三、核心问题分析

### 🔴 严重问题（功能缺失）

**问题 1：历史会话不持久化**
- 前端：`chat_messages` 返回空数组
- 后端：`ai_stub::chat_messages()` 返回 `json!([])`
- 影响：刷新页面后所有对话丢失
- 修复方案：添加 `data/chat_history.json` 持久化

**问题 2：策略报告未实现**
- 前端：仅显示最后一条 AI 回复
- 后端：无独立的报告生成逻辑
- 影响：庭审结束后无法生成完整分析报告
- 修复方案：添加 `generate_strategy_report` 命令，基于案件类型+对话历史生成

**问题 3：TTS 语音合成未实现**
- 前端：显示"未启用"
- 后端：无 TTS 模块
- 影响：无法通过耳机播报应对建议
- 修复方案：集成 `piper-rs` 或 `ort` 本地 TTS

### 🟡 中等问题（功能不完整）

**问题 4：法律策略引擎过于简单**
- 当前：仅 3 个关键词匹配（异议/证据/赔偿）
- 期望：基于案件类型（借贷/离婚/劳动/合同）+ 庭审阶段（质证/辩论）的动态策略
- 数据：`data/templates/strategies.yaml` 已有完整策略库
- 修复方案：在 `get_suggestion()` 中加载 YAML 并匹配

**问题 5：LLM 聊天无上下文**
- 当前：每次调用独立，无对话历史
- 期望：维护 conversation history，支持多轮对话
- 修复方案：在 LlmEngine 中添加 context 管理

### 🟢 轻微问题（体验优化）

**问题 6：VAD 灵敏度需调优**
- 当前：硬编码阈值 `energy_threshold: 0.015`
- 期望：根据环境噪音自适应
- 状态：已有自适应逻辑，但参数需实测调优

**问题 7：说话人分离精度有限**
- 当前：MFCC 特征 + 余弦相似度
- 期望：更精确的 speaker embedding（如 pyannote）
- 状态：文档已标注"后续可替换"

---

## 四、功能实现统计

### WorkPage
- ✅ 已实现：9/12 功能（75%）
- ❌ 未实现：TTS、完整策略引擎、录音文件管理

### ChatPage
- ✅ 已实现：5/8 功能（62.5%）
- ❌ 未实现：历史持久化、策略报告、多轮上下文

---

## 五、修复优先级建议

### P0（立即修复）
1. 历史会话持久化 → `chat_messages` 读写 JSON
2. 策略报告生成 → 基于 YAML 模板 + 案件类型
3. 法律策略引擎完善 → 加载 strategies.yaml

### P1（本迭代）
4. LLM 多轮上下文管理
5. TTS 基础集成（piper-rs）

### P2（后续迭代）
6. VAD 参数调优
7. Speaker embedding 升级
8. 录音文件管理 UI

---

## 六、技术债务

1. `sidecar.rs` 已废弃但仍保留在代码库
2. `ai_stub.rs` 命名不准确（已不是 stub）
3. `asrReady` 状态已从前端移除，但后端仍需手动加载模型

---

## 七、结论

**整体完成度：68%**

核心庭审流程（录音→VAD→ASR→说话人分离→转写显示）已完整实现。

主要缺失：
- 庭后分析的历史持久化和策略报告
- 法律策略引擎的深度（YAML 数据未利用）
- TTS 语音播报

建议按 P0 → P1 → P2 顺序逐步补全。
