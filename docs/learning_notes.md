# 学习笔记

本文档按项目涉及的知识点整理，帮助读者理解这个 demo 背后的工程概念。

## 1. RAG 基础

RAG 是 Retrieval-Augmented Generation 的缩写，核心思想是先从资料库中检索相关内容，再基于检索结果回答问题。

本项目中的关键概念：

- chunk：把长文档、表格行或段落切成适合检索的小块；
- embedding：把文本转成向量，便于计算语义相似度；
- vector database：保存向量和 metadata 的数据库，本项目使用 ChromaDB；
- top-k search：返回最相关的前 k 条结果；
- metadata：记录来源文件、source_type、业务域、阶段、任务名等结构化信息；
- evidence source：检索结果对应的原始资料来源，用于解释回答依据。

## 2. ChromaDB

ChromaDB 是本地向量库，用于保存 chunk 的 embedding 和 metadata。

本项目关注：

- collection：一组向量和文档记录；
- persist_dir：向量库持久化目录，当前为 `outputs/chroma_db`；
- collection.count()：检查知识库中是否已有数据；
- rebuild：重新解析 data 和 uploads，并重建向量库。

为什么需要重建知识库：

上传文件或修改原始资料后，旧的向量库不会自动知道新内容。必须重新构建，才能让新资料进入检索结果。

## 3. vector mode vs keyword fallback

vector mode：

- 使用 embedding 进行语义检索；
- 更适合自然语言查询；
- 依赖 `sentence-transformers` 和 `chromadb`；
- 首次加载模型可能较慢。

keyword fallback：

- 使用关键词重合做兜底检索；
- 不依赖向量模型；
- 可保证 demo 在依赖缺失时仍能运行；
- 语义理解能力有限。

适用场景：

- 正式评估和展示建议使用 vector mode；
- 环境不完整时可用 keyword fallback 快速验证链路；
- 两种模式下的指标不能直接比较。

## 4. Rerank

为什么需要 rerank：

初始检索常见情况是“正确证据在 top5 中，但不在 top1”。这时可以对候选结果重新排序，把更可能正确的证据排到前面。

本项目当前使用轻量规则 rerank：

- 原始分数归一化；
- 关键词重合；
- source_type 加权；
- evidence_strength 加权；
- 业务域、阶段、字段名命中加分。

模型 reranker：

后续可使用 cross-encoder 或 bge-reranker 一类模型，对 query 和候选文本做更精细的相关性判断。

重要边界：

rerank 不能解决未召回问题。如果正确文档没有进入候选集，rerank 无法凭空把它排到前面。

## 5. Agent Router

Agent Router 的作用是根据用户问题选择合适工具。

当前 intent 包括：

- `rule_qa`：规则类问答，例如“聊天记录能不能作为正式依据”；
- `rag_search`：资料检索，例如“请检索 A样阶段新增电控测试复核节点”；
- `diff_summary`：新旧配置变化摘要；
- `evidence_summary`：证据匹配摘要；
- `review_report`：复核建议报告；
- `status_check`：系统状态检查；
- `help`：帮助说明。

tool calling：

这里的 tool calling 是项目内部函数调用，不是大模型函数调用。Router 根据规则选择函数，例如调用 `search_docs()`、读取 `change_report.csv` 或生成规则化报告。

## 6. LLM API

为什么 Codex 写代码不等于项目接入 LLM：

Codex 是开发助手，帮助生成和修改项目代码；项目本身是否调用大模型 API，要看项目代码里是否实现了 API client、环境变量配置和调用逻辑。

本项目中 LLM API 的用途：

- 基于 RAG 检索结果生成更自然的中文回答；
- 基于结构化统计和重点清单润色复核报告；
- 失败时自动回退规则模板。

业务判断仍由规则和证据链控制：

- 差异分析不由 LLM 判断；
- evidence_status 不由 LLM 判断；
- review_priority 不由 LLM 判断；
- decision_suggestion 的结构化逻辑不由 LLM 替代。

## 7. RAG 评估

常用指标：

- hit@k：top-k 结果中是否命中目标；
- MRR：首次命中结果排名的倒数；
- source_file hit：是否命中预期文件；
- source_type hit：是否命中预期来源类型；
- evidence_strength hit：是否命中预期证据强度；
- keyword hit：检索结果是否包含期望关键词；
- badcase：未通过评估的样本，用于后续调优。

为什么要记录 retrieval_mode：

vector mode 和 keyword fallback 的检索机制不同。没有 retrieval_mode 标注，就无法判断指标是否可比。

## 8. 工程能力

本项目涉及的工程实践：

- `.venv`：隔离项目依赖；
- `requirements.txt`：记录依赖；
- `.gitignore`：避免提交密钥、缓存和上传文件；
- Git 分支：把功能开发和主线隔离；
- Streamlit：快速构建 Web Demo；
- 子进程调用：页面按钮运行脚本；
- 文件上传：保存文件、写 manifest、重建知识库；
- 日志和错误提示：让失败原因可见；
- 文档化：README、runbook、debug_notes、roadmap 帮助项目可维护。

## 9. 业务建模经验

这个 demo 的关键不是“让模型直接判断对错”，而是把业务资料拆成更清楚的层次：

- 配置上下文：旧配置和新配置；
- 具体变更依据：任命通知、会议纪要；
- 中等依据：部门在线更新；
- 弱线索：聊天记录和口头通知；
- 规则依据：复核规则和证据强弱说明。

这种分层能让 RAG 检索结果更容易解释，也能降低把弱线索误当正式依据的风险。
