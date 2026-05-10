# Codex Context

## 1. 当前项目目标

本项目是一个“车企/汽车零部件项目开发流程配置变更场景”的命令行 demo。目标是用虚构数据模拟真实流程配置变更工作流，包括：

- 生成旧版流程配置、新版目标配置、部门更新表、任命通知、会议纪要、聊天记录和规则文档。
- 对比旧版系统配置和新版目标配置，识别结构化差异。
- 将原始资料构建为离线知识库，支持 RAG 检索。
- 将差异清单中的 `evidence_query` 与原始证据资料匹配，输出带证据的变更清单。
- 对证据匹配结果做质量分层：配置上下文、强变更依据、中等变更依据、弱线索、规则依据。
- 通过轻量 Agent Router 提供命令行问答入口，按用户意图调用差异分析、RAG 检索、证据摘要、复核报告和项目状态检查。

所有数据均为虚构，不包含真实公司、真实人员、真实客户或真实项目信息。

## 2. 已完成 Step1-Step6.5 的内容

### Step1/Step2：模拟数据集

- `scripts/generate_mock_data.py` 可生成 `data/` 下全部模拟资料。
- 数据包括：
  - `01_system_export_current_config.csv/.xlsx`：V1.0 旧版系统配置。
  - `02_department_update_feishu.csv/.xlsx`：部门在线更新表。
  - `03_target_config_v2.csv/.xlsx`：V2.0 新版目标配置。
  - `04_appointment_adjustment_notice.md`：任命调整通知。
  - `05_process_change_meeting_minutes.md`：流程变更会议纪要。
  - `06_chat_change_messages.md`：聊天/口头通知记录。
  - `07_process_rule_manual.md`：流程配置变更规则说明。

### Step3：差异分析

- 核心模块：`src/change_analyzer.py`
- 运行脚本：`scripts/run_change_analysis.py`
- 输入：
  - `data/01_system_export_current_config.csv`
  - `data/03_target_config_v2.csv`
- 输出：
  - `outputs/change_report.csv`
  - `outputs/change_report.xlsx`
  - `outputs/change_summary.md`
- 主要逻辑：
  - 优先用 `task_id` 匹配。
  - `task_id` 为空时用 `business_domain + phase + task_name` 组合键。
  - 识别新增任务、删除任务、字段变更。
  - 不把 `version`、`effective_date`、`source` 作为主要差异字段。
  - 为每条差异生成 `risk_level`、`evidence_query` 和 `review_suggestion`。

### Step4：RAG 离线建库与检索

- 文档加载模块：`src/document_loader.py`
- 检索引擎：`src/rag_engine.py`
- 构建脚本：`scripts/build_knowledge_base.py`
- 检索脚本：`scripts/search_knowledge_base.py`
- chunk 检查脚本：`scripts/inspect_chunks.py`
- 支持格式：
  - `.csv`
  - `.xlsx`
  - `.md`
  - `.pdf` 可选兼容，缺少依赖时跳过。
- 去重规则：
  - 同名 CSV 和 XLSX 同时存在时，优先读取 CSV，跳过 XLSX。
- 输出：
  - `outputs/chunks_preview.csv`
  - `outputs/kb_build_summary.md`
  - `outputs/chroma_db/`
- 重要约束：
  - `outputs/change_report.csv` 是系统生成结果，不进入知识库。
  - 知识库只包含 `data/` 下原始证据资料。

### Step4.6：vector mode 性能优化

- `src/rag_engine.py` 已实现进程内缓存：
  - `_EMBEDDING_MODEL`
  - `_CHROMA_CLIENT`
  - `_CHROMA_COLLECTION`
- 关键函数：
  - `get_embedding_model()`
  - `get_chroma_collection()`
  - `reset_rag_cache()`
  - `batch_search_docs()`
- vector mode 可用时复用 SentenceTransformer 模型和 ChromaDB collection。
- vector mode 不可用时自动 fallback 到 keyword mode。
- 测试脚本：`scripts/test_vector_search.py`

### Step5：变更依据匹配

- 核心模块：`src/evidence_matcher.py`
- 运行脚本：`scripts/match_change_evidence.py`
- 输入：
  - `outputs/change_report.csv`
  - Step4 构建的知识库
- 输出：
  - `outputs/change_report_with_evidence.csv`
  - `outputs/change_report_with_evidence.xlsx`
  - `outputs/evidence_summary.md`
- 主要逻辑：
  - 对每条差异读取 `evidence_query`。
  - 调用 `batch_search_docs()` 批量检索原始资料。
  - 保存前 3 条主要证据。
  - 输出 `evidence_status`、`conflict_flag`、`final_review_suggestion` 等字段。

### Step5.5：证据匹配质量检查与修正

- 证据来源被重新分类：
  - `config_context`：`old_config`、`target_config`
  - `strong_change_evidence`：`appointment_notice`、`meeting_minutes`
  - `medium_change_evidence`：`department_update`
  - `weak_clue`：`chat_message`
  - `rule_evidence`：`rule_manual`
