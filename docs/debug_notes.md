# Debug 记录

本文档记录项目开发过程中遇到的关键问题、原因分析、修复方法和工程启发，便于后续维护和复盘。

## 1. 虚拟环境问题

问题现象：

命令行运行脚本时提示缺少依赖，或者 `check_rag_mode.py` 显示无法 import `sentence_transformers`、`chromadb`，但 Streamlit 页面中又似乎可以正常运行。

原因分析：

Windows 上 `python` 命令可能指向全局 Python，而不是项目 `.venv`。如果依赖安装在 `.venv`，但脚本由全局 Python 执行，就会出现依赖缺失。Streamlit 页面按钮如果直接调用 `"python"`，也可能误用全局环境。

修复方法：

- 推荐创建并激活 `.venv`；
- 使用 `python -c "import sys; print(sys.executable)"` 检查当前解释器；
- Streamlit 页面按钮使用 `sys.executable` 调用脚本；
- 必要时直接使用：

```powershell
.\.venv\Scripts\python.exe scripts\check_rag_mode.py
```

工程启发：

公开 demo 项目要把环境路径问题写清楚。脚本内调用子进程时，应优先使用当前进程的 `sys.executable`，避免“页面一个 Python、脚本另一个 Python”。

## 2. vector mode 失败问题

问题现象：

系统进入 keyword fallback，或者 RAG 评估无法使用 `--strict-vector`。

原因分析：

能 import `sentence_transformers` 和 `chromadb` 不代表 vector mode 一定可用。还需要 ChromaDB 持久化目录存在、collection 能连接，并且 collection 中有数据。

可能原因包括：

- `outputs/chroma_db` 未构建；
- ChromaDB 文件被删除或损坏；
- collection 名称不一致；
- collection 中 chunk 数为 0；
- 当前 Python 环境缺少依赖。

修复方法：

```powershell
python scripts/build_knowledge_base.py
python scripts/check_rag_mode.py
```

如果仍失败，先确认 Python 环境，再确认 `outputs/chroma_db` 是否存在。

工程启发：

“依赖可导入”和“服务可用”是两件事。RAG 评估必须记录 `retrieval_mode`，否则容易把 keyword fallback 结果误当成 vector mode 结果。

## 3. keyword fallback 误读问题

问题现象：

baseline 和 rerank 的评估结果看起来可以比较，但实际可能一个来自 vector mode，另一个来自 keyword fallback。

原因分析：

keyword fallback 是兜底检索，排序逻辑和 vector mode 不同。二者指标不能直接比较。

修复方法：

- 在评估结果中加入 `retrieval_mode`；
- summary 顶部写入 `use_rerank`、`generated_at`、`python_executable`；
- 新增 `--strict-vector`，无法使用 vector mode 时直接停止评估；
- Streamlit 评估展示中提示 baseline 和 rerank 的 retrieval_mode 是否一致。

工程启发：

评估指标必须有上下文。没有模式标注的指标很容易误导判断。

## 4. rerank 效果判断

问题现象：

rerank 后 top3/top5 提升明显，但 top1 提升有限，部分规则类问题仍然没有命中理想来源。

原因分析：

rerank 只能重排序候选结果。如果正确文档没有被初始检索召回，rerank 无法凭空生成正确候选。

修复方法：

- 增加轻量规则 rerank；
- 对规则类、复核类、依据判定类问题提升 `rule_manual` 权重；
- baseline 与 rerank 分开评估；
- 在文档中说明 rerank 的边界。

工程启发：

排序优化和召回优化要分开看。top5 已召回但 top1 不高，适合 rerank；正确文档完全没召回，则需要 query rewrite、hybrid search 或 chunk 优化。

## 5. Streamlit 输出乱码问题

问题现象：

在文件上传页点击“重新构建知识库”后，脚本运行成功，但页面显示的 stdout/stderr 中文乱码。

原因分析：

Windows 子进程 stdout/stderr 编码可能和 Streamlit 主进程不一致。即使 Python 文件是 UTF-8，控制台输出也可能被错误解码。

修复方法：

- `subprocess.run()` 使用 `encoding="utf-8"`；
- 设置 `errors="replace"`，避免不可解码字符导致页面报错；
- 子进程环境变量加入 `PYTHONIOENCODING=utf-8`；
- stdout 和 stderr 分开展示；
- 返回码为 0 时提示“脚本运行完成”，否则提示“脚本运行失败”。

工程启发：

Web 页面里展示子进程输出时，要主动控制编码和错误兜底。演示项目尤其不能让一段日志乱码破坏用户判断。

## 6. Agent 关键词型查询路由问题

问题现象：

用户输入“A样阶段新增电控测试复核节点”时，Agent Router 返回 `help`，没有触发 RAG 检索。

原因分析：

早期 intent 识别更偏向问句和固定关键词，没有覆盖短文本业务关键词查询。这类 query 虽然没有问号，但明显是业务检索意图。

修复方法：

- 只有用户明确问“帮助”“help”“怎么用”“你能做什么”等时才返回 help；
- 增加业务关键词触发 `rag_search`，例如阶段、节点、复核、测试、配置、任务、负责人、交付物、A样、B1样、SOP、电控、电机、电源、整机；
- help 文案补充：可以在 RAG 检索测试页输入关键词，也可以在 Agent 问答中用“请检索……”提问。

工程启发：

Agent Router 不能只识别自然语言问句，也要识别业务关键词检索。很多真实用户会直接输入短语。

## 7. 文件上传进入知识库

问题现象：

用户上传补充资料后，希望能在 RAG 和 Agent 中检索到上传内容。

原因分析：

上传文件本身不会自动进入 ChromaDB。需要先保存文件、记录 manifest，再重建知识库，将上传资料解析成 chunk。

修复方法：

- 上传文件保存到 `uploads/`；
- `uploads/upload_manifest.csv` 记录 `upload_id`、原始文件名、保存文件名、source_type、description、upload_time；
- `document_loader.py` 读取 manifest，将上传文件按 source_type 加入知识库；
- chunk metadata 增加 `source_origin=upload`、`upload_id`、`original_filename`；
- Streamlit 上传页提示上传后需要重新构建知识库。

工程启发：

上传能力要有明确边界。当前版本只让上传资料进入 RAG 知识库，不自动替换主配置表，也不自动参与差异分析，这样更安全、可解释。
