# RAG 评估与 Rerank 说明

## 评估目标

本项目当前只评估 retrieval，不评估 LLM 生成。评估对象是 `search_docs()` 是否能把相关原始资料检索到前若干名。

评估关注：

- top-k 是否命中期望 source_file；
- top-k 是否命中期望 source_type；
- 检索文本是否包含期望关键词；
- evidence_strength 是否符合预期；
- MRR 是否提升；
- rerank 是否把已召回的正确证据排得更靠前。

## 评估集

评估集位于：

```text
eval/rag_eval_set.csv
```

字段包括：

- `case_id`
- `query`
- `query_type`
- `expected_source_files`
- `expected_source_types`
- `expected_keywords`
- `expected_evidence_strength`
- `note`

样本覆盖规则问答、配置上下文查询、变更依据查询、聊天记录政策、SOP 复核、不同业务域和弱线索问题。所有问题均为虚构场景，不包含真实公司或客户信息。

## baseline 与 rerank

baseline：

```powershell
python scripts/run_rag_evaluation.py --strict-vector
```

rerank：

```powershell
python scripts/run_rag_evaluation.py --rerank --strict-vector
```

输出文件分开保存：

```text
outputs/eval/rag_eval_summary.md
outputs/eval/rag_eval_results.csv
outputs/eval/rag_eval_failed_cases.csv
outputs/eval/rag_eval_summary_rerank.md
outputs/eval/rag_eval_results_rerank.csv
outputs/eval/rag_eval_failed_cases_rerank.csv
```

`python scripts/run_rag_evaluation.py` 只生成 baseline 文件。  
`python scripts/run_rag_evaluation.py --rerank` 只生成 rerank 文件。  
二者不会互相覆盖。

## retrieval_mode

每次评估都会记录：

- `retrieval_mode`
- `use_rerank`
- `generated_at`
- `python_executable`

`retrieval_mode=vector` 表示使用 sentence-transformers + ChromaDB。  
`retrieval_mode=keyword_fallback` 表示向量依赖或向量库不可用，系统退回关键词检索。

baseline 和 rerank 必须在同一 `retrieval_mode` 下比较。如果一个是 vector，另一个是 keyword fallback，指标不可直接比较。

检查当前模式：

```powershell
python scripts/check_rag_mode.py
```

严格要求 vector：

```powershell
python scripts/run_rag_evaluation.py --strict-vector
python scripts/run_rag_evaluation.py --rerank --strict-vector
```

如果无法使用 vector mode，评估会停止并提示原因。

## 当前 rerank 方案

当前使用轻量规则 rerank，不依赖大模型，也不下载大型 reranker 模型。

主要信号：

- 原始检索分数归一化；
- query 与 text / metadata 的关键词重合；
- source_type 与 query 意图匹配；
- evidence_strength 加权；
- 业务域、阶段和字段名命中加分。

输出字段：

- `rerank_score`
- `rerank_reason`

## 当前 Step12 结论

在 vector mode 下，baseline 与 rerank 的评估结果显示：

- rerank 对 top3/top5 有比较明确的提升；
- top1 只有小幅提升；
- 部分 change_evidence 类问题和规则类问题受益于 source_type 加权；
- 仍有 badcase 来自候选召回不足，rerank 无法凭空补回未召回文档。

这说明当前轻量 rerank 的价值主要是“把已经召回的正确证据排得更靠前”，而不是解决所有检索问题。

## badcase 原因

常见失败原因：

- query 太短，关键词不足；
- query 的业务说法和文档中的表述不一致；
- chunk 切分导致关键信息分散；
- 正确文档没有进入候选集；
- source_type 加权不足或过强；
- 上传新资料后没有重新评估，导致指标和知识库状态不一致。

## 后续优化方向

- query rewrite：把用户口语问题改写成更适合检索的查询；
- hybrid search：结合向量检索、关键词检索和 metadata 过滤；
- model reranker：引入轻量 cross-encoder 或 bge-reranker；
- chunk 优化：对表格行、会议结论、规则段落设计更精细的切分；
- metadata 过滤：根据业务域、阶段、source_type 做候选收窄；
- 上传资料评估：上传新资料并重建知识库后，重新运行 baseline/rerank 评估，确认新增资料没有干扰原有检索质量。

## 重要边界

Rerank 只能重排序已召回候选。如果正确文档没有进入候选集，rerank 无法解决。此时应该优先考虑 query rewrite、hybrid search、metadata filter 或 chunk 设计。
