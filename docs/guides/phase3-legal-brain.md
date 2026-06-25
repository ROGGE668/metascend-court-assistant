# Phase 3: 庭审语义理解与法律策略生成

## 目标

对实时转写文本进行法律语义分析，自动识别对方主张、证据、程序异议，并生成简短应答策略卡片。全部逻辑本地运行。

## 案件领域（MVP）

民间借贷、离婚纠纷、劳动争议、合同纠纷。

## 技术选型

- **意图识别**: 规则引擎 + 轻量 BERT 序列标注（可选）
- **法条/案例检索**: ChromaDB + `BAAI/bge-large-zh-v1.5` 量化版
- **策略生成**: Ollama + `qwen2.5:7b` 或 `llama3.1:8b` 4-bit 量化
- **风险过滤**: 规则 + 本地小模型二次审核

## 模块设计

新增 `src/legal/`：

```
src/legal/
├── __init__.py
├── intent_extractor.py     # 抽取主张、证据、程序异议
├── knowledge_base.py       # 法条/案例/模板向量库管理
├── retriever.py            # RAG 检索
├── strategy_generator.py   # 生成应答策略
├── risk_filter.py          # 过滤高风险/情绪化建议
├── templates.py            # 策略模板库
└── engine.py               # LegalEngine 对外接口
```

## 核心接口

```python
class LegalIntent:
    claim: str | None         # 诉讼请求/主张
    evidence: str | None      # 证据提及
    objection: bool           # 是否程序异议
    legal_ground: str | None  # 对方引用的法条

class Strategy:
    text: str                 # 简短提示文本
    reasoning: str            # 依据（法条/判例）
    risk_level: str           # low / medium / high
    source: str               # rule / rag / llm

class LegalEngine:
    def __init__(self, case_type: CaseType, kb_path: Path): ...
    def extract_intent(self, text: str, speaker_role: Role) -> LegalIntent: ...
    def generate_strategy(self, intent: LegalIntent, context: list[str]) -> Strategy: ...
```

## 意图识别策略

优先级：规则引擎（最快） -> 小模型（可选） -> 兜底 LLM。

规则示例：
- 含“借条”“转账记录” -> 证据相关
- 含“利息超过 LPR 四倍” -> 民间借贷利率抗辩
- 含“加班”“经济补偿金” -> 劳动争议
- 含“感情破裂”“抚养权” -> 离婚纠纷

## 知识库构建

1. **法条库**: 民法典、民事诉讼法、劳动法、相关司法解释。
2. **案例库**: 指导性案例、典型案例的争议焦点和裁判要旨。
3. **模板库**: 按案由和场景（质证、辩论、陈述）组织的应答模板。

数据格式示例（JSONL）：
```json
{"type": "law", "text": "《最高人民法院关于审理民间借贷案件适用法律若干问题的规定》第二十五条...", "metadata": {"topic": "利率", "case_type": "借贷"}}
```

## RAG 流程

1. 对当前转写文本和最近 3 句上下文做 BGE 嵌入。
2. 在 ChromaDB 中检索 Top-K（默认 K=3）相关法条/模板。
3. 将检索结果填入 prompt，交给本地 LLM 生成策略。
4. 风险过滤模型审核输出，标记 high risk 的建议不显示或加警告。

## LLM Prompt 模板

```
你是一名辅助普通当事人的AI法律助手。请根据以下信息给出一句简短的应答建议。
案由：{case_type}
对方发言：{text}
相关法条/模板：{retrieved_context}
要求：
- 不超过 30 字
- 引用具体法条编号
- 不得煽动对抗法庭
- 仅作为参考策略，非最终法律意见
```

## UI 改动

- 字幕区显示 `[角色] 原文`
- 底部新增建议卡片，显示策略文本和依据
- 卡片颜色按 risk_level 区分（绿/黄/红）

## 性能目标

- 意图抽取延迟 < 100ms
- RAG 检索延迟 < 200ms
- LLM 生成延迟 < 2s（7B q4 在 M3/M4/M5 上）
- 整体“发言结束 -> 建议显示” < 3s

## 实现步骤

1. 收集并清洗民事法律知识库（JSONL）。
2. 实现 `knowledge_base.py`，用 ChromaDB 建立本地向量索引。
3. 实现 `retriever.py`，完成嵌入 + 检索。
4. 实现 `intent_extractor.py`，规则引擎优先。
5. 实现 `templates.py`，按案由组织模板。
6. 实现 `strategy_generator.py`，RAG + LLM。
7. 实现 `risk_filter.py`，过滤高风险输出。
8. 实现 `engine.py`，组合以上模块。
9. 修改 `src/pipeline.py`，在 ASR 后调用 LegalEngine。
10. 修改 UI，显示建议卡片。
11. 单元测试：20 段模拟质证/辩论对话，验证合理率 > 75%。

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| LLM 给出错误法律建议 | 强免责声明；RAG 限制在本地知识库；高风险建议过滤 |
| 7B 模型推理慢 | 异步运行在独立进程；必要时降级为规则/模板 |
| 知识库覆盖不足 | 先聚焦 4 个案由；持续增量更新 |
| 用户隐私担忧 | 全部本地运行，不上传；录音加密 |

## 测试计划

- 意图抽取单元测试（20 条标注语料）。
- RAG 检索召回测试（Top-3 命中率 > 80%）。
- 策略生成人工评估（合理率 > 75%）。
- 风险过滤测试（确保不出现煽动性/虚假法条建议）。

## 依赖

- `chromadb>=0.5.0`
- `sentence-transformers>=3.0.0`
- `ollama>=0.4.0`
