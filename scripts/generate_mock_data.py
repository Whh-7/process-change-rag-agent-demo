#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""生成车企/汽车零部件项目开发流程配置变更模拟数据集 V1。

说明：
- 所有公司、人员、项目、客户、部门信息均为虚构。
- 脚本只依赖 Python 标准库。
- 运行后会重新生成 data/ 目录下全部 xlsx、csv 和 markdown 文件。
"""

from __future__ import annotations

import csv
import html
import os
import shutil
import zipfile
from copy import deepcopy
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"

CONFIG_FIELDS = [
    "task_id",
    "project_type",
    "business_domain",
    "phase",
    "gate",
    "task_name",
    "task_alias",
    "owner_role",
    "owner_name",
    "responsible_department",
    "collaborate_departments",
    "input_doc",
    "deliverable",
    "approval_role",
    "approval_mode",
    "system_node",
    "trigger_condition",
    "due_rule",
    "is_required",
    "version",
    "effective_date",
    "source",
]

UPDATE_FIELDS = [
    "update_id",
    "submit_department",
    "submitter",
    "business_domain",
    "related_phase",
    "related_task",
    "update_type",
    "old_config",
    "new_config",
    "reason",
    "evidence_hint",
    "priority",
    "status",
    "submit_date",
    "remark",
]

PHASE_GATES = {
    "立项阶段": "GR0 项目立项评审",
    "准备阶段": "GR1 项目启动评审",
    "策划阶段": "GR2 方案冻结评审",
    "A样阶段": "GR3 A样启动评审",
    "B1样阶段": "GR4 B样启动评审",
    "B2样阶段": "GR5 设计冻结评审",
    "C样阶段": "GR6 生产件批准评审",
    "D样阶段": "GR7 SOP准备评审",
    "SOP阶段": "GR8 项目总结",
}

PROJECT_TYPES = ["曜川电驱平台项目", "澜星热管理总成项目", "青衡高压电源项目", "启岚整机集成项目"]
BUSINESS_DOMAINS = ["电机", "电控", "电源", "整机", "热管理", "传动系统", "车载软件"]

ROLE_NAMES = {
    "项目经理": "周宁",
    "产品经理": "许知行",
    "系统工程师": "陆知衡",
    "软件工程师": "乔安澜",
    "硬件工程师": "沈清和",
    "结构工程师": "叶云澈",
    "测试工程师": "秦若南",
    "质量工程师": "何沐川",
    "采购工程师": "温澄",
    "制造工程师": "傅景元",
    "工艺工程师": "罗星野",
    "成本经理": "韩知夏",
    "供应商质量工程师": "姜予安",
    "项目财务经理": "魏书言",
}

ROLE_DEPARTMENTS = {
    "项目经理": "项目管理部",
    "产品经理": "系统工程部",
    "系统工程师": "系统工程部",
    "软件工程师": "软件开发部",
    "硬件工程师": "硬件开发部",
    "结构工程师": "整机集成部",
    "测试工程师": "测试验证部",
    "质量工程师": "质量管理部",
    "采购工程师": "采购部",
    "制造工程师": "制造工程部",
    "工艺工程师": "制造工程部",
    "成本经理": "项目管理部",
    "供应商质量工程师": "质量管理部",
    "项目财务经理": "项目管理部",
}

DOMAIN_DEFAULT_DEPT = {
    "电机": "电机系统部",
    "电控": "电控软件部",
    "电源": "电源开发部",
    "整机": "整机集成部",
    "热管理": "热管理开发部",
    "传动系统": "整机集成部",
    "车载软件": "软件开发部",
    "通用": "项目管理部",
}


def gate_for(phase: str) -> str:
    """根据阶段返回阶段门。"""
    return PHASE_GATES[phase]


def owner_name(role: str) -> str:
    """根据角色返回默认虚构负责人。"""
    return ROLE_NAMES[role]


def responsible_dept(domain: str, role: str) -> str:
    """结合业务域和角色推断责任部门。"""
    if role in {"项目经理", "成本经理", "项目财务经理"}:
        return ROLE_DEPARTMENTS[role]
    if role in {"质量工程师", "采购工程师", "制造工程师", "工艺工程师", "供应商质量工程师"}:
        return ROLE_DEPARTMENTS[role]
    return DOMAIN_DEFAULT_DEPT.get(domain, ROLE_DEPARTMENTS[role])


def make_task(
    idx: int,
    project_type: str,
    business_domain: str,
    phase: str,
    task_name: str,
    task_alias: str,
    owner_role: str,
    input_doc: str,
    deliverable: str,
    approval_role: str,
    approval_mode: str,
    trigger_condition: str,
    due_rule: str,
    version: str,
    effective_date: str,
    source: str,
    responsible_department: str | None = None,
    collaborate_departments: str = "",
    owner: str | None = None,
    is_required: str = "是",
) -> dict[str, str]:
    """组装一条流程配置任务。"""
    gate = gate_for(phase)
    return {
        "task_id": f"T{idx:03d}",
        "project_type": project_type,
        "business_domain": business_domain,
        "phase": phase,
        "gate": gate,
        "task_name": task_name,
        "task_alias": task_alias,
        "owner_role": owner_role,
        "owner_name": owner or owner_name(owner_role),
        "responsible_department": responsible_department or responsible_dept(business_domain, owner_role),
        "collaborate_departments": collaborate_departments,
        "input_doc": input_doc,
        "deliverable": deliverable,
        "approval_role": approval_role,
        "approval_mode": approval_mode,
        "system_node": f"{gate.split()[0]}-{idx:03d}",
        "trigger_condition": trigger_condition,
        "due_rule": due_rule,
        "is_required": is_required,
        "version": version,
        "effective_date": effective_date,
        "source": source,
    }


COMMON_TASKS = [
    ("通用", "立项阶段", "项目立项申请", "立项申请", "项目经理", "项目机会清单", "项目立项申请表", "项目经理", "会签", "收到虚构客户需求包", "GR0前5个工作日"),
    ("通用", "立项阶段", "客户需求分析", "需求分析", "产品经理", "虚构客户需求包", "客户需求分析报告", "系统工程师", "会签", "立项申请创建后", "GR0前3个工作日"),
    ("通用", "立项阶段", "商业可行性测算", "可行性测算", "成本经理", "需求分析报告", "商业可行性测算表", "项目财务经理", "会签", "立项评审排期后", "GR0前2个工作日"),
    ("通用", "准备阶段", "项目计划制定", "主计划", "项目经理", "立项批准记录", "项目主计划", "项目经理", "单人审批", "GR0通过后", "GR1前5个工作日"),
    ("通用", "准备阶段", "核心团队任命确认", "团队任命", "项目经理", "组织架构草案", "核心团队任命表", "项目经理", "单人审批", "项目主计划发布后", "GR1前3个工作日"),
    ("通用", "准备阶段", "初始风险清单建立", "风险清单", "质量工程师", "历史问题库", "初始风险清单", "质量工程师", "会签", "团队任命完成后", "GR1前2个工作日"),
    ("通用", "策划阶段", "系统需求分解", "需求分解", "系统工程师", "客户需求分析报告", "系统需求规格说明书", "产品经理", "会签", "GR1通过后", "GR2前7个工作日"),
    ("通用", "策划阶段", "DFMEA", "设计FMEA", "质量工程师", "系统需求规格说明书", "DFMEA记录", "质量工程师", "会签", "方案设计启动后", "GR2前5个工作日"),
    ("通用", "策划阶段", "供应商长名单建立", "供应商长名单", "采购工程师", "初始BOM清单", "供应商长名单", "采购工程师", "单人审批", "关键外购件识别后", "GR2前3个工作日"),
    ("通用", "A样阶段", "A样设计输入冻结", "A样输入", "系统工程师", "系统需求规格说明书", "A样设计输入冻结单", "系统工程师", "会签", "A样启动申请创建后", "GR3前3个工作日"),
    ("通用", "A样阶段", "A样试制问题跟踪", "A样问题", "项目经理", "A样试制记录", "A样问题跟踪表", "项目经理", "会签", "A样试制完成后", "问题提出后2个工作日内更新"),
    ("通用", "A样阶段", "A样测试方案", "A样测试", "测试工程师", "A样设计输入冻结单", "A样测试方案", "质量工程师", "会签", "A样样件入库后", "测试前3个工作日"),
    ("通用", "B1样阶段", "B1样问题关闭计划", "B1关闭", "项目经理", "A样测试报告", "B1样问题关闭计划", "项目经理", "会签", "A样问题评审完成后", "GR4前5个工作日"),
    ("通用", "B1样阶段", "B1样验证执行", "B1验证", "测试工程师", "A样测试方案", "B1样验证报告", "质量工程师", "会签", "B1样件齐套后", "测试完成后3个工作日"),
    ("通用", "B1样阶段", "B1样设计问题复盘", "B1复盘", "系统工程师", "B1样验证报告", "B1样设计问题复盘表", "项目经理", "会签", "B1验证报告发布后", "GR4后5个工作日内"),
    ("通用", "B2样阶段", "B2样设计冻结评审", "设计冻结", "系统工程师", "B1样设计问题复盘表", "设计冻结评审包", "项目经理", "会签", "B1问题关闭率达到90%", "GR5前5个工作日"),
    ("通用", "B2样阶段", "B2样BOM冻结", "BOM冻结", "硬件工程师", "设计冻结评审包", "B2样BOM冻结清单", "采购工程师", "会签", "设计冻结评审通过后", "GR5前3个工作日"),
    ("通用", "B2样阶段", "B2样测试计划更新", "测试计划更新", "测试工程师", "B1样验证报告", "B2样测试计划", "质量工程师", "会签", "B2样件计划确认后", "测试前5个工作日"),
    ("通用", "C样阶段", "PFMEA", "过程FMEA", "工艺工程师", "设计冻结评审包", "PFMEA记录", "质量工程师", "会签", "工艺路线发布后", "GR6前5个工作日"),
    ("通用", "C样阶段", "PPAP资料准备", "PPAP准备", "供应商质量工程师", "B2样BOM冻结清单", "PPAP资料包", "质量工程师", "会签", "C样试生产计划发布后", "GR6前7个工作日"),
    ("通用", "C样阶段", "C样成本复核", "成本复核", "成本经理", "B2样BOM冻结清单", "C样成本复核表", "项目财务经理", "会签", "C样BOM稳定后", "GR6前3个工作日"),
    ("通用", "D样阶段", "D样生产验证", "生产验证", "制造工程师", "C样试生产记录", "D样生产验证报告", "制造工程师", "单人审批", "D样生产启动后", "GR7前5个工作日"),
    ("通用", "D样阶段", "D样质量门审核", "质量门", "质量工程师", "D样生产验证报告", "D样质量门审核表", "项目经理", "会签", "D样验证完成后", "GR7前3个工作日"),
    ("通用", "D样阶段", "SOP准备检查", "SOP检查", "项目经理", "D样质量门审核表", "SOP准备检查表", "项目经理", "会签", "SOP准备评审排期后", "GR7前2个工作日"),
    ("通用", "SOP阶段", "SOP首批问题收敛", "首批收敛", "质量工程师", "SOP准备检查表", "SOP首批问题清单", "项目经理", "会签", "首批量产完成后", "SOP后5个工作日"),
    ("通用", "SOP阶段", "量产成本闭环", "成本闭环", "成本经理", "C样成本复核表", "量产成本闭环报告", "项目财务经理", "会签", "首批订单完成后", "SOP后10个工作日"),
    ("通用", "SOP阶段", "项目经验总结", "项目总结", "项目经理", "项目过程资料", "项目经验总结报告", "项目经理", "单人审批", "项目总结会排期后", "SOP后15个工作日"),
]

DOMAIN_TASKS = {
    "电机": [
        ("准备阶段", "电机接口边界确认", "电机边界", "系统工程师", "立项批准记录", "电机接口边界确认表", "项目经理", "会签", "GR0通过后", "GR1前4个工作日", "系统工程部、电控软件部"),
        ("策划阶段", "电机控制策略评审", "控制策略", "系统工程师", "系统需求规格说明书", "电机控制策略评审记录", "系统工程师", "会签", "控制目标冻结后", "GR2前4个工作日", "电控软件部、测试验证部"),
        ("A样阶段", "电机样件测试", "样件测试", "测试工程师", "A样设计输入冻结单", "电机样件测试报告", "质量工程师", "会签", "电机A样入库后", "测试完成后3个工作日", "电机系统部、测试验证部"),
        ("B1样阶段", "电机NVH问题分析", "NVH分析", "系统工程师", "电机样件测试报告", "电机NVH问题分析表", "项目经理", "会签", "B1样NVH异常触发", "问题提出后5个工作日", "测试验证部"),
        ("B2样阶段", "电机DV测试", "DV测试", "测试工程师", "B2样测试计划", "电机DV测试报告", "质量工程师", "会签", "B2样件齐套后", "GR5后10个工作日内", "电机系统部"),
        ("C样阶段", "电机OTS认可", "OTS认可", "质量工程师", "电机DV测试报告", "电机OTS认可单", "质量工程师", "会签", "C样电机供应状态冻结后", "GR6前3个工作日", "采购部、制造工程部"),
        ("D样阶段", "电机产线节拍确认", "节拍确认", "制造工程师", "D样生产验证报告", "电机产线节拍确认表", "制造工程师", "单人审批", "D样产线试运行后", "GR7前4个工作日", "电机系统部"),
        ("SOP阶段", "电机量产异常闭环", "量产异常", "质量工程师", "SOP首批问题清单", "电机量产异常闭环表", "项目经理", "会签", "电机首批问题出现后", "SOP后8个工作日", "制造工程部"),
    ],
    "电控": [
        ("准备阶段", "控制器接口边界确认", "控制器边界", "系统工程师", "立项批准记录", "控制器接口边界确认表", "项目经理", "会签", "GR0通过后", "GR1前4个工作日", "硬件开发部、软件开发部"),
        ("策划阶段", "软件需求冻结", "软件需求", "软件工程师", "系统需求规格说明书", "软件需求冻结单", "系统工程师", "会签", "系统需求分解完成后", "GR2前4个工作日", "系统工程部"),
        ("策划阶段", "控制器硬件评审", "硬件评审", "硬件工程师", "系统需求规格说明书", "控制器硬件评审记录", "硬件工程师", "会签", "控制器规格定义后", "GR2前3个工作日", "硬件开发部、质量管理部"),
        ("A样阶段", "电控软件单元测试", "单元测试", "软件工程师", "软件需求冻结单", "电控软件单元测试报告", "软件工程师", "单人审批", "A样代码冻结后", "代码冻结后5个工作日", "测试验证部"),
        ("B1样阶段", "软件集成测试", "集成测试", "测试工程师", "电控软件单元测试报告", "软件集成测试报告", "质量工程师", "会签", "B1软件包发布后", "测试完成后3个工作日", "软件开发部"),
        ("B1样阶段", "诊断功能评审", "诊断评审", "软件工程师", "软件集成测试报告", "诊断功能评审记录", "系统工程师", "会签", "诊断需求冻结后", "GR4前3个工作日", "系统工程部"),
        ("B2样阶段", "控制器EMC问题关闭", "EMC关闭", "硬件工程师", "B1样验证报告", "控制器EMC问题关闭单", "质量工程师", "会签", "EMC问题清单发布后", "GR5前2个工作日", "测试验证部"),
        ("C样阶段", "电控EOL测试脚本确认", "EOL脚本", "制造工程师", "软件集成测试报告", "电控EOL测试脚本确认表", "制造工程师", "会签", "C样产线调试开始前", "GR6前4个工作日", "软件开发部"),
        ("SOP阶段", "电控软件版本归档", "软件归档", "软件工程师", "SOP配置清单", "电控软件版本归档记录", "项目经理", "会签", "SOP软件版本发布后", "SOP后3个工作日", "质量管理部"),
    ],
    "电源": [
        ("准备阶段", "高压接口边界确认", "高压边界", "硬件工程师", "立项批准记录", "高压接口边界确认表", "项目经理", "会签", "GR0通过后", "GR1前4个工作日", "系统工程部、整机集成部"),
        ("策划阶段", "电池包接口评审", "电池接口", "硬件工程师", "系统需求规格说明书", "电池包接口评审记录", "系统工程师", "会签", "高压接口定义完成后", "GR2前4个工作日", "系统工程部、电源开发部"),
        ("策划阶段", "高压安全评审", "高压安全", "质量工程师", "系统需求规格说明书", "高压安全评审记录", "质量工程师", "会签", "高压方案形成后", "GR2前3个工作日", "硬件开发部"),
        ("A样阶段", "BMS功能测试", "BMS测试", "测试工程师", "A样设计输入冻结单", "BMS功能测试报告", "质量工程师", "会签", "BMS A样软件发布后", "测试完成后3个工作日", "软件开发部"),
        ("B1样阶段", "电源热失控风险复核", "热失控复核", "质量工程师", "BMS功能测试报告", "电源热失控风险复核表", "质量工程师", "会签", "B1风险评审触发后", "GR4前3个工作日", "热管理开发部"),
        ("B2样阶段", "电源BOM冻结", "电源BOM", "硬件工程师", "设计冻结评审包", "电源BOM冻结清单", "采购工程师", "会签", "电源设计冻结后", "GR5前3个工作日", "采购部"),
        ("C样阶段", "电源PPAP样件确认", "电源PPAP", "供应商质量工程师", "PPAP资料包", "电源PPAP样件确认单", "质量工程师", "会签", "C样供应商样件到货后", "GR6前3个工作日", "电源开发部"),
        ("D样阶段", "高压下线检测确认", "下线检测", "制造工程师", "D样生产验证报告", "高压下线检测确认表", "制造工程师", "单人审批", "D样高压检测完成后", "GR7前3个工作日", "质量管理部"),
    ],
    "整机": [
        ("准备阶段", "整车集成边界确认", "集成边界", "系统工程师", "虚构整车边界条件", "整车集成边界确认表", "项目经理", "会签", "GR0通过后", "GR1前4个工作日", "系统工程部"),
        ("策划阶段", "整车集成评审", "集成评审", "结构工程师", "系统需求规格说明书", "整车集成评审记录", "项目经理", "会签", "系统方案形成后", "GR2前4个工作日", "系统工程部、测试验证部"),
        ("A样阶段", "整车装配可行性评审", "装配评审", "制造工程师", "A样结构样件图", "整车装配可行性评审表", "制造工程师", "会签", "A样结构方案完成后", "GR3前2个工作日", "整机集成部"),
        ("B1样阶段", "整车道路试验", "道路试验", "测试工程师", "B1样验证计划", "整车道路试验报告", "质量工程师", "会签", "B1样装车完成后", "试验完成后5个工作日", "整机集成部"),
        ("B2样阶段", "整车问题关闭", "整车关闭", "项目经理", "整车道路试验报告", "整车问题关闭清单", "项目经理", "会签", "道路试验问题发布后", "GR5前3个工作日", "质量管理部"),
        ("C样阶段", "整车一致性检查", "一致性检查", "质量工程师", "PPAP资料包", "整车一致性检查表", "质量工程师", "会签", "C样装车完成后", "GR6前2个工作日", "制造工程部"),
        ("SOP阶段", "整车售后问题转交", "售后转交", "质量工程师", "SOP首批问题清单", "整车售后问题转交单", "项目经理", "会签", "SOP问题收敛后", "SOP后10个工作日", "项目管理部"),
    ],
    "热管理": [
        ("准备阶段", "热管理边界条件确认", "热边界", "系统工程师", "立项批准记录", "热管理边界条件确认表", "项目经理", "会签", "GR0通过后", "GR1前4个工作日", "整机集成部"),
        ("策划阶段", "热管理方案评审", "热管理方案", "系统工程师", "系统需求规格说明书", "热管理方案评审记录", "系统工程师", "会签", "热负荷目标确认后", "GR2前4个工作日", "整机集成部"),
        ("A样阶段", "冷却系统台架测试", "冷却台架", "测试工程师", "热管理方案评审记录", "冷却系统台架测试报告", "质量工程师", "会签", "A样冷却回路搭建后", "测试完成后3个工作日", "热管理开发部"),
        ("B1样阶段", "冷却系统验证", "冷却验证", "测试工程师", "冷却系统台架测试报告", "冷却系统验证报告", "质量工程师", "会签", "B1样热管理件齐套后", "GR4前3个工作日", "整机集成部"),
        ("B2样阶段", "热管理管路冻结", "管路冻结", "结构工程师", "冷却系统验证报告", "热管理管路冻结图", "系统工程师", "会签", "B2样设计冻结前", "GR5前3个工作日", "热管理开发部"),
        ("C样阶段", "热管理供应商过程审核", "过程审核", "供应商质量工程师", "PPAP资料包", "热管理供应商过程审核表", "质量工程师", "会签", "C样供应商审核排期后", "GR6前5个工作日", "采购部"),
        ("D样阶段", "冷却液加注工艺确认", "加注确认", "工艺工程师", "D样生产验证报告", "冷却液加注工艺确认表", "制造工程师", "会签", "D样产线调试后", "GR7前4个工作日", "制造工程部"),
        ("SOP阶段", "热管理售后诊断资料归档", "诊断归档", "系统工程师", "项目经验总结报告", "热管理售后诊断资料包", "项目经理", "会签", "SOP后资料归档启动", "SOP后15个工作日", "质量管理部"),
    ],
    "传动系统": [
        ("策划阶段", "传动匹配方案评审", "匹配评审", "系统工程师", "系统需求规格说明书", "传动匹配方案评审记录", "项目经理", "会签", "传动目标定义后", "GR2前4个工作日", "整机集成部"),
        ("A样阶段", "减速器样件检查", "减速器检查", "测试工程师", "A样设计输入冻结单", "减速器样件检查报告", "质量工程师", "会签", "A样减速器入库后", "检查完成后2个工作日", "质量管理部"),
        ("B1样阶段", "传动效率测试", "效率测试", "测试工程师", "减速器样件检查报告", "传动效率测试报告", "质量工程师", "会签", "B1样台架准备完成后", "测试完成后3个工作日", "测试验证部"),
        ("B2样阶段", "传动系统设计冻结", "传动冻结", "系统工程师", "传动效率测试报告", "传动系统设计冻结报告", "项目经理", "会签", "效率问题关闭后", "GR5前3个工作日", "质量管理部"),
        ("C样阶段", "传动系统PPAP复核", "传动PPAP", "供应商质量工程师", "PPAP资料包", "传动系统PPAP复核表", "质量工程师", "会签", "C样PPAP资料齐套后", "GR6前3个工作日", "采购部"),
        ("D样阶段", "传动系统产线防错确认", "防错确认", "制造工程师", "D样生产验证报告", "传动系统产线防错确认表", "制造工程师", "单人审批", "D样产线防错验证后", "GR7前3个工作日", "质量管理部"),
        ("SOP阶段", "传动系统量产偏差复盘", "偏差复盘", "质量工程师", "SOP首批问题清单", "传动系统量产偏差复盘表", "项目经理", "会签", "SOP首批完成后", "SOP后10个工作日", "制造工程部"),
    ],
    "车载软件": [
        ("准备阶段", "软件工具链准备确认", "工具链确认", "软件工程师", "项目主计划", "软件工具链准备确认表", "项目经理", "会签", "GR0通过后", "GR1前4个工作日", "质量管理部"),
        ("策划阶段", "车载软件架构评审", "软件架构", "软件工程师", "系统需求规格说明书", "车载软件架构评审记录", "系统工程师", "会签", "软件需求冻结后", "GR2前3个工作日", "系统工程部"),
        ("A样阶段", "车载软件开源组件清单", "开源清单", "软件工程师", "车载软件架构评审记录", "车载软件开源组件清单", "质量工程师", "会签", "A样代码基线建立后", "GR3前2个工作日", "质量管理部"),
        ("B1样阶段", "车载软件集成回归测试", "回归测试", "测试工程师", "车载软件开源组件清单", "车载软件集成回归测试报告", "质量工程师", "会签", "B1软件包发布后", "测试完成后3个工作日", "软件开发部"),
        ("B2样阶段", "车载软件版本冻结", "版本冻结", "软件工程师", "车载软件集成回归测试报告", "车载软件版本冻结单", "项目经理", "会签", "B2软件版本发布后", "GR5前2个工作日", "质量管理部"),
        ("C样阶段", "车载软件刷写流程确认", "刷写确认", "制造工程师", "车载软件版本冻结单", "车载软件刷写流程确认表", "制造工程师", "会签", "C样产线调试开始前", "GR6前4个工作日", "软件开发部"),
        ("D样阶段", "车载软件量产发布检查", "发布检查", "软件工程师", "车载软件刷写流程确认表", "车载软件量产发布检查单", "项目经理", "会签", "D样发布候选版本生成后", "GR7前3个工作日", "质量管理部"),
        ("SOP阶段", "车载软件配置基线归档", "基线归档", "软件工程师", "车载软件量产发布检查单", "车载软件配置基线归档记录", "项目经理", "会签", "SOP版本确认后", "SOP后3个工作日", "项目管理部"),
    ],
}


def build_v1_config() -> list[dict[str, str]]:
    """生成约 80 条 V1.0 系统现有配置。"""
    rows: list[dict[str, str]] = []
    task_id = 1
    for item in COMMON_TASKS:
        _, phase, task_name, alias, role, input_doc, deliverable, approval_role, approval_mode, trigger, due_rule = item
        domain = BUSINESS_DOMAINS[(task_id - 1) % len(BUSINESS_DOMAINS)]
        rows.append(make_task(task_id, PROJECT_TYPES[(task_id - 1) % len(PROJECT_TYPES)], domain, phase, task_name, alias, role, input_doc, deliverable, approval_role, approval_mode, trigger, due_rule, "V1.0", "2025-01-01", "SYS-V1"))
        task_id += 1

    for domain in BUSINESS_DOMAINS:
        for item in DOMAIN_TASKS[domain]:
            phase, task_name, alias, role, input_doc, deliverable, approval_role, approval_mode, trigger, due_rule, collaborate = item
            rows.append(make_task(task_id, PROJECT_TYPES[(task_id - 1) % len(PROJECT_TYPES)], domain, phase, task_name, alias, role, input_doc, deliverable, approval_role, approval_mode, trigger, due_rule, "V1.0", "2025-01-01", "SYS-V1", collaborate_departments=collaborate))
            task_id += 1
    return rows


def update_row(
    update_id: str,
    submit_department: str,
    submitter: str,
    business_domain: str,
    phase: str,
    task: str,
    update_type: str,
    old_config: str,
    new_config: str,
    reason: str,
    evidence_hint: str,
    priority: str,
    status: str,
    remark: str,
) -> dict[str, str]:
    """组装一条部门在线更新记录。"""
    return {
        "update_id": update_id,
        "submit_department": submit_department,
        "submitter": submitter,
        "business_domain": business_domain,
        "related_phase": phase,
        "related_task": task,
        "update_type": update_type,
        "old_config": old_config,
        "new_config": new_config,
        "reason": reason,
        "evidence_hint": evidence_hint,
        "priority": priority,
        "status": status,
        "submit_date": "2025-02-26",
        "remark": remark,
    }


def build_updates() -> list[dict[str, str]]:
    """生成约 35 条飞书更新记录，其中一部分为弱线索。"""
    data = [
        ("U001", "系统工程部", "陆知衡", "电控", "立项阶段", "客户需求分析", "负责人调整", "owner_name=许知行", "建议改成陆知衡负责，产品经理只会签", "需求分解职责已转入系统工程接口人", "APPT-001", "高", "已确认", "进入V2"),
        ("U002", "电机系统部", "方澄远", "电机", "策划阶段", "电机控制策略评审", "负责人调整", "owner_name=陆知衡", "方澄远负责控制策略，测试验证部参与", "电机控制策略责任人调整", "APPT-002", "高", "已确认", "进入V2"),
        ("U003", "电控软件部", "邵予白", "电控", "策划阶段", "软件需求冻结", "负责人调整", "owner_name=乔安澜", "改邵予白负责，系统工程师审批", "软件需求归口到电控平台组", "APPT-003", "高", "已确认", "进入V2"),
        ("U004", "电源开发部", "顾景初", "电源", "策划阶段", "电池包接口评审", "负责人调整", "owner_name=沈清和", "顾景初负责接口评审", "电源接口负责人变更", "APPT-004", "高", "已确认", "进入V2"),
        ("U005", "整机集成部", "林越川", "整机", "策划阶段", "整车集成评审", "负责人调整", "owner_name=叶云澈", "后续林越川牵头整车集成评审", "整机集成职责调整", "APPT-005", "高", "已确认", "进入V2"),
        ("U006", "热管理开发部", "夏南栀", "热管理", "B1样阶段", "冷却系统验证", "负责人调整", "owner_name=秦若南", "夏南栀负责，质量这边只会签", "冷却验证负责人调整", "APPT-006", "中", "已确认", "进入V2"),
        ("U007", "软件开发部", "邵予白", "车载软件", "B2样阶段", "车载软件版本冻结", "负责人调整", "owner_name=乔安澜", "邵予白接版本冻结", "软件发布责任人调整", "APPT-007", "高", "已确认", "进入V2"),
        ("U008", "测试验证部", "秦若南", "热管理", "A样阶段", "A样测试方案", "交付文档变更", "deliverable=A样测试方案", "统一叫A样DVP&R测试方案", "测试模板升级", "MIN-004", "高", "会议确认", "进入V2"),
        ("U009", "质量管理部", "何沐川", "电机", "策划阶段", "DFMEA", "交付文档变更", "deliverable=DFMEA记录", "DFMEA及特殊特性清单", "特殊特性需同步输出", "MIN-005", "中", "会议确认", "进入V2"),
        ("U010", "采购部", "温澄", "传动系统", "C样阶段", "PPAP资料准备", "交付文档变更", "deliverable=PPAP资料包", "PPAP提交包及检查清单", "PPAP提交包需增加检查表", "MIN-006", "高", "会议确认", "进入V2"),
        ("U011", "电机系统部", "方澄远", "电机", "B2样阶段", "电机DV测试", "交付文档变更", "deliverable=电机DV测试报告", "电机DV测试报告及问题闭环表", "DV问题闭环需一并归档", "MIN-007", "中", "会议确认", "进入V2"),
        ("U012", "软件开发部", "邵予白", "车载软件", "SOP阶段", "车载软件配置基线归档", "交付文档变更", "deliverable=车载软件配置基线归档记录", "量产软件配置基线包", "软件配置审计要求", "MIN-008", "中", "会议确认", "进入V2"),
        ("U013", "质量管理部", "何沐川", "电源", "策划阶段", "高压安全评审", "审批角色调整", "approval_role=质量工程师", "审批改成项目经理，质量工程师会签", "高压安全属于阶段门关键风险", "MIN-009", "高", "会议确认", "进入V2"),
        ("U014", "采购部", "温澄", "电源", "B2样阶段", "B2样BOM冻结", "审批角色调整", "approval_role=采购工程师", "建议供应商质量工程师审批，采购参与", "关键外购件冻结需SQE确认", "MIN-010", "中", "会议确认", "进入V2"),
        ("U015", "项目管理部", "周宁", "电控", "B2样阶段", "B2样设计冻结评审", "审批角色调整", "approval_role=项目经理", "审批角色改为质量工程师，项目经理会签", "设计冻结前加强质量门控", "MIN-011", "中", "会议确认", "进入V2"),
        ("U016", "热管理开发部", "夏南栀", "热管理", "B2样阶段", "热管理管路冻结", "责任部门调整", "responsible_department=整机集成部", "责任部门改热管理开发部", "管路冻结由热管理归口", "MIN-012", "中", "会议确认", "进入V2"),
        ("U017", "电控软件部", "邵予白", "电控", "C样阶段", "电控EOL测试脚本确认", "责任部门调整", "responsible_department=制造工程部", "责任部门改电控软件部，制造会签", "脚本逻辑由电控维护", "MIN-013", "中", "会议确认", "进入V2"),
        ("U018", "项目管理部", "周宁", "热管理", "SOP阶段", "量产成本闭环", "时间规则调整", "due_rule=SOP后10个工作日", "改成SOP后15个工作日", "首批订单结算周期延长", "MIN-014", "低", "会议确认", "进入V2"),
        ("U019", "测试验证部", "秦若南", "整机", "B1样阶段", "整车道路试验", "时间规则调整", "due_rule=试验完成后5个工作日", "试验完成后7个工作日", "道路试验报告照片和日志补录耗时更长", "MIN-015", "中", "会议确认", "进入V2"),
        ("U020", "制造工程部", "傅景元", "电源", "D样阶段", "SOP准备检查", "时间规则调整", "due_rule=GR7前2个工作日", "GR7前4个工作日", "SOP检查项多，需要提前关闭", "MIN-016", "中", "会议确认", "进入V2"),
        ("U021", "系统工程部", "陆知衡", "整机", "策划阶段", "功能安全影响分析", "新增任务节点", "", "新增功能安全影响分析节点", "策划阶段需识别功能安全影响", "MIN-001", "高", "会议确认", "进入V2"),
        ("U022", "电源开发部", "顾景初", "电源", "A样阶段", "高压互锁检查", "新增任务节点", "", "新增高压互锁检查，顾景初负责", "A样前置安全检查缺失", "MIN-002", "高", "会议确认", "进入V2"),
        ("U023", "电控软件部", "邵予白", "电控", "B1样阶段", "诊断DTC一致性检查", "新增任务节点", "", "新增诊断DTC一致性检查", "诊断功能评审后需检查DTC映射", "MIN-003", "中", "会议确认", "进入V2"),
        ("U024", "热管理开发部", "夏南栀", "热管理", "C样阶段", "冷却液泄漏复核", "新增任务节点", "", "新增冷却液泄漏复核", "C样试生产发现泄漏线索", "CHAT-014;MIN-017", "高", "会议确认", "进入V2"),
        ("U025", "软件开发部", "邵予白", "车载软件", "A样阶段", "开源组件合规确认", "新增任务节点", "", "新增开源组件合规确认", "软件合规要求前移", "MIN-018", "中", "会议确认", "进入V2"),
        ("U026", "质量管理部", "何沐川", "车载软件", "B1样阶段", "B1样人工复核记录", "新增任务节点", "", "新增B1样人工复核记录表", "关键结论需人工复核", "CHAT-001;MIN-017", "高", "会议确认", "进入V2"),
        ("U027", "供应商质量部", "姜予安", "传动系统", "C样阶段", "传动供应商变更复核", "新增任务节点", "", "传动供应商变更复核，SQE看一下", "供应商工艺切换需形成记录", "MIN-018", "中", "会议确认", "进入V2"),
        ("U028", "项目管理部", "周宁", "传动系统", "SOP阶段", "SOP配置差异复盘", "新增任务节点", "", "SOP阶段补一个配置差异复盘", "项目总结需沉淀配置变化", "MIN-018", "低", "会议确认", "进入V2"),
        ("U029", "系统工程部", "陆知衡", "车载软件", "策划阶段", "系统需求分解", "任务名称规范化", "系统需求分解", "系统需求分解与追溯", "需求追溯字段需前置", "MIN-019", "中", "会议确认", "进入V2"),
        ("U030", "电控软件部", "乔安澜", "电控", "B1样阶段", "软件集成测试", "任务名称规范化", "软件集成测试", "叫软件集成验证可能更贴切", "聊天里有人提了，没正式定", "CHAT-006", "低", "待复核", "弱线索"),
        ("U031", "制造工程部", "傅景元", "电机", "D样阶段", "D样生产验证", "负责人调整", "owner_name=傅景元", "可能由罗星野接，先别改", "口头提到工艺牵头", "CHAT-009", "低", "待复核", "弱线索"),
        ("U032", "项目管理部", "周宁", "整机", "B2样阶段", "整车问题关闭", "审批角色调整", "approval_role=项目经理", "也许改系统工程师审批？", "信息冲突，需等会议", "CHAT-012", "低", "待复核", "弱线索"),
        ("U033", "项目管理部", "魏书言", "热管理", "SOP阶段", "量产成本闭环", "交付文档变更", "deliverable=量产成本闭环报告", "想改量产成本收益复盘报告", "财务建议，会议未确认", "CHAT-019", "低", "待复核", "弱线索"),
        ("U034", "硬件开发部", "沈清和", "电源", "B2样阶段", "电源BOM冻结", "责任部门调整", "responsible_department=电源开发部", "可能转采购部维护BOM", "只有群聊提到", "CHAT-020", "低", "待复核", "弱线索"),
        ("U035", "整机集成部", "叶云澈", "整机", "准备阶段", "整车集成边界确认", "时间规则调整", "due_rule=GR1前4个工作日", "可能要GR1前6天", "边界输入经常晚到", "CHAT-021", "低", "待复核", "弱线索"),
        ("U036", "质量管理部", "何沐川", "电机", "C样阶段", "电机OTS认可", "审批角色调整", "approval_role=质量工程师", "采购也想会签，不确定", "聊天线索", "CHAT-022", "低", "待复核", "弱线索"),
        ("U037", "软件开发部", "乔安澜", "车载软件", "D样阶段", "车载软件量产发布检查", "时间规则调整", "due_rule=GR7前3个工作日", "有人说可以放到GR7后，但没有会议结论", "仅口头讨论，和现行阶段门逻辑冲突", "CHAT-023", "低", "待复核", "弱线索"),
    ]
    return [update_row(*item) for item in data]


def build_v2_config(v1_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """基于 V1.0 生成 V2.0，包含 20 多处可追溯变化。"""
    rows = deepcopy(v1_rows)
    changes = {
        "客户需求分析": {"owner_name": "陆知衡", "source": "U001;APPT-001"},
        "电机控制策略评审": {"owner_name": "方澄远", "source": "U002;APPT-002"},
        "软件需求冻结": {"owner_name": "邵予白", "source": "U003;APPT-003"},
        "电池包接口评审": {"owner_name": "顾景初", "source": "U004;APPT-004"},
        "整车集成评审": {"owner_name": "林越川", "source": "U005;APPT-005"},
        "冷却系统验证": {"owner_name": "夏南栀", "source": "U006;APPT-006"},
        "车载软件版本冻结": {"owner_name": "邵予白", "source": "U007;APPT-007"},
        "A样测试方案": {"deliverable": "A样DVP&R测试方案", "source": "U008;MIN-004"},
        "DFMEA": {"deliverable": "DFMEA及特殊特性清单", "source": "U009;MIN-005"},
        "PPAP资料准备": {"deliverable": "PPAP提交包及检查清单", "source": "U010;MIN-006"},
        "电机DV测试": {"deliverable": "电机DV测试报告及问题闭环表", "source": "U011;MIN-007"},
        "车载软件配置基线归档": {"deliverable": "量产软件配置基线包", "source": "U012;MIN-008"},
        "高压安全评审": {"approval_role": "项目经理", "approval_mode": "会签", "source": "U013;MIN-009"},
        "B2样BOM冻结": {"approval_role": "供应商质量工程师", "source": "U014;MIN-010"},
        "B2样设计冻结评审": {"approval_role": "质量工程师", "source": "U015;MIN-011"},
        "热管理管路冻结": {"responsible_department": "热管理开发部", "source": "U016;MIN-012"},
        "电控EOL测试脚本确认": {"responsible_department": "电控软件部", "source": "U017;MIN-013"},
        "量产成本闭环": {"due_rule": "SOP后15个工作日", "source": "U018;MIN-014"},
        "整车道路试验": {"due_rule": "试验完成后7个工作日", "source": "U019;MIN-015"},
        "SOP准备检查": {"due_rule": "GR7前4个工作日", "source": "U020;MIN-016"},
        "系统需求分解": {"task_name": "系统需求分解与追溯", "task_alias": "需求追溯", "source": "U029;MIN-019"},
    }
    for row in rows:
        row.update(changes.get(row["task_name"], {}))
        row["version"] = "V2.0"
        row["effective_date"] = "2025-03-15"
        if row["source"] == "SYS-V1":
            row["source"] = "SYS-V1继承"

    next_id = len(rows) + 1
    new_tasks = [
        ("整机", "策划阶段", "功能安全影响分析", "功能安全", "系统工程师", "系统需求规格说明书", "功能安全影响分析表", "质量工程师", "会签", "系统需求分解完成后", "GR2前5个工作日", "MIN-001;U021", "系统工程部、质量管理部"),
        ("电源", "A样阶段", "高压互锁检查", "HVIL检查", "硬件工程师", "A样设计输入冻结单", "高压互锁检查记录", "质量工程师", "会签", "电源A样上电前", "上电前2个工作日", "MIN-002;U022", "电源开发部、测试验证部"),
        ("电控", "B1样阶段", "诊断DTC一致性检查", "DTC检查", "软件工程师", "诊断功能评审记录", "诊断DTC一致性检查表", "系统工程师", "会签", "B1诊断软件发布后", "GR4前2个工作日", "MIN-003;U023", "系统工程部"),
        ("热管理", "C样阶段", "冷却液泄漏复核", "泄漏复核", "测试工程师", "冷却系统验证报告", "冷却液泄漏复核表", "质量工程师", "会签", "C样冷却回路装配后", "GR6前3个工作日", "CHAT-014;MIN-017;U024", "热管理开发部、制造工程部"),
        ("车载软件", "A样阶段", "开源组件合规确认", "开源合规", "软件工程师", "车载软件架构评审记录", "开源组件合规确认单", "质量工程师", "会签", "A样代码基线建立后", "GR3前2个工作日", "MIN-018;U025", "质量管理部"),
        ("车载软件", "B1样阶段", "B1样人工复核记录", "人工复核", "质量工程师", "B1样验证报告", "B1样人工复核记录表", "项目经理", "会签", "关键结论提交后", "提交后1个工作日", "CHAT-001;MIN-017;U026", "项目管理部"),
        ("传动系统", "C样阶段", "传动供应商变更复核", "供应商变更", "供应商质量工程师", "传动系统PPAP复核表", "传动供应商变更复核表", "质量工程师", "会签", "供应商工艺变更提出后", "GR6前3个工作日", "MIN-018;U027", "采购部、质量管理部"),
        ("传动系统", "SOP阶段", "SOP配置差异复盘", "配置复盘", "项目经理", "项目经验总结报告", "SOP配置差异复盘报告", "项目经理", "单人审批", "项目总结启动后", "SOP后12个工作日", "MIN-018;U028", "系统工程部、质量管理部"),
    ]
    for item in new_tasks:
        domain, phase, task_name, alias, role, input_doc, deliverable, approval_role, approval_mode, trigger, due, source, collaborate = item
        rows.append(make_task(next_id, PROJECT_TYPES[(next_id - 1) % len(PROJECT_TYPES)], domain, phase, task_name, alias, role, input_doc, deliverable, approval_role, approval_mode, trigger, due, "V2.0", "2025-03-15", source, collaborate_departments=collaborate))
        next_id += 1
    return rows


def col_name(index: int) -> str:
    """把从 1 开始的列号转换为 Excel 列名。"""
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    """写入 CSV，使用 utf-8-sig 方便 Excel 正确识别中文。"""
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_xlsx(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    """用标准库写入一个简单的 xlsx 工作簿。"""
    table = [fields] + [[str(row.get(field, "")) for field in fields] for row in rows]
    sheet_rows = []
    for r_idx, row in enumerate(table, 1):
        cells = []
        for c_idx, value in enumerate(row, 1):
            ref = f"{col_name(c_idx)}{r_idx}"
            safe_value = html.escape(value, quote=False)
            cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{safe_value}</t></is></c>')
        sheet_rows.append(f'<row r="{r_idx}">{"".join(cells)}</row>')

    dimension = f"A1:{col_name(len(fields))}{len(table)}"
    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<dimension ref="{dimension}"/>'
        '<sheetViews><sheetView workbookViewId="0"/></sheetViews>'
        '<sheetFormatPr defaultRowHeight="15"/>'
        f'<sheetData>{"".join(sheet_rows)}</sheetData>'
        "</worksheet>"
    )
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )
    workbook_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        "</Relationships>"
    )
    content_types_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        "</Types>"
    )
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as xlsx:
        xlsx.writestr("[Content_Types].xml", content_types_xml)
        xlsx.writestr("_rels/.rels", rels_xml)
        xlsx.writestr("xl/workbook.xml", workbook_xml)
        xlsx.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml)
        xlsx.writestr("xl/worksheets/sheet1.xml", sheet_xml)


def write_table_files(filename: str, rows: list[dict[str, str]], fields: list[str]) -> None:
    """同名输出 xlsx 和 csv 两种格式。"""
    write_xlsx(DATA_DIR / f"{filename}.xlsx", rows, fields)
    write_csv(DATA_DIR / f"{filename}.csv", rows, fields)


def build_notice_md() -> str:
    """生成模拟 PDF 解析后的任命调整通知。"""
    rows = [
        ("电控", "立项阶段", "客户需求分析", "许知行", "陆知衡", "系统工程部", "2025-03-15", "APPT-001"),
        ("电机", "策划阶段", "电机控制策略评审", "陆知衡", "方澄远", "电机系统部", "2025-03-15", "APPT-002"),
        ("电控", "策划阶段", "软件需求冻结", "乔安澜", "邵予白", "电控软件部", "2025-03-15", "APPT-003"),
        ("电源", "策划阶段", "电池包接口评审", "沈清和", "顾景初", "电源开发部", "2025-03-15", "APPT-004"),
        ("整机", "策划阶段", "整车集成评审", "叶云澈", "林越川", "整机集成部", "2025-03-15", "APPT-005"),
        ("热管理", "B1样阶段", "冷却系统验证", "秦若南", "夏南栀", "热管理开发部", "2025-03-15", "APPT-006"),
        ("车载软件", "B2样阶段", "车载软件版本冻结", "乔安澜", "邵予白", "软件开发部", "2025-03-15", "APPT-007"),
        ("车载软件", "B1样阶段", "B1样人工复核记录", "何沐川", "何沐川", "质量管理部", "2025-03-15", "APPT-008"),
        ("电源", "A样阶段", "高压互锁检查", "沈清和", "顾景初", "电源开发部", "2025-03-15", "APPT-009"),
        ("电控", "B1样阶段", "诊断DTC一致性检查", "乔安澜", "邵予白", "电控软件部", "2025-03-15", "APPT-010"),
        ("热管理", "C样阶段", "冷却液泄漏复核", "秦若南", "夏南栀", "热管理开发部", "2025-03-15", "APPT-011"),
        ("传动系统", "C样阶段", "传动供应商变更复核", "姜予安", "姜予安", "质量管理部", "2025-03-15", "APPT-012"),
        ("传动系统", "SOP阶段", "SOP配置差异复盘", "周宁", "周宁", "项目管理部", "2025-03-15", "APPT-013"),
    ]
    lines = [
        "# 任命调整通知",
        "",
        "以下内容为模拟 PDF 解析文本。为配合虚构项目开发流程配置 V2.0 发布，确保电机、电控、电源、整机、热管理、传动系统及车载软件相关任务责任清晰，经虚构项目管理委员会确认，自 2025-03-15 起按下表执行负责人调整。本通知仅用于模拟数据，不代表任何真实公司、真实客户或真实人员。",
        "",
        "| 业务域 | 阶段 | 任务名称 | 原负责人 | 新负责人 | 责任部门 | 生效日期 | 调整依据 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    lines.extend(f"| {' | '.join(row)} |" for row in rows)
    return "\n".join(lines) + "\n"


def build_minutes_md() -> str:
    """生成更贴近真实场景的流程配置变更会议纪要。"""
    conclusions = [
        "新增“功能安全影响分析”节点，放入策划阶段 GR2 前，依据编号 MIN-001。",
        "新增“高压互锁检查”节点，放入电源 A样阶段，依据编号 MIN-002。",
        "新增“诊断DTC一致性检查”节点，放入电控 B1样阶段，依据编号 MIN-003。",
        "A样测试方案交付文档统一调整为“A样DVP&R测试方案”，依据编号 MIN-004。",
        "DFMEA交付物调整为“DFMEA及特殊特性清单”，依据编号 MIN-005。",
        "PPAP资料准备交付物调整为“PPAP提交包及检查清单”，依据编号 MIN-006。",
        "电机DV测试交付物调整为“电机DV测试报告及问题闭环表”，依据编号 MIN-007。",
        "车载软件配置基线归档交付物调整为“量产软件配置基线包”，依据编号 MIN-008。",
        "高压安全评审审批角色调整为项目经理，质量工程师会签，依据编号 MIN-009。",
        "B2样BOM冻结审批角色调整为供应商质量工程师，采购工程师参与会签，依据编号 MIN-010。",
        "B2样设计冻结评审审批角色调整为质量工程师，依据编号 MIN-011。",
        "热管理管路冻结责任部门调整为热管理开发部，依据编号 MIN-012。",
        "电控EOL测试脚本确认责任部门调整为电控软件部，制造工程部协同，依据编号 MIN-013。",
        "量产成本闭环时间规则调整为 SOP后15个工作日，依据编号 MIN-014。",
        "整车道路试验报告时间规则调整为试验完成后7个工作日，依据编号 MIN-015。",
        "SOP准备检查时间规则调整为 GR7前4个工作日，依据编号 MIN-016。",
        "聊天记录中提到的 B1样人工复核、冷却液泄漏复核可进入 V2.0，但需在正式上线前人工复核，依据编号 MIN-017。",
        "传动供应商变更复核、开源组件合规确认、SOP配置差异复盘进入新增节点清单，依据编号 MIN-018。",
    ]
    todos = [
        "项目管理部在 2025-03-12 前输出 V2.0 建议清单。",
        "质量管理部复核所有新增节点的必填性和审批链路。",
        "系统工程部核对任务名称规范化是否影响历史数据映射。",
        "各业务域责任部门确认协同部门字段是否遗漏。",
    ]
    risks = [
        "聊天记录与会议纪要不一致时，以会议纪要为准，并标记需人工复核。",
        "负责人调整必须与任命通知一致，缺少 APPT 编号不得直接进入正式系统。",
        "时间规则调整可能影响阶段门达成率统计，正式上线前需做口径说明。",
    ]
    lines = [
        "# 流程配置变更会议纪要",
        "",
        "- 会议主题：项目开发流程配置 V2.0 变更评审会",
        "- 会议时间：2025-03-03 14:00-16:30",
        "- 会议地点：虚构协同会议室 P2 / 线上会议",
        "- 参会角色：项目经理、产品经理、系统工程师、软件工程师、硬件工程师、测试工程师、质量工程师、采购工程师、制造工程师、工艺工程师、成本经理、供应商质量工程师、项目财务经理",
        "",
        "## 背景说明",
        "",
        "V1.0 流程配置主要覆盖通用项目开发任务，对电机、电控、电源、整机、热管理、传动系统和车载软件的业务域差异表达不足。各部门在飞书表格中提交了多项配置变更建议，其中部分建议来自正式任命通知，部分来自会议讨论，另有少量来自聊天记录，需要区分证据强弱。",
        "",
        "## 讨论摘要",
        "",
        "1. 各业务域同意在不改变阶段门主线的前提下补充专业任务节点。",
        "2. 文档命名以阶段门输入输出一致性为原则，涉及历史名称的任务需要保留别名。",
        "3. 部分聊天记录内容存在冲突，只可作为检索线索，不能单独作为正式变更依据。",
        "",
        "## 会议结论",
        "",
    ]
    lines.extend(f"{idx}. {item}" for idx, item in enumerate(conclusions, 1))
    lines.extend(["", "## 待办事项", ""])
    lines.extend(f"- {item}" for item in todos)
    lines.extend(["", "## 风险提示", ""])
    lines.extend(f"- {item}" for item in risks)
    return "\n".join(lines) + "\n"


def build_chat_md() -> str:
    """生成口语化、存在冲突且需要复核的聊天记录。"""
    messages = [
        ("2025-02-26 10:15", "项目经理-周宁", "B2样阶段的设计冻结评审后续可能要项目经理牵头，系统工程师参与，具体等会议纪要确认。"),
        ("2025-02-26 10:22", "质量工程师-何沐川", "B1样验证后最好加个人工复核，不然几个关键结论进系统太快了。"),
        ("2025-02-26 10:37", "系统工程师-陆知衡", "客户需求分析我这边可以接，但产品经理还得会签，别写成完全移交。"),
        ("2025-02-26 11:04", "电机工程师-方澄远", "电机控制策略评审后面我来牵头，测试那边帮忙看可测性。"),
        ("2025-02-26 11:20", "软件工程师-邵予白", "软件需求冻结不要叫冻结会了吧，叫软件需求冻结单更像交付物。"),
        ("2025-02-26 11:33", "软件工程师-乔安澜", "软件集成测试这个名字是不是改成软件集成验证？我不确定，先记个线索。"),
        ("2025-02-26 13:10", "硬件工程师-沈清和", "电源BOM冻结我听采购说他们想维护，但电源开发这边还没点头。"),
        ("2025-02-26 13:45", "采购工程师-温澄", "BOM冻结还是SQE审批比较稳，采购参与就行，这个看会议怎么定。"),
        ("2025-02-26 14:02", "制造工程师-傅景元", "D样生产验证也许后面让工艺牵头，我只是听说，别直接改。"),
        ("2025-02-26 14:18", "工艺工程师-罗星野", "SOP准备检查建议提前到GR7前4天，不然现场问题来不及关。"),
        ("2025-02-26 14:41", "热管理工程师-夏南栀", "热管理管路冻结还是归我们热管理开发部吧，整机那边只协同。"),
        ("2025-02-26 15:03", "整机工程师-林越川", "整车问题关闭我觉得项目经理批就可以，系统工程师审批可能不合适。"),
        ("2025-02-26 15:09", "系统工程师-陆知衡", "整车问题关闭也可以系统工程师审，不过这个和林越川说的不一样，先别定。"),
        ("2025-02-26 15:27", "测试工程师-秦若南", "冷却液泄漏复核这个节点可能要加，C样装配后经常才暴露。"),
        ("2025-02-26 15:55", "质量工程师-何沐川", "DFMEA要带特殊特性清单，否则后面PPAP老是追不到。"),
        ("2025-02-26 16:12", "供应商质量工程师-姜予安", "传动供应商如果换工艺，C样阶段最好有个复核表。"),
        ("2025-02-26 16:30", "项目财务经理-魏书言", "量产成本闭环报告想加收益复盘，但这个只是财务建议，没会上定。"),
        ("2025-02-26 16:48", "软件工程师-邵予白", "开源组件合规确认能不能前移到A样？不然后面补材料很痛苦。"),
        ("2025-02-26 17:06", "成本经理-韩知夏", "量产成本闭环10天可能不够，15天比较现实。"),
        ("2025-02-26 17:21", "整机工程师-叶云澈", "整车集成边界确认经常晚，可能要GR1前6天，但我没有正式依据。"),
        ("2025-02-26 17:36", "质量工程师-何沐川", "电机OTS认可采购也想会签，但目前只听到一句，先不要进正式配置。"),
        ("2025-02-26 18:02", "项目经理-周宁", "SOP阶段补一个配置差异复盘挺有必要，等会议纪要给结论。"),
    ]
    lines = ["# 口头通知/聊天记录", ""]
    for time_text, speaker, content in messages:
        lines.extend([f"[{time_text}] {speaker}：", content, ""])
    return "\n".join(lines).rstrip() + "\n"


def build_rule_manual_md() -> str:
    """生成流程配置变更规则说明。"""
    return """# 流程配置变更规则说明

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
"""


def write_markdown_files() -> None:
    """写入四份 markdown 场景资料。"""
    (DATA_DIR / "04_appointment_adjustment_notice.md").write_text(build_notice_md(), encoding="utf-8")
    (DATA_DIR / "05_process_change_meeting_minutes.md").write_text(build_minutes_md(), encoding="utf-8")
    (DATA_DIR / "06_chat_change_messages.md").write_text(build_chat_md(), encoding="utf-8")
    (DATA_DIR / "07_process_rule_manual.md").write_text(build_rule_manual_md(), encoding="utf-8")


def main() -> None:
    """生成 data 目录下全部模拟数据文件。"""
    if DATA_DIR.exists():
        shutil.rmtree(DATA_DIR)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    v1_rows = build_v1_config()
    update_rows = build_updates()
    v2_rows = build_v2_config(v1_rows)

    write_table_files("01_system_export_current_config", v1_rows, CONFIG_FIELDS)
    write_table_files("02_department_update_feishu", update_rows, UPDATE_FIELDS)
    write_table_files("03_target_config_v2", v2_rows, CONFIG_FIELDS)
    write_markdown_files()

    print(f"已生成模拟数据目录：{DATA_DIR}")
    print(f"V1配置任务：{len(v1_rows)} 条")
    print(f"部门更新记录：{len(update_rows)} 条")
    print(f"V2配置任务：{len(v2_rows)} 条")
    print("生成文件：")
    for path in sorted(DATA_DIR.iterdir()):
        print(f"- {path.name}")


if __name__ == "__main__":
    # 固定规则生成，保证每次运行输出一致，方便测试和回归比对。
    os.chdir(ROOT_DIR)
    main()
