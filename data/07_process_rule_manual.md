# 流程配置变更规则说明

## 需要关注的字段

- 定位字段：task_id、project_type、business_domain、phase、gate、system_node。
- 任务字段：task_name、task_alias、trigger_condition、due_rule、is_required。
- 责任字段：owner_role、owner_name、responsible_department、collaborate_departments。
- 输入输出字段：input_doc、deliverable。
- 审批字段：approval_role、approval_mode。
- 版本字段：version、effective_date、source。

## 强依据来源

- 系统配置表：用于确认 V1.0 旧值、任务唯一性和历史节点位置。
- 新版目标配置表：用于确认 V2.0 目标状态和最终建议结果。
- 任命调整通知：负责人变更的优先依据，需匹配业务域、阶段、任务名称和生效日期。
- 正式会议纪要：新增任务、交付文档、审批角色、责任部门和时间规则变更的强依据。

## 中等依据来源

- 部门在线更新表属于中等依据。状态为“已确认”或“会议确认”的记录可作为建议来源，但仍需与任命通知或会议纪要交叉校验。
- 部门在线更新表中的 evidence_hint 可用于 RAG 检索，但不能替代正式来源原文。

## 弱依据来源

- 聊天记录、口头通知、非正式转述均为弱依据。
- 弱依据只能生成待复核线索，不能单独驱动正式配置修改。
- 当聊天记录之间互相冲突时，应保留所有线索并标记为“需人工复核”。

## 新增任务节点校验规则

- 新增节点必须包含 business_domain、phase、gate、task_name、owner_role、owner_name、responsible_department、deliverable、approval_role、trigger_condition 和 due_rule。
- task_id 和 system_node 不得与 V1.0 或 V2.0 既有节点重复。
- 新增节点原则上需要会议纪要依据；若仅来自聊天记录，状态必须为“待复核”。
- 新增节点应检查上下游输入输出，避免 deliverable 无后续消费或 input_doc 无来源。

## 负责人变更校验规则

- 负责人变更优先匹配任命调整通知中的 APPT 编号。
- owner_role、owner_name、responsible_department 必须逻辑一致。
- 若部门在线更新表写法口语化，需要抽取结构化旧值和新值后再比对。
- 若只有聊天记录或口头通知支持，不得进入正式 V2.0，只能生成建议清单。

## 交付文档变更校验规则

- 必须保留 old_config、new_config、reason 和 evidence_hint。
- 文档名称变化应同步检查 input_doc 是否受影响。
- 涉及阶段门准入、PPAP、DFMEA、DVP&R、配置基线等文档时，需要优先查找会议纪要依据。

## 责任部门变更校验规则

- responsible_department 表示正式责任部门，不等同于 submit_department。
- 责任部门变化必须检查 collaborate_departments 是否需要同步补充。
- 业务域归口部门与责任部门冲突时，应标记为“需人工复核”。

## 审批角色变更校验规则

- 审批角色变化需同时检查 approval_mode。
- 若审批角色从单人审批变为会签，应检查协同部门字段是否覆盖相关角色。
- 关键安全、高压、BOM冻结、设计冻结相关审批变化必须有会议纪要依据。

## 证据冲突处理

如果任命通知、会议纪要、部门在线更新表和聊天记录之间存在冲突，系统必须标记为“需人工复核”，并输出冲突来源编号，例如 APPT、MIN、U、CHAT 编号。

## AI 系统权限边界

AI 系统只能生成流程配置变更建议清单、证据摘录、差异说明和待复核项，不得直接修改正式系统配置。所有正式变更必须由授权人员人工复核、审批并录入。
