# 法律知识库数据工程指南

## 目标

构建一个本地可维护、可增量更新的法律知识库，供 Phase 3 的 RAG 检索使用。覆盖 MVP 四类民事案由：民间借贷、离婚纠纷、劳动争议、合同纠纷。

## 知识库组成

```
data/knowledge_base/
├── laws/                    # 法律法规
│   ├── civil_code.jsonl
│   ├── civil_procedure.jsonl
│   ├── labor_law.jsonl
│   └── judicial_opinions/   # 司法解释
├── cases/                   # 典型案例
│   ├── lending_cases.jsonl
│   ├── divorce_cases.jsonl
│   ├── labor_cases.jsonl
│   └── contract_cases.jsonl
└── templates/               # 策略模板
    ├── lending_templates.jsonl
    ├── divorce_templates.jsonl
    ├── labor_templates.jsonl
    └── contract_templates.jsonl
```

## 数据格式

统一使用 JSONL，每行一个条目：

```json
{"type": "law", "text": "《民法典》第六百七十九条：自然人之间的借款合同，自贷款人提供借款时成立。", "metadata": {"topic": "借款合同成立", "case_type": "借贷", "source": "民法典"}}
{"type": "case", "text": "裁判要旨：仅有转账凭证不能证明借贷关系成立，需结合聊天记录、借条等综合认定。", "metadata": {"topic": "借贷举证", "case_type": "借贷", "source": "指导性案例"}}
{"type": "template", "text": "对方仅凭转账记录主张借款，可回应：转账不等于借款，请对方进一步证明借贷合意。", "metadata": {"topic": "借贷抗辩", "case_type": "借贷", "scene": "质证"}}
```

字段说明：
- `type`: law / case / template
- `text`: 检索和生成的文本内容
- `metadata`: 用于过滤和显示的元数据

## 数据来源

- **法律法规**: 国家法律法规数据库（需手动整理或购买结构化数据）。
- **司法解释**: 最高人民法院发布的司法解释。
- **指导性案例**: 最高人民法院指导案例、公报案例。
- **策略模板**: 由执业律师按场景梳理。

## 数据清洗流程

1. **收集**: 从公开渠道下载原始文本/PDF。
2. **结构化**: 按上述 JSONL 格式切分，确保每条 `text` 是一个完整的法律知识点。
3. **标注**: 标注 `case_type` 和 `topic`，便于按案由过滤检索。
4. **去重**: 基于 text 的 hash 去重。
5. **质检**: 抽样由法律专家审核准确性和完整性。

## 向量化与索引

使用 `sentence-transformers` 加载 `BAAI/bge-large-zh-v1.5` 量化版，对 `text` 字段生成 1024 维向量，存入 ChromaDB。

```python
from src.legal.knowledge_base import KnowledgeBase

kb = KnowledgeBase(path="data/knowledge_base")
kb.build_index()   # 首次构建
kb.add_documents([...])  # 增量添加
```

## 检索策略

1. 按当前 `case_type` 过滤集合。
2. 对转写文本和最近 3 句上下文分别嵌入，取平均作为查询向量。
3. 检索 Top-K（默认 K=3），按相似度排序。
4. 若最高相似度 < 0.55，视为检索失败，降级为规则模板。

## 增量更新

- 法条更新：新增 JSONL 文件或追加行，重新调用 `build_index()`。
- 模板更新：直接修改 templates JSONL，重启应用生效。
- 版本管理：在 `data/knowledge_base/version.txt` 中记录版本号。

## 质量指标

- Top-3 检索命中率 > 80%（人工评估 50 条查询）。
- 法条引用准确率 100%（关键法条需人工校验）。
- 模板覆盖 4 个案由 × 5 个常见场景 = 至少 20 个模板。

## 安全与合规

- 知识库仅本地存储，不上传。
- 案例数据需脱敏，不得包含真实当事人姓名、案号等敏感信息。
- 模板需经律师审核，避免给出违法或不当建议。
