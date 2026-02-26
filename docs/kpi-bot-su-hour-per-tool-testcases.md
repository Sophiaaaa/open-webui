# KPI Bot（su_hour_per_tool）自然语言识别测试用例

本文档用于测试 KPI Bot 对 `su_hour_per_tool`（每机台装机时间 / SU Hour per Tool）在不同自然语言表达下的识别能力，覆盖：

- 指标问法（KPI 识别）
- 时间描述（time_range 解析）
- 范围描述（scope 解析：product / organization / tools）
- 组合场景与多轮对话（missing_params / finished_selection）
- 边界与反例（避免误判）

## 0. 测试基准与输出字段

### 0.1 基准日期（用于相对时间）

后端时间解析会依赖“当前日期”。本用例以 **2026-02-26** 为测试基准日（与本仓库环境一致）。

- 自然年：2026 年 = `202601-202612`
- 财年定义：财年从 4 月开始，到次年 3 月结束
  - 当前财年（基准日 2026-02-26）= `202504-202603`
  - 半期（基准日 2026-02-26，落在 FY 的 10~03 段）= `202510-202603`

### 0.2 期望解析字段（用于人工核对）

建议在每条用例中核对以下字段（对应后端 analyze_intent 的返回）：

- `kpi`：期望为 `su_hour_per_tool`
- `time_range`：`YYYYMM` 或 `YYYYMM-YYYYMM` 或 `all` 或 `null`
- `scope`：`["product:CT", "organization:xxx", "tools:100367", ...]`
- `missing_params`：可能包含 `time_range` / `scope`
- `finished_selection`：在用户表达“无/不用/就这样/全部/跳过”等否定或结束意图时应为 `true`

## 1. KPI 问法（只测试指标识别）

说明：本节用例的重点是 `kpi` 是否识别为 `su_hour_per_tool`。时间与范围可为空（期望 `missing_params` 至少包含 `time_range`，scope 可能也会缺失）。

| ID | 用户输入 | 期望 kpi |
|---:|---|---|
| K-001 | su hour per tool | su_hour_per_tool |
| K-002 | SU HOUR PER TOOL | su_hour_per_tool |
| K-003 | Su Hour Per Tool 是多少 | su_hour_per_tool |
| K-004 | startup hour per tool | su_hour_per_tool |
| K-005 | Startup Hour per Tool 结果 | su_hour_per_tool |
| K-006 | su hour | su_hour_per_tool |
| K-007 | SU hour 统计一下 | su_hour_per_tool |
| K-008 | su工时 | su_hour_per_tool |
| K-009 | SU工时是多少 | su_hour_per_tool |
| K-010 | 平均装机时间 | su_hour_per_tool |
| K-011 | 平均装机时间是多少？ | su_hour_per_tool |
| K-012 | 平均装机小时数 | su_hour_per_tool |
| K-013 | 平均装机小时 | su_hour_per_tool |
| K-014 | 装机时间 | su_hour_per_tool |
| K-015 | 装机工时 | su_hour_per_tool |
| K-016 | 机台装机时间 | su_hour_per_tool |
| K-017 | 每机台装机时间 | su_hour_per_tool |
| K-018 | 平均每台装机结果 | su_hour_per_tool |
| K-019 | 平均每台的装机结果 | su_hour_per_tool |
| K-020 | 查询 SU Hour per Tool | su_hour_per_tool |
| K-021 | 帮我查一下 su hour per tool | su_hour_per_tool |
| K-022 | 想看 SU Hour per Tool 的数据 | su_hour_per_tool |
| K-023 | su hour per tool 趋势 | su_hour_per_tool |
| K-024 | su hour per tool 分析 | su_hour_per_tool |
| K-025 | 我只关心装机工时这个指标 | su_hour_per_tool |
| K-026 | 这个月装机时间怎么样 | su_hour_per_tool |
| K-027 | su hour per tool，时间先不说 | su_hour_per_tool |
| K-028 | su hour per tool scope 也先不说 | su_hour_per_tool |
| K-029 | su hour per tool + 机台数量（应仍命中 su） | su_hour_per_tool |
| K-030 | fe 人数 和 su hour per tool（应仍命中 su） | su_hour_per_tool |

