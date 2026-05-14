# RAG 评估与 Rerank 说明

## 为什么需要 Rerank

当前 RAG 检索链路已经可以把很多正确证据召回到 top5，但 top1 命中率不总是理想。这意味着“正确证据经常在候选列表里”，但排序还需要优化。Rerank 的目标不是扩大知识库，也不是让 LLM 判断答案，而是把已召回的正确证据尽量排到更靠前的位置。

## 当前方案

本项目使用轻量规则 rerank，不依赖大模型，也不下载大型 reranker 模型。评分由以下部分组成：

- 原始检索分归一化；
- query 与文本/metadata 的关键词重合；
- source_type 与问题意图的匹配加分；
- evidence_strength 加分；
- 业务域、阶段和字段名命中加分。

最终分数写入：

- `rerank_score`
- `rerank_reason`

## 运行评估

评估前建议先检查当前检索模式：

```bash
python scripts/check_rag_mode.py
```

baseline：

```bash
python scripts/run_rag_evaluation.py
```

启用 rerank：

```bash
python scripts/run_rag_evaluation.py --rerank
```

如果希望确保评估必须在 vector mode 下运行，可以使用严格模式：

```bash
python scripts/run_rag_evaluation.py --strict-vector
python scripts/run_rag_evaluation.py --rerank --strict-vector
```

自定义 top-k：

```bash
python scripts/run_rag_evaluation.py --rerank --top-k-values 1,3,5 --candidate-k 20
```

输出文件：

```text
outputs/eval/rag_eval_results.csv
outputs/eval/rag_eval_summary.md
outputs/eval/rag_eval_failed_cases.csv
outputs/eval/rag_eval_results_rerank.csv
outputs/eval/rag_eval_summary_rerank.md
outputs/eval/rag_eval_failed_cases_rerank.csv
```

baseline 与 rerank 分开生成、分开保存：

- baseline 摘要：`outputs/eval/rag_eval_summary.md`
- baseline 明细：`outputs/eval/rag_eval_results.csv`
- baseline 失败样本：`outputs/eval/rag_eval_failed_cases.csv`
- rerank 摘要：`outputs/eval/rag_eval_summary_rerank.md`
- rerank 明细：`outputs/eval/rag_eval_results_rerank.csv`
- rerank 失败样本：`outputs/eval/rag_eval_failed_cases_rerank.csv`

`python scripts/run_rag_evaluation.py` 只生成 baseline 文件；`python scripts/run_rag_evaluation.py --rerank` 只生成 rerank 文件，不会覆盖 baseline。

## 当前效果口径

当前轻量 rerank 主要用于改善“正确证据已进入候选集，但排序不够靠前”的情况。它通常更容易提升 top3/top5 和部分 `change_evidence` 类问题的 MRR。top1 提升相对有限，因为如果正确证据没有进入候选集，rerank 无法凭空召回。

后续如果需要更明显提升 top1，可以考虑：

- 引入轻量模型 reranker；
- 使用 cross-encoder；
- 针对规则类 query 做 query rewrite；
- 为 `rule_manual`、`meeting_minutes` 等来源增加专门召回通道。

## 指标说明

- `source_file hit rate`：top-k 是否命中期望来源文件。
- `source_type hit rate`：top-k 是否命中期望来源类型。
- `keyword hit rate`：top-k 文本是否包含期望关键词。
- `MRR`：首次命中结果的倒数排名。
- `overall_pass`：命中 source_file，或同时命中 source_type 和关键词。

## retrieval_mode 说明

评估结果会记录：

- `retrieval_mode`
- `use_rerank`
- `generated_at`
- `python_executable`

`retrieval_mode=vector` 表示使用 sentence-transformers + ChromaDB 向量检索。`retrieval_mode=keyword_fallback` 表示向量依赖不可用或向量库不可用，系统退回关键词检索。

baseline 与 rerank 必须在同一 `retrieval_mode` 下比较。如果一个是 vector，另一个是 keyword fallback，指标不可直接比较。若 summary 中提示 keyword fallback，请先检查依赖和向量库：

```bash
python scripts/check_rag_mode.py
```

rerank 只能重排序已经召回的候选结果，不能修复“正确文档没有进入候选集”的问题。

## 后续可替换方向

当前 rerank 是轻量规则版本，便于公开 demo 运行。后续可以替换或叠加：

- `bge-reranker`；
- cross-encoder reranker；
- 业务字段召回和 rerank 的联合调参；
- 面向不同 query_type 的权重自适应。
