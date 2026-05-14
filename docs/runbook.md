# 运行手册

本文档用于从零运行项目、排查环境问题，并说明上传、评估、LLM 和常见故障处理方式。

## 1. 创建虚拟环境

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

不激活虚拟环境时，可以直接运行：

```powershell
.\.venv\Scripts\python.exe scripts\run_change_analysis.py
```

## 2. 从零运行完整 pipeline

```powershell
python scripts/generate_mock_data.py
python scripts/run_change_analysis.py
python scripts/build_knowledge_base.py
python scripts/check_rag_mode.py
python scripts/match_change_evidence.py
python scripts/run_rag_evaluation.py --strict-vector
python scripts/run_rag_evaluation.py --rerank --strict-vector
python scripts/run_agent.py "聊天记录能不能作为正式变更依据？"
streamlit run app.py
```

如果你使用 `.venv` 但没有激活：

```powershell
.\.venv\Scripts\python.exe scripts\build_knowledge_base.py
.\.venv\Scripts\python.exe scripts\check_rag_mode.py
.\.venv\Scripts\streamlit.exe run app.py
```

## 3. 确认 vector mode

运行：

```powershell
python scripts/check_rag_mode.py
```

需要同时满足：

- 可以 import `sentence_transformers`；
- 可以 import `chromadb`；
- `outputs/chroma_db` 存在；
- ChromaDB collection 能连接；
- collection 中有 chunk。

如果任一条件不满足，系统会 fallback 到 keyword mode。fallback 是为了保证 demo 可运行，但不应该把 keyword fallback 指标和 vector mode 指标直接比较。

## 4. 排查 keyword fallback

常见原因：

- 当前 Python 不是 `.venv`，依赖没有安装；
- `sentence_transformers` 或 `chromadb` 缺失；
- `outputs/chroma_db` 没有构建；
- ChromaDB 目录损坏或被占用；
- collection 名称或持久化目录不匹配。

处理建议：

```powershell
python -m pip install -r requirements.txt
python scripts/build_knowledge_base.py
python scripts/check_rag_mode.py
```

如果你怀疑当前 Python 环境不对：

```powershell
python -c "import sys; print(sys.executable)"
.\.venv\Scripts\python.exe scripts\check_rag_mode.py
```

## 5. 运行差异分析

```powershell
python scripts/run_change_analysis.py
```

输出：

```text
outputs/change_report.csv
outputs/change_report.xlsx
outputs/change_summary.md
```

## 6. 构建知识库

```powershell
python scripts/build_knowledge_base.py
```

输出：

```text
outputs/chroma_db/
outputs/chunks_preview.csv
outputs/kb_build_summary.md
```

注意：`outputs/change_report.csv` 是系统分析结果，不会进入知识库。知识库只加载 `data/` 和 `uploads/` 中的原始资料。

## 7. ChromaDB 文件占用处理

Windows 下，如果 Streamlit 页面已经使用过 RAG 检索，当前进程可能占用 `outputs/chroma_db/`。这时点击页面里的“构建知识库”按钮，可能出现 `PermissionError: WinError 32`。

处理方式：

1. 关闭 Streamlit 页面；
2. 关闭可能占用 ChromaDB 的终端进程；
3. 回到终端运行：

```powershell
python scripts/build_knowledge_base.py
```

不要强行删除正在被占用的 ChromaDB 目录。

## 8. RAG 检索测试

```powershell
python scripts/search_knowledge_base.py "SOP阶段有哪些复核要求？"
python scripts/search_knowledge_base.py "请检索 A样阶段新增电控测试复核节点 的相关依据"
```

如果启用了 rerank 的入口，例如 Agent Router 或 Streamlit 检索页，结果中可能出现 `rerank_score` 和 `rerank_reason`。

## 9. 证据匹配

```powershell
python scripts/match_change_evidence.py
```

输出：

```text
outputs/change_report_with_evidence.csv
outputs/change_report_with_evidence.xlsx
outputs/evidence_summary.md
```