## 2. 时间描述（time_range 解析）

说明：本节用例用“固定 KPI 触发词 + 时间表达”来验证 `time_range` 是否符合预期。范围（scope）可为空。

### 2.1 单月（YYYYMM）与月度写法

| ID | 用户输入 | 期望 time_range |
|---:|---|---|
| T-001 | 202501 的 su hour per tool | 202501 |
| T-002 | 2025-01 的 su hour per tool | 202501 |
| T-003 | 2025/01 的 su hour per tool | 202501 |
| T-004 | 2025年1月 su hour per tool | 202501 |
| T-005 | 2025年01月 su hour per tool | 202501 |
| T-006 | 2025年1月份 su hour per tool | 202501 |
| T-007 | 25年1月 su hour per tool | 202501 |
| T-008 | 25年01月 su hour per tool | 202501 |
| T-009 | 25年1月份 su hour per tool | 202501 |
| T-010 | 202512 装机工时 | 202512 |

### 2.2 月份范围（YYYYMM-YYYYMM）

| ID | 用户输入 | 期望 time_range |
|---:|---|---|
| T-011 | 202501-202506 的 su hour per tool | 202501-202506 |
| T-012 | 202504-202603 的 su hour per tool | 202504-202603 |
| T-013 | FY26 的 su hour per tool（注意：会被归一化为月度范围） | 202504-202603 |
| T-014 | FY2026 的 su hour per tool | 202504-202603 |

### 2.3 自然年（2024年 / 24年 / 今年去年明年）

| ID | 用户输入 | 期望 time_range |
|---:|---|---|
| T-021 | 2024年 su hour per tool | 202401-202412 |
| T-022 | 24年 su hour per tool | 202401-202412 |
| T-023 | 2026年 su hour per tool | 202601-202612 |
| T-024 | 今年 su hour per tool（基准日 2026-02-26） | 202601-202612 |
| T-025 | 去年 su hour per tool（基准日 2026-02-26） | 202501-202512 |
| T-026 | 明年 su hour per tool（基准日 2026-02-26） | 202701-202712 |
| T-027 | 本年 su hour per tool（基准日 2026-02-26） | 202601-202612 |

### 2.4 自然季度（中文“第X季度”/ “Qx”）

| ID | 用户输入 | 期望 time_range |
|---:|---|---|
| T-031 | 2025年第一季度 su hour per tool | 202501-202503 |
| T-032 | 2025年第二季度 su hour per tool | 202504-202506 |
| T-033 | 2025年第三季度 su hour per tool | 202507-202509 |
| T-034 | 2025年第四季度 su hour per tool | 202510-202512 |
| T-035 | 25年3季度 su hour per tool | 202507-202509 |
| T-036 | 25年Q4 su hour per tool | 202510-202512 |
| T-037 | 2025年Q4 su hour per tool | 202510-202512 |

### 2.5 财年（FY）/ 财年季度 / 财年半期

| ID | 用户输入 | 期望 time_range |
|---:|---|---|
| T-041 | FY26 su hour per tool | 202504-202603 |
| T-042 | fy26 su hour per tool | 202504-202603 |
| T-043 | FY26 Q1 su hour per tool | 202504-202506 |
| T-044 | FY26 Q2 su hour per tool | 202507-202509 |
| T-045 | FY26 Q3 su hour per tool | 202510-202512 |
| T-046 | FY26 Q4 su hour per tool | 202601-202603 |
| T-047 | FY26 1H su hour per tool | 202504-202509 |
| T-048 | FY26 2H su hour per tool | 202510-202603 |
| T-049 | FY26 H1 su hour per tool | 202504-202509 |
| T-050 | FY26 H2 su hour per tool | 202510-202603 |
| T-051 | FY26 上半期 su hour per tool | 202504-202509 |
| T-052 | FY26 下半期 su hour per tool | 202510-202603 |

### 2.6 “当前财年/半期”（相对当前日期）

