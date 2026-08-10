# 智能工单协同系统

这是面试 AI Coding 题目的阶段性实现。本仓库当前完成 **阶段 1：最小工单系统**，使用 Python 命令行和 SQLite 本地数据库，不包含 Web 前端、AI 分析或第三方框架。

## 阶段 1 已完成功能

- 创建工单并持久化到 SQLite。
- 查看工单列表和单条工单详情。
- 按状态、分类、优先级、提交人进行任意组合筛选。
- 按 `OPEN → IN_PROGRESS → RESOLVED → CLOSED` 顺序修改状态。
- 检测标题和描述完全相同的重复工单，并提示已有工单 ID。
- 使用幂等 `init` 命令初始化 5 条覆盖不同状态、分类和优先级的示例工单。

## 文件说明

| 文件 | 作用 |
| --- | --- |
| `app.py` | CLI 入口，定义 `init`、`create`、`list`、`show`、`status` 命令。 |
| `database.py` | 使用标准库 `sqlite3` 建表并执行参数化 SQL。 |
| `ticket_service.py` | 输入校验、重复检测、组合筛选和状态流转等业务规则。 |
| `.gitignore` | 排除本地数据库、Python 缓存和虚拟环境。 |

程序首次运行时会在项目目录生成 `tickets.db`。该文件是本地运行数据，不提交到 Git。

## 环境要求

- Python 3.10 或更高版本。
- 无第三方依赖。

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

可选值：

- 状态：`OPEN`、`IN_PROGRESS`、`RESOLVED`、`CLOSED`
- 优先级：`P0`、`P1`、`P2`、`P3`
- 分类：`账号权限`、`软件故障`、`网络问题`、`硬件设备`、`其他`

## 阶段 1 验证结果

已实际验证以下流程：初始化 5 条示例工单、创建新工单、查询列表和详情、顺序修改状态、双条件组合筛选、重复创建拒绝、非法状态跳转拒绝，以及程序重启后的数据持久化。

## 当前范围

当前仅实现阶段 1。AI 分析、自动化测试和人工确认闭环将在后续阶段分别加入。