- 新增字段：
  - `primary_evidence_category`
  - `has_config_context`
  - `has_strong_change_evidence`
  - `has_medium_change_evidence`
  - `has_weak_clue`
  - `has_rule_evidence`
  - `weak_clue_flag`
  - `config_context_files`
  - `change_evidence_files`
  - `rule_evidence_files`
- 新增检查脚本：
  - `scripts/inspect_evidence_matches.py`

### Step6：轻量 Agent Router

- 核心模块：`src/agent_router.py`
- 命令行入口：`scripts/run_agent.py`
- 支持 intent：
  - `rag_search`
  - `diff_summary`
  - `evidence_summary`
  - `review_report`
  - `status_check`
  - `help`
- 功能：
  - 根据用户自然语言问题选择已有工具。
  - 可单次问答，也可交互式问答。
  - 不调用大模型，全部使用规则模板和检索结果生成回答。

### Step6.5：Agent 回答质量与复核优先级

- `src/evidence_matcher.py` 新增：
  - `impact_level`
  - `review_priority`
  - `decision_suggestion`
- `src/agent_router.py` 新增/优化：
  - `rule_qa` intent，优先于普通 RAG 检索。
  - 对规则类问题先给明确结论，再列相关来源。
  - 普通 RAG 检索增加“基于检索结果的简要判断”。
  - 复核报告从“高风险”改为“配置影响等级 + 依据状态 + 复核优先级”口径。
- `scripts/run_agent.py` 输出 sources 格式：
  - `source_file | source_type | evidence_strength | score`

## 3. 当前关键文件结构

```text
data/
  01_system_export_current_config.csv
  01_system_export_current_config.xlsx
  02_department_update_feishu.csv
  02_department_update_feishu.xlsx
  03_target_config_v2.csv
  03_target_config_v2.xlsx
  04_appointment_adjustment_notice.md
  05_process_change_meeting_minutes.md
  06_chat_change_messages.md
  07_process_rule_manual.md

src/
  change_analyzer.py
  document_loader.py
  rag_engine.py
  evidence_matcher.py
  agent_router.py

scripts/
  generate_mock_data.py
  run_change_analysis.py
  build_knowledge_base.py
  inspect_chunks.py
  search_knowledge_base.py
  test_vector_search.py
  match_change_evidence.py
  inspect_evidence_matches.py
  run_agent.py

outputs/
  change_report.csv
  change_report.xlsx
  change_summary.md
  chunks_preview.csv
  kb_build_summary.md
  chroma_db/
  change_report_with_evidence.csv
  change_report_with_evidence.xlsx
  evidence_summary.md

docs/
  codex_context.md

README.md
requirements.txt
```

## 4. 运行顺序和常用命令

推荐完整运行顺序：

```bash
python scripts/generate_mock_data.py
python scripts/run_change_analysis.py
python scripts/build_knowledge_base.py
python scripts/match_change_evidence.py
python scripts/inspect_evidence_matches.py
python scripts/run_agent.py
```

常用单步命令：

```bash
# 生成或刷新模拟数据
python scripts/generate_mock_data.py

# 01 vs 03 差异分析
python scripts/run_change_analysis.py

# 构建 RAG 知识库
python scripts/build_knowledge_base.py

# 查看 chunk 切分
python scripts/inspect_chunks.py

# 单次 RAG 检索
python scripts/search_knowledge_base.py "聊天记录能不能作为正式变更依据"

# 测试 vector/cache/fallback 检索链路
python scripts/test_vector_search.py

# 变更依据匹配
python scripts/match_change_evidence.py

# 检查证据匹配质量
python scripts/inspect_evidence_matches.py

# Agent 单次问答
python scripts/run_agent.py "新旧配置有哪些变化？"

# Agent 交互模式
python scripts/run_agent.py
```

常用 Agent 测试问题：

```text
当前系统完成到哪一步了？
新旧配置有哪些变化？
这些变更的依据匹配情况怎么样？
聊天记录能不能作为正式变更依据？
旧配置表和新版配置表能不能证明变更原因？
生成一份本次流程配置变更复核建议报告
哪些变化需要重点补证？
哪些变化可以常规复核？
哪些变化存在冲突或弱线索？
SOP阶段有哪些复核要求？
```

## 5. 重要限制

后续继续开发时请遵守以下限制：

- 不要修改 `data/` 目录下的数据文件，除非用户明确要求重新造数或刷新模拟数据。
- 不要修改 `scripts/generate_mock_data.py`，除非用户明确要求调整数据生成逻辑。
- 不要把 `outputs/change_report.csv` 放入知识库；它是系统生成的差异分析结果，不是原始证据来源。
- 不要引入 LangChain 或 LangGraph。
- 不要接大模型 API。
- 不要做 Streamlit 页面，当前项目保持命令行版 demo。
- 不要修改 Step3 差异分析逻辑，除非只是为了兼容导入或用户明确要求。
- 所有总结、建议、路由和回答都应使用规则模板或检索结果生成，不使用大模型生成。