| ID | 用户输入 | 期望 time_range |
|---:|---|---|
| T-061 | 当前财年 su hour per tool（基准日 2026-02-26） | 202504-202603 |
| T-062 | 半期 su hour per tool（基准日 2026-02-26） | 202510-202603 |

### 2.7 “不限时间/所有时间”（all）

| ID | 用户输入 | 期望 time_range |
|---:|---|---|
| T-071 | 不限时间的 su hour per tool | all |
| T-072 | 不限制时间 su hour per tool | all |
| T-073 | 不筛选时间 su hour per tool | all |
| T-074 | 时间不做筛选 su hour per tool | all |
| T-075 | 所有时间 su hour per tool | all |
| T-076 | 全部时间 su hour per tool | all |
| T-077 | 所有范围 su hour per tool | all |
| T-078 | 全部范围 su hour per tool | all |
| T-079 | all time su hour per tool | all |
| T-080 | no time filter su hour per tool | all |

### 2.8 时间边界与反例（预期不被解析或可能缺失）

| ID | 用户输入 | 期望 time_range | 备注 |
|---:|---|---|---|
| TN-001 | 2026Q1 su hour per tool | null | 当前实现要求“年Q”或中文季度写法 |
| TN-002 | 2026-1 su hour per tool | null | 需要 2026-01 或 202601 |
| TN-003 | 2026年1-3月 su hour per tool | null | 当前未实现该类表达 |
| TN-004 | 最近7天 su hour per tool | null | 当前未实现“近N天/周”解析 |

### 2.9 细粒度与异常时间（单日/非法日期）

说明：验证 Bot 对“日”粒度的处理（通常应忽略日或提取月）以及对非法日期的容错。

| ID | 用户输入 | 期望 time_range | 备注 |
|---:|---|---|---|
| T-091 | 2025年3月15日 su hour per tool | 202503 | 预期提取“2025年3月”，忽略“15日” |
| T-092 | 2025-03-15 su hour per tool | 202503 | 预期正则匹配到 2025-03 |
| T-093 | 20250315 su hour per tool | null 或 202503 | 取决于是否被误判为 SN 或被截断 |
| T-094 | 2025年13月 su hour per tool | 202513 | 正则强行提取，SQL 无结果 |
| T-095 | 2025-13 su hour per tool | 202513 | 正则强行提取 |

## 3. 范围描述（scope 解析）

说明：本节用例验证 `scope` 的抽取。`scope` 形式为 `category:value`，其中：

- `product:CT`（产品线，内置列表匹配）
- `tools:100367`（6 位数字 SN）
- `organization:XXX`（组织/团队，建议用显式键值对确保可测）

### 3.1 产品线（product）隐式命中

| ID | 用户输入 | 期望 scope（包含） |
|---:|---|---|
| S-001 | CT 的 su hour per tool | product:CT |
| S-002 | 3DI 的 su hour per tool | product:3DI |
| S-003 | SPS 的 su hour per tool | product:SPS |
| S-004 | ES 的 su hour per tool | product:ES |
| S-005 | CT/SPS 的 su hour per tool | product:CT；product:SPS |
| S-006 | (CT) su hour per tool | product:CT |
| S-007 | 【SPS】su hour per tool | product:SPS |
| S-008 | CT，SPS 的装机工时 | product:CT；product:SPS |

### 3.2 工具/机台 SN（tools）抽取（6 位数字）

| ID | 用户输入 | 期望 scope（包含） | 备注 |
|---:|---|---|---|
| S-021 | 100367 的 su hour per tool | tools:100367 | 6 位数字 |
| S-022 | tools:100367 的 su hour per tool | tools:100367 | 显式键值对 |
| S-023 | tool:100367 的 su hour per tool | tools:100367 | tool 会归一为 tools |
| S-024 | 机台 100367 装机工时 | tools:100367 | |
| S-025 | 202503 的 su hour per tool | （不应出现 tools:202503） | 202503 会被视为时间，不应当作 SN |

### 3.3 组织/团队（organization）显式键值对

