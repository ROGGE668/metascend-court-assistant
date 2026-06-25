# 本地 OCR 导入指南

本项目的 OCR 只用于“证据 / 知识库导入”前的可选预处理，不进入实时庭审 ASR 主链路。

## 启用方式

1. 在 `.env` 中确认或开启：
   ```env
   ENABLE_OCR_FALLBACK=true
   ```
2. 在支持安装依赖的环境中安装可选 OCR 依赖：
   ```bash
   uv pip install --system --python .venv/bin/python paddlepaddle paddleocr pymupdf pdf2image
   ```
3. 重启应用后，在“证据管理 / 知识库导入”时自动对扫描 PDF、图片启用回退解析。

## 导入顺序

- 优先读取可直接提取的文本：`.txt` / `.md` / `.pdf` 文本层。
- 若没有文本，再按配置启用 OCR。
- 纯文本导入路径保持不变，不会因为 OCR 依赖缺失而中断。

## 当前 Mac 可装性

- 这台 Mac 的 `pip` 目前无法解析 PyPI 域名，现场安装暂时受阻。
- 但 `~/.cache/uv/wheels-v6/pypi` 中已缓存过 OCR 相关 wheels，包括：
  - `paddlepaddle`
  - `paddleocr`
  - `pymupdf`
  - `pdf2image`
- 修复网络/DNS 后，可直接安装并运行验证。
