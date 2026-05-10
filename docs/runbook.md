# 运行手册

## 创建和激活虚拟环境

Windows PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

如果 PowerShell 禁止激活脚本：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

确认当前 Python 环境：

```powershell
python --version
python -c "import sys; print(sys.executable)"
```

不激活虚拟环境也可以直接运行：

```powershell
.\.venv\Scripts\python.exe scripts\run_change_analysis.py
```

## 推荐运行顺序

```bash
python scripts/generate_mock_data.py
python scripts/run_change_analysis.py
python scripts/build_knowledge_base.py
python scripts/match_change_evidence.py
python scripts/inspect_evidence_matches.py
python scripts/run_agent.py "聊天记录能不能作为正式变更依据？"
streamlit run app.py
```

## vector mode 和 keyword fallback

项目优先使用 `sentence-transformers + ChromaDB` 的 vector mode。

- 优点：语义检索能力更强，适合中文自然语言 query。
- 首次运行可能较慢，因为需要下载或加载 embedding 模型。
- 构建后的本地向量库位于 `outputs/chroma_db/`。

如果依赖不可用、模型加载失败或 ChromaDB 无法连接，系统会自动切换到 keyword fallback mode。

- 优点：不依赖向量模型，保证 demo 基本可运行。
- 局限：只基于关键词重叠，召回质量不如 vector mode。

## ChromaDB 文件占用处理

Windows 下，如果 Streamlit 页面已经执行过 RAG 检索，当前进程可能会占用 `outputs/chroma_db/` 文件。此时点击页面里的“构建知识库”按钮可能出现 `PermissionError: WinError 32`。

处理方式：

1. 关闭 Streamlit 页面。
2. 回到终端。
3. 运行：

```bash
python scripts/build_knowledge_base.py
```

不要手动强删正在被占用的 ChromaDB 目录。

## 启动 Streamlit 页面

激活虚拟环境后：

```powershell
streamlit run app.py
```

不激活虚拟环境：

```powershell
.\.venv\Scripts\streamlit.exe run app.py
```

页面包含：

- 系统状态
- Agent 问答
- 变更清单
- 证据匹配
- 复核建议报告
- RAG 检索测试

## 常见问题

### 页面提示缺少 change_report.csv

运行：

```bash
python scripts/run_change_analysis.py
```

### 页面提示知识库未构建

运行：

```bash
python scripts/build_knowledge_base.py
```

### 页面提示缺少证据匹配结果

运行：

```bash
python scripts/match_change_evidence.py
```

### Streamlit 按钮使用了错误 Python 环境

页面按钮内部使用 `sys.executable` 调用脚本。请确认 Streamlit 本身是从 `.venv` 启动的：

```powershell
.\.venv\Scripts\streamlit.exe run app.py
```