| ID | 用户输入 | 期望 scope（包含） |
|---:|---|---|
| S-041 | organization:SMSC_BJ_SPS 的 su hour per tool | organization:SMSC_BJ_SPS |
| S-042 | organization:ABC-TEAM 的 su hour per tool | organization:ABC-TEAM |
| S-043 | organization:Team_01 的 su hour per tool | organization:Team_01 |

### 3.4 scope 边界与误判防护（产品代码不应在组织编码里子串命中）

| ID | 用户输入 | 期望 scope（包含） | 期望 scope（不包含） |
|---:|---|---|---|
| SB-001 | organization:SMSC_BJ_SPS 的 su hour per tool | organization:SMSC_BJ_SPS | product:SPS |
| SB-002 | organization:XXCTYY 的 su hour per tool | organization:XXCTYY | product:CT |
| SB-003 | organization:AA-3DI-BB 的 su hour per tool | organization:AA-3DI-BB | product:3DI |

### 3.5 Scope 异常与边界（SN 长度/格式/不存在）

| ID | 用户输入 | 期望 scope（包含） | 期望 scope（不包含） | 备注 |
|---:|---|---|---|---|
| SB-011 | 12345 的 su hour per tool | (空) | tools:12345 | 5位数字不应识别为 SN |
| SB-012 | 1234567 的 su hour per tool | (空) | tools:1234567 | 7位数字不应识别为 SN |
| SB-013 | A12345 的 su hour per tool | (空) | tools:A12345 | 含字母通常不识别为 tools（除非 DB 命中） |
| SB-014 | 999999 的 su hour per tool | tools:999999 | | 6位数字正则命中，虽不存在但Bot层会透传 |
| SB-015 | SN#100367 的 su hour per tool | tools:100367 | | 若分词处理得当可能提取到 100367 |
| SB-016 | product:UnknownProduct 的 su hour per tool | product:UnknownProduct | | 显式键值对强制提取 |
| SB-017 | organization:NoExistentOrg 的 su hour per tool | organization:NoExistentOrg | | 显式键值对强制提取 |

## 4. 组合场景（KPI + 时间 + 范围）

说明：本节用例用于验证在单轮输入里，KPI/time/scope 同时存在时的正确抽取。

| ID | 用户输入 | 期望 kpi | 期望 time_range | 期望 scope（包含） |
|---:|---|---|---|---|
| C-001 | 202501 CT 的 su hour per tool | su_hour_per_tool | 202501 | product:CT |
| C-002 | 2025年1月 SPS 的装机工时 | su_hour_per_tool | 202501 | product:SPS |
| C-003 | FY26 CT 的 su hour per tool | su_hour_per_tool | 202504-202603 | product:CT |
| C-004 | FY26 Q4 100367 的 su hour per tool | su_hour_per_tool | 202601-202603 | tools:100367 |
| C-005 | 25年Q4 CT/SPS 的 su hour per tool | su_hour_per_tool | 202510-202512 | product:CT；product:SPS |
| C-006 | 当前财年 organization:SMSC_BJ_SPS 的 su hour per tool | su_hour_per_tool | 202504-202603 | organization:SMSC_BJ_SPS |
| C-007 | 不限时间 CT 的 su hour per tool | su_hour_per_tool | all | product:CT |
| C-008 | all time tools:100367 的 su hour per tool | su_hour_per_tool | all | tools:100367 |
| C-009 | 2024-2025 CT 的 su hour per tool | su_hour_per_tool | 202401-202512 | product:CT |

## 5. 多轮对话场景（补齐时间/范围/结束选择）

说明：本节用例用于在 UI 或 OpenAI 接口里模拟“先问指标 → 再补时间 → 再补范围/或跳过”的对话流程。  
期望重点：`missing_params`、`finished_selection`、以及上下文是否会被正确继承。

### 5.1 先问 KPI，后补时间

| ID | 第 1 轮用户输入 | 第 1 轮期望 | 第 2 轮用户输入 | 第 2 轮期望 time_range |
|---:|---|---|---|---|
| D-001 | su hour per tool | 缺 time_range（可能也缺 scope） | 202501 | 202501 |
| D-002 | 装机工时 | 缺 time_range（可能也缺 scope） | FY26 | 202504-202603 |
| D-003 | 平均装机小时数 | 缺 time_range（可能也缺 scope） | 不限时间 | all |

