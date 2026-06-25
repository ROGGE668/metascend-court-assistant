# 部署与运维指南

## 环境要求

- 目标设备：MacBook Air / Pro，Apple Silicon（M1-M5），16GB+ 内存
- 操作系统：macOS 14 及以上
- Python：3.11，用于本地模型/推理后端开发；前端桌面壳采用 Tauri 2
- 网络：首次下载模型需要；运行时可完全离线

## 从源码部署

1. 进入项目目录：
   ```bash
   cd "/Users/hong/Documents/Metascend Court Assistant-庭审法律助手"
   ```

2. 创建虚拟环境并安装依赖：
   ```bash
   uv sync --extra dev
   ```

3. 下载模型：
   ```bash
   export HF_ENDPOINT=https://hf-mirror.com   # 国内环境
   uv run python scripts/download_models.py
   ```

4. 验证 Python 后端：
  ```bash
  uv run pytest tests/ -v
  uv run python src/pipeline.py
  ```

## 前端与桌面开发

推荐先运行前端预览，验证 UI 与交互：

```bash
cd frontend
npm install
npm run dev
```

Tauri 桌面壳与 macOS `.app` 打包是当前主要修复与验证目标。
## 模型分发

- 首次启动时引导用户下载模型。
- 可将模型缓存目录压缩为 `.tar.gz`，随应用分发。
- 模型路径：`~/.cache/metascend/models`。

## 知识库更新

1. 准备新增 JSONL 文件。
2. 放入 `data/knowledge_base/` 对应目录。
3. 运行重建索引脚本（待实现）：
   ```bash
   uv run python scripts/rebuild_kb.py
   ```

## 日志与监控

- 日志位置：`data/logs/session_YYYY-MM-DD_HH-MM-SS.log`
- 隐私日志默认加密，普通日志不包含案情细节。
- 性能指标：每个 ASR 片段的识别延迟会写入日志。

## 常见问题排查

**应用启动后立即退出**
- 检查麦克风权限是否已授权。
- 检查模型是否已下载。

**转写延迟高**
- 检查 ASR 模型大小和 compute_type。
- 关闭其他占用 GPU/CPU 的应用。

**无声音输出**
- 检查系统默认输出设备。
- 检查蓝牙耳机是否连接。

**模型下载失败**
- 设置 `HF_ENDPOINT=https://hf-mirror.com`。
- 检查磁盘空间是否足够。

## 回滚

- 模型回滚：从备份的模型缓存目录恢复。
- 知识库回滚：从 `data/knowledge_base/backups/` 恢复 JSONL。
- 应用回滚：替换 `.app` 或使用备份的虚拟环境。
