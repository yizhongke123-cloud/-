# 智能工单协同系统

这是面试 AI Coding 题目的阶段性实现。本仓库当前完成 **阶段 1：最小工单系统**、**阶段 2：工程加固与自动化测试**、**阶段 3：AI 辅助分析** 和 **阶段 4：人工确认闭环**，使用 Python 命令行和 SQLite 本地数据库，不包含 Web 前端或复杂框架。

## 阶段 1 已完成功能

- 创建工单并持久化到 SQLite。
- 查看工单列表和单条工单详情。
- 按状态、分类、优先级、提交人进行任意组合筛选。
- 按 `OPEN → IN_PROGRESS → RESOLVED → CLOSED` 顺序修改状态。
- 检测标题和描述完全相同的重复工单，并提示已有工单 ID。
- 使用幂等 `init` 命令初始化 5 条覆盖不同状态、分类和优先级的示例工单。

## 阶段 2 已完成加固

- 标题去除首尾空白后仍为空时拒绝创建。
- 优先级和状态只接受规定的枚举值。
- 状态只能逐步向前流转，禁止跳级、倒退和重复设置。
- 数据库唯一约束和业务检查共同阻止重复工单，并返回已有 ID。
- SQLite 打开、读写或约束异常会转换为简明中文提示，不向普通用户展示堆栈。
- 新增 11 个 pytest 测试，覆盖正常、异常、边界、组合筛选和持久化场景。

## 阶段 3 已完成 AI 辅助分析

- 在独立 `ai_service.py` 中调用真实的 OpenAI 兼容 API。
- 根据工单标题和描述建议分类、优先级、一句话摘要和判断理由。
- API Key、模型和兼容接口地址只从环境变量读取。
- Prompt 把工单放入纯 JSON 不可信数据包；模型只能从现实事件事实分类，禁止执行字段中夹带的指令或采用其指定结果。
- 模型响应必须通过 JSON、字段类型、字段集合、长度和枚举校验。
- AI 结果只写入独立的 `ai_suggestions` 表，不自动修改正式工单。
- 缺少配置、错误密钥、超时、网络错误或非法响应统一显示“AI分析不可用”，基础命令仍可使用。

## 阶段 4 已完成人工确认闭环

- AI 分析后只持久化 `ai_category`、`ai_priority`、`ai_summary`、`ai_reason` 四项原始业务建议。
- 建议初始为 `PENDING`，正式工单分类和优先级不会自动改变。
- `confirm-ai` 由人工确认最新待处理建议后，才把最终分类和优先级写入正式工单。
- 人工可用 `--category`、`--priority` 覆盖 AI 建议，AI 原始四字段仍保持不变。
- `reject-ai` 可拒绝建议，正式工单保持不变。
- 建议状态、人工最终结果、分析时间和处理时间分开保存，`show` 可查看完整历史。
- 已有阶段 3 数据库首次运行时会自动迁移，保留原有四项建议内容。

## 文件说明

| 文件 | 作用 |
| --- | --- |
| `app.py` | CLI 入口，包含基础工单、AI 分析、人工确认和拒绝命令。 |
| `database.py` | 使用标准库 `sqlite3` 建表、迁移建议表并执行参数化 SQL 和确认事务。 |
| `ticket_service.py` | 工单规则、建议保存、人工确认和拒绝等业务逻辑。 |
| `ai_service.py` | 构造安全 Prompt、调用真实模型并严格校验返回结果。 |
| `main.py` | 推荐启动入口，兼容全部命令。 |
| `tests/test_ticket_system.py` | 阶段 2 自动化测试，使用独立临时数据库。 |
| `tests/test_ai_service.py` | AI JSON、枚举、提示注入、建议隔离和失败降级测试。 |
| `tests/test_ai_confirmation.py` | 人工确认、人工覆盖、拒绝、重复处理保护和旧库迁移测试。 |
| `requirements.txt` | 测试环境所需的 pytest 依赖。 |
| `.gitignore` | 排除本地数据库、Python 缓存和虚拟环境。 |

程序首次运行时会在项目目录生成 `tickets.db`。该文件是本地运行数据，不提交到 Git。

## 环境要求

- Python 3.10 或更高版本。
- 基础工单和 SQLite 访问只使用 Python 标准库。
- AI 调用需要 openai，运行自动化测试需要 pytest；均列在 `requirements.txt` 中。

安装测试依赖：

```powershell
python -m pip install -r requirements.txt
```

## 快速开始

初始化示例数据：

```powershell
python app.py init
```

查看全部工单：

```powershell
python app.py list
```

创建工单：

```powershell
python app.py create --title "新员工无法登录邮箱" --description "入职后邮箱提示账号不存在" --submitter "张三" --category "账号权限" --priority P1
```

查看详情并修改状态：

```powershell
python app.py show 6
python app.py status 6 IN_PROGRESS
```

组合筛选：

```powershell
python app.py list --status IN_PROGRESS --category "账号权限"
```

## 配置并使用 AI 分析

先在当前 PowerShell 会话设置环境变量。不要把真实密钥写进代码或提交到 Git：

```powershell
$env:AI_API_KEY="你的 API Key"
$env:AI_MODEL="你的模型名称"
```

使用 OpenAI 兼容服务时，再设置它提供的基础地址；使用 OpenAI 官方接口时可以不设置：

```powershell
$env:AI_BASE_URL="https://你的兼容服务地址/v1"
```

分析指定工单：

```powershell
python main.py analyze 1
python main.py show 1
```

`analyze` 会保存并显示建议，但不会覆盖工单原有的正式分类和优先级。

人工确认并采用 AI 建议：

```powershell
python main.py confirm-ai 1
python main.py show 1
```

人工修正后再确认：

```powershell
python main.py confirm-ai 1 --category "其他" --priority P2
```

拒绝最新待处理建议：

```powershell
python main.py reject-ai 1
```

AI 调用数据流：

1. 根据 ID 从 SQLite 读取工单标题和描述。
2. 将标题和描述作为不可信 JSON 数据发送给模型。
3. 模型尝试返回 `category`、`priority`、`summary`、`reason` JSON。
4. 程序重新解析并检查全部字段和枚举值。
5. 只有校验成功的四项业务建议才保存到 `ai_suggestions`，状态为 `PENDING`，正式工单保持不变。
6. 人工确认后，程序在一个数据库事务中保存人工最终值并更新正式工单；拒绝时只记录拒绝状态。

任何配置、网络、认证、超时或响应校验错误都会在第 4 步之前或之中终止，只显示“AI分析不可用”，不会保存半成品建议。

可选值：

- 状态：`OPEN`、`IN_PROGRESS`、`RESOLVED`、`CLOSED`
- 优先级：`P0`、`P1`、`P2`、`P3`
- 分类：`账号权限`、`软件故障`、`网络问题`、`硬件设备`、`其他`

## 阶段 1 验证结果

已实际验证以下流程：初始化 5 条示例工单、创建新工单、查询列表和详情、顺序修改状态、双条件组合筛选、重复创建拒绝、非法状态跳转拒绝，以及程序重启后的数据持久化。

## 自动化测试

运行全部测试：

```powershell
python -m pytest -v
```

测试使用 pytest 提供的临时目录，每个测试都有独立 SQLite 数据库，不会修改正式的 `tickets.db`，也没有通过固定返回值绕过真实业务逻辑。

阶段 4 完成时的实际运行结果：`26 passed`。

## 当前范围

当前已完成阶段 1、阶段 2、阶段 3 和阶段 4。系统保持纯命令行实现，未增加前端、登录、权限或消息通知。