### 5.2 先问 KPI+时间，后补范围

| ID | 第 1 轮用户输入 | 第 1 轮期望 | 第 2 轮用户输入 | 第 2 轮期望 scope（包含） |
|---:|---|---|---|---|
| D-011 | 202501 su hour per tool | 缺 scope | CT | product:CT |
| D-012 | FY26 su hour per tool | 缺 scope | tools:100367 | tools:100367 |
| D-013 | 25年Q4 su hour per tool | 缺 scope | organization:SMSC_BJ_SPS | organization:SMSC_BJ_SPS |

### 5.3 用户表达“范围不补了/就这样”（finished_selection）

| ID | 第 1 轮用户输入 | 第 1 轮期望 | 第 2 轮用户输入 | 第 2 轮期望 |
|---:|---|---|---|---|
| D-021 | 202501 su hour per tool | 缺 scope | 无 | finished_selection=true，scope 仍为空 |
| D-022 | 202501 su hour per tool | 缺 scope | 不用了 | finished_selection=true，scope 仍为空 |
| D-023 | 202501 su hour per tool | 缺 scope | 就这样 | finished_selection=true，scope 仍为空 |
| D-024 | 202501 su hour per tool | 缺 scope | 跳过 | finished_selection=true，scope 仍为空 |
| D-025 | 202501 su hour per tool | 缺 scope | 全部 | finished_selection=true（注意：“全部”也可能被理解为结束选择） |

### 5.4 “只回复全部/不限”在有上下文时，弱触发 time_range=all

| ID | 第 1 轮用户输入 | 第 2 轮用户输入 | 第 2 轮期望 time_range |
|---:|---|---|---|
| D-031 | 202501 CT 的 su hour per tool | 不限 | all |
| D-032 | 202501 CT 的 su hour per tool | 全部 | all |
| D-033 | 202501 CT 的 su hour per tool | all | all |

## 6. 边界与反例（不应误识别为 su_hour_per_tool）

说明：本节用于防止 su_hour_per_tool 的关键词过度命中；同时也用于验证优先级和歧义处理。

| ID | 用户输入 | 期望 kpi | 备注 |
|---:|---|---|---|
| N-001 | 机台数量统计 | machine_count | 不应误判为装机工时 |
| N-002 | fe人数统计 | fe_count | 不应误判为装机工时 |
| N-003 | os人数统计 | os_count | 不应误判为装机工时 |
| N-004 | chamber数量统计 | chamber_count | 不应误判为装机工时 |
| N-005 | 装机（不含“装机时间/工时”等关键词） | null | 当前规则不包含“装机”单词 |
| N-006 | SU（仅 SU 两个字母） | null | 当前规则不包含单独“su” |

## 7. 补充场景：复杂异常输入与鲁棒性

说明：验证 Bot 在面对冲突信息、特殊字符、超长输入时的表现。

| ID | 用户输入 | 期望 kpi | 期望 time_range | 期望 scope | 备注 |
|---:|---|---|---|---|---|
| R-001 | 202501 202601 su hour per tool | su_hour_per_tool | 202501 | | 冲突时间：预期优先匹配第一个 |
| R-002 | 202501-202503 202504-202506 su hour per tool | su_hour_per_tool | 202501-202503 | | 冲突范围：预期优先匹配第一个范围 |
| R-003 | su hour per tool @#$%^&*() | su_hour_per_tool | | | 忽略特殊符号 |
| R-004 | su hour per tool OR 1=1 | su_hour_per_tool | | | SQL注入尝试应被忽略或视为文本 |
| R-005 | su hour per tool tools:100367 tools:100368 | su_hour_per_tool | | tools:100367, tools:100368 | 重复 Key 应合并为列表 |
| R-006 | su hour per tool 100367 100368 | su_hour_per_tool | | tools:100367, tools:100368 | 多个 SN 应都被正则捕获 |


