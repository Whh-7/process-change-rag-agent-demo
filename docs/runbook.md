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

## 运行 RAG 评估

RAG 评估用于检查 `search_docs()` 的检索命中效果。当前只评估 retrieval，不评估大模型生成。

先确保知识库已经构建：

```bash
python scripts/build_knowledge_base.py
```

然后运行：

```bash
python scripts/run_rag_evaluation.py
```

如果使用 `.venv`：

```powershell
.\.venv\Scripts\python.exe scripts\run_rag_evaluation.py
```

评估集：

```text
eval/rag_eval_set.csv
```

输出：

```text
outputs/eval/rag_eval_results.csv
outputs/eval/rag_eval_summary.md
outputs/eval/rag_eval_failed_cases.csv
```

主要指标：

- source_file hit rate：是否命中期望来源文件。
- source_type hit rate：是否命中期望来源类型。
- keyword hit rate：检索文本是否包含期望关键词。
- evidence_strength hit rate：证据强度是否符合预期。
- MRR：首次命中的倒数排名。
- overall_pass：综合通过率。

## 可选启用 LLM

默认情况下不需要配置 LLM。没有 `.env` 或 `LLM_ENABLE=false` 时，Agent Router 会使用规则模板回答。

创建 `.env`：

```powershell
Copy-Item .env.example .env
```

启用 DeepSeek OpenAI-compatible API：

```text
LLM_ENABLE=true
LLM_PROVIDER=openai_compatible
LLM_API_KEY=your_real_api_key
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-v4-flash
LLM_TEMPERATURE=0.2
LLM_MAX_TOKENS=1200
```

关闭 LLM：

```text
LLM_ENABLE=false
```

检查当前是否使用 LLM：

- 命令行 `scripts/run_agent.py` 会打印 `llm_used` 和 `fallback_reason`。
- Streamlit 页面顶部和“系统状态”Tab 会显示 LLM 配置状态，但不会显示 API key。
- Agent 问答 Tab 会展示 `llm_used` 和 `fallback_reason`。

常见问题：

- `llm_used=false`：通常表示 `LLM_ENABLE=false`、未检测到 API key，或 API 调用失败。
- API key 未检测到：检查 `.env` 是否存在，`LLM_API_KEY` 是否仍为 `your_api_key_here`。
- API 调用失败：检查网络、额度、`LLM_BASE_URL` 和 `LLM_MODEL`。
- base_url 或 model 配错：修改 `.env` 后重启命令行进程或 Streamlit 页面。
- 如何回退规则模板：把 `LLM_ENABLE=false`，或暂时移除 `.env`。

安全提醒：

- 不要提交 `.env`。
- 不要在日志、截图或文档中暴露 API key。
- LLM 只用于回答生成和报告润色，不替代差异分析、证据强弱判断和复核优先级规则。

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