检查结果：

```powershell
python scripts/inspect_evidence_matches.py
```

## 10. Agent Router

单次问题：

```powershell
python scripts/run_agent.py "聊天记录能不能作为正式变更依据？"
python scripts/run_agent.py "新旧配置有哪些变化？"
python scripts/run_agent.py "生成一份本次流程配置变更复核建议报告"
```

交互模式：

```powershell
python scripts/run_agent.py
```

Agent Router 使用规则判断 intent，并调用对应工具。它不是 LangGraph 状态机。

## 11. Streamlit 页面

```powershell
streamlit run app.py
```

或：

```powershell
.\.venv\Scripts\streamlit.exe run app.py
```

页面包含：

- 系统状态；
- 文件上传；
- Agent 问答；
- 变更清单；
- 证据匹配；
- 复核建议报告；
- RAG 检索测试。

## 12. 上传文件

支持格式：

- `.csv`
- `.xlsx`
- `.md`
- `.txt`
- `.pdf`

PDF 只支持文本型 PDF，扫描件 OCR 当前不支持。

操作步骤：

1. 启动页面；
2. 进入“文件上传”Tab；
3. 选择文件；
4. 选择 `source_type`；
5. 填写可选说明；
6. 点击“保存上传文件”；
7. 重新构建知识库；
8. 到“RAG 检索测试”页输入上传文件中的关键词验证；
9. 也可以在 Agent 问答中使用“请检索 xxx 的相关依据”。

`source_type` 选择建议：

- 部门在线更新表：`department_update`
- 任命通知：`appointment_notice`
- 会议纪要：`meeting_minutes`
- 聊天记录/口头通知：`chat_message`
- 规则文档：`rule_manual`
- 旧配置表：`old_config`
- 新版目标配置表：`target_config`
- 其他补充资料：`other`

配置表字段要求：

- 必须字段：`business_domain`、`phase`、`task_name`
- 推荐字段：`owner_name`、`responsible_department`、`deliverable`、`approval_role`

当前版本上传的配置表只进入知识库，不自动替换主配置表，也不自动参与差异分析。

## 13. RAG 评估

先检查模式：

```powershell
python scripts/check_rag_mode.py
```

baseline：

```powershell
python scripts/run_rag_evaluation.py --strict-vector
```

rerank：

```powershell
python scripts/run_rag_evaluation.py --rerank --strict-vector
```

输出：

```text
outputs/eval/rag_eval_summary.md
outputs/eval/rag_eval_results.csv
outputs/eval/rag_eval_failed_cases.csv
outputs/eval/rag_eval_summary_rerank.md
outputs/eval/rag_eval_results_rerank.csv
outputs/eval/rag_eval_failed_cases_rerank.csv
```

baseline 和 rerank 必须在同一 `retrieval_mode` 下比较。

## 14. 启用或关闭 LLM

默认不需要 LLM。

创建 `.env`：

```powershell
Copy-Item .env.example .env
```

启用：

```text
LLM_ENABLE=true
LLM_PROVIDER=openai_compatible
LLM_API_KEY=your_real_api_key
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-v4-flash
LLM_TEMPERATURE=0.2
LLM_MAX_TOKENS=1200
```

关闭：

```text
LLM_ENABLE=false
```

检查：

- 命令行 Agent 会输出 `llm_used` 和 `fallback_reason`；
- Streamlit 页面会展示 LLM 状态，但不会展示 API key；
- API 调用失败时自动回退到规则模板。

LLM 只用于回答生成和报告润色，不替代差异分析、证据匹配和复核规则。

## 15. Git 提交注意事项

不要提交：

- `.env`
- `.env.*`
- `uploads/` 下真实上传文件
- `uploads/upload_manifest.csv`
- `outputs/chroma_db/`
- 大体积缓存、sqlite、parquet、日志文件

可以提交：

- `uploads/.gitkeep`
- `outputs/.gitkeep`
- `eval/rag_eval_set.csv`
- 源码、脚本和文档
