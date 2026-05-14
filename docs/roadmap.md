# Roadmap

## 当前版本

当前版本已经完成公开 demo 的核心闭环：

- 虚构多来源数据；
- 新旧配置差异分析；
- RAG 知识库；
- vector mode 与 keyword fallback；
- 证据匹配和复核优先级；
- Agent Router；
- Streamlit 页面；
- 可选 OpenAI-compatible LLM 生成层；
- RAG 评估集；
- baseline / rerank 分开评估；
- retrieval_mode 标注和 strict-vector 检查；
- 轻量文件上传进入知识库。

## v0.2：上传配置表参与差异分析

- 支持用户上传旧版/新版配置表作为差异分析输入；
- 支持选择“仅入知识库”或“参与差异分析”；
- 增加配置表版本管理和字段映射；
- 输出上传来源的 change_report。

## v0.3：飞书 API 或导出表接入

- 支持飞书导出 CSV/XLSX 的标准化解析；
- 预留飞书 API 接入适配层；
- 记录数据来源、导出时间和提交部门。

## v0.4：增量建库

- 对新增上传文件做增量 chunk；
- 避免每次重建整个 ChromaDB；
- 支持删除或停用某个上传文件对应的 chunk；
- 保留知识库版本记录。

## v0.5：检索质量优化

- query rewrite；
- hybrid search；
- metadata filter；
- 模型 reranker；
- chunk 策略调优；
- 按 query_type 统计 badcase。

## v0.6：LLM 生成质量评估

- 构建回答质量评估样本；
- 检查引用来源是否忠实；
- 检查是否编造超出资料的信息；
- 区分 retrieval 指标和 generation 指标。

## v0.7：人工复核状态流

- 为每条变更增加人工复核状态；
- 支持确认、退回、补证、暂缓纳入；
- 支持导出复核后的候选变更清单；
- 记录复核人、复核时间和处理意见。

## v0.8：权限和多部门协作

- 区分项目经理、质量、软件、硬件、制造等角色视图；
- 增加多部门协作状态；
- 支持更细粒度的数据访问控制。

## 可选方向：LangGraph 状态编排

当前 Agent Router 是轻量规则路由，不依赖 LangGraph。后续如果需要更复杂的状态机、任务分解、人工确认节点和多工具编排，可以考虑引入 LangGraph。
