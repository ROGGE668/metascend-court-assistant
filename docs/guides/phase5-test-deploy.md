# Phase 5: 测试、打包与试点（历史记录）

> 本节保留原始测试/部署思路；当前前端交付已改为 Tauri 2，不再沿用旧版 Python/Tk 打包脚本。

## 目标

完成系统集成测试、性能调优、macOS 应用打包，并在受控环境下进行试点。

## 测试策略

### 单元测试

- 每个模块独立测试：音频、VAD、ASR、Diarization、Legal、TTS。
- 慢测试标记为 `@pytest.mark.slow`，默认跳过。
- 运行命令：
  ```bash
  uv run pytest tests/ -v          # 快速测试
  uv run pytest tests/ --run-slow  # 包含模型加载测试
  ```

### 集成测试

- 端到端音频 -> 字幕延迟测试。
- 多人对话场景模拟。
- 噪声环境模拟（空调、翻纸、咳嗽）。

### 对抗测试

- 快速打断、方言口音、快速说话、多人重叠。
- 测试系统在极端输入下不崩溃。

### 法律测试

- 20+ 段模拟庭审对话，人工评估策略合理率。
- 重点检查：不出现虚假法条、不煽动对抗法庭。

### 隐私测试

- 断网运行，确认无外部请求。
- 录音文件 AES-256 加密，验证解密可恢复。

## 性能基准

| 指标 | 目标 |
|------|------|
| Phase 1: 音频 -> 字幕 | < 1.5s |
| Phase 2: 说话人切换检测 | < 500ms |
| Phase 3: 发言 -> 建议卡片 | < 3s |
| Phase 4: 建议 -> 耳机出声 | < 4s（含 LLM） |
| 连续运行时间 | >= 4 小时 |

## 历史打包脚本

### 启动脚本

历史上曾通过 `scripts/installers/run_mvp.sh` 加载 `.env` 并通过 `uv` 启动主流程：

```bash
./scripts/installers/run_mvp.sh
```

### 构建启动器

历史上曾通过 `scripts/installers/build_app.sh` 先运行快速测试和 lint，然后在 `dist/` 生成：

- `metascend-court-assistant`：命令行启动器
- `Metascend-Court-Assistant.command`：可在 Finder 中双击的 Terminal 启动脚本

```bash
./scripts/installers/build_app.sh
./dist/metascend-court-assistant
```

### 历史完整应用打包（未来）

- 历史方案曾考虑使用 `py2app` / Platypus 包装上述启动器为 `.app`。
- 当前已切换为 Tauri 2 原生打包，不再沿此路线继续。

## 部署流程

1. 在目标 Mac（M3/M4/M5, 16GB+）上安装 `uv`。
2. 运行 `uv sync` 安装依赖。
3. 运行 `uv run python scripts/download_models.py` 下载模型。
4. 运行 `./scripts/installers/run_mvp.sh` 验证功能。
5. 运行 `./scripts/installers/build_app.sh` 生成分发启动器。

## 更新机制

- 法条和知识库通过应用内热更新（JSONL diff）。
- 模型更新通过重新运行下载脚本或应用内提示。
- 所有更新均本地完成，不依赖应用商店审核。

## 试点计划

1. **内部测试**: 3-5 名志愿者在模拟庭审中使用，收集延迟和准确率反馈。
2. **律师监督试点**: 在律师陪同下，对 5-10 例真实民事案件进行庭前模拟或庭中辅助（需合规允许）。
3. **反馈闭环**: 用户标记建议是否有用，形成 RLHF 数据，持续优化策略库。

## 法律合规 checklist

- [x] 所有语音数据本地处理，不上传。
- [x] 录音文件 AES-256-GCM 加密存储（通过 `ENABLE_RECORDING=true` 开启）。
- [x] 日志 AES-256-GCM 加密存储（通过 `ENABLE_ENCRYPTED_LOGS=true` 开启，写入 `data/logs/app.log.enc`）。
- [x] UI 明确显示“仅供参考，不构成法律意见”。
- [x] 提供一键静音（关闭窗口 / `q` 键）。
- [ ] 遵守当地法庭电子设备管理规定（需用户自行确认）。

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| 法庭禁止电子设备 | 明确产品定位；提供庭前模拟模式；合规允许后再庭中使用 |
| 模型更新体积大 | 增量更新；按需下载 |
| 打包后路径问题 | 使用 `__file__` 和 `Path` 解析资源路径 |
| 用户误信错误建议 | 强免责声明；律师监督试点；高风险过滤 |

## 验收标准

- 在 M3/M4/M5 MacBook 上稳定运行 4 小时以上。
- Phase 1-3 功能完整，延迟达标。
- 法律建议合理率 > 75%（律师评估）。
- 无外部网络请求（除首次模型下载）。
- 应用可独立启动和退出。
