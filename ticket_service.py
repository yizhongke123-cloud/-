"""工单业务规则。"""

from datetime import datetime
from pathlib import Path
import sqlite3
from typing import TYPE_CHECKING

import database

if TYPE_CHECKING:
    from ai_service import AnalysisResult


STATUS_FLOW = {
    "OPEN": "IN_PROGRESS",
    "IN_PROGRESS": "RESOLVED",
    "RESOLVED": "CLOSED",
}


class TicketError(Exception):
    """可直接展示给命令行用户的业务错误。"""


class DuplicateTicketError(TicketError):
    def __init__(self, existing_id: int):
        self.existing_id = existing_id
        super().__init__(f"重复工单，已有工单 ID：{existing_id}")


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _text(value: str, field_name: str, max_length: int) -> str:
    normalized = value.strip()
    if not normalized:
        raise TicketError(f"{field_name}不能为空")
    if len(normalized) > max_length:
        raise TicketError(f"{field_name}不能超过 {max_length} 个字符")
    return normalized


def _enum(value: str, field_name: str, allowed: tuple[str, ...]) -> str:
    if value not in allowed:
        raise TicketError(
            f"{field_name}非法：{value}；可选值为 {', '.join(allowed)}"
        )
    return value


def create_ticket(
    db_path: str | Path,
    *,
    title: str,
    description: str,
    submitter: str,
    category: str,
    priority: str,
    status: str = "OPEN",
) -> int:
    title = _text(title, "标题", 100)
    description = _text(description, "描述", 2000)
    submitter = _text(submitter, "提交人", 50)
    category = _enum(category, "分类", database.CATEGORIES)
    priority = _enum(priority, "优先级", database.PRIORITIES)
    status = _enum(status, "状态", database.STATUSES)

    with database.connect(db_path) as connection:
        existing = database.find_by_content(connection, title, description)
        if existing is not None:
            raise DuplicateTicketError(existing["id"])

        try:
            return database.insert_ticket(
                connection,
                title=title,
                description=description,
                submitter=submitter,
                category=category,
                priority=priority,
                status=status,
                timestamp=_now(),
            )
        except sqlite3.IntegrityError:
            existing = database.find_by_content(connection, title, description)
            if existing is not None:
                raise DuplicateTicketError(existing["id"]) from None
            raise


def list_tickets(
    db_path: str | Path,
    *,
    status: str | None = None,
    category: str | None = None,
    priority: str | None = None,
    submitter: str | None = None,
) -> list[sqlite3.Row]:
    filters: dict[str, str] = {}
    if status is not None:
        filters["status"] = _enum(status, "状态", database.STATUSES)
    if category is not None:
        filters["category"] = _enum(category, "分类", database.CATEGORIES)
    if priority is not None:
        filters["priority"] = _enum(priority, "优先级", database.PRIORITIES)
    if submitter is not None:
        filters["submitter"] = _text(submitter, "提交人", 50)

    with database.connect(db_path) as connection:
        return database.fetch_tickets(connection, filters)


def get_ticket(db_path: str | Path, ticket_id: int) -> sqlite3.Row:
    with database.connect(db_path) as connection:
        ticket = database.fetch_ticket(connection, ticket_id)
    if ticket is None:
        raise TicketError(f"工单不存在：{ticket_id}")
    return ticket


def change_status(db_path: str | Path, ticket_id: int, new_status: str) -> None:
    new_status = _enum(new_status, "状态", database.STATUSES)

    with database.connect(db_path) as connection:
        ticket = database.fetch_ticket(connection, ticket_id)
        if ticket is None:
            raise TicketError(f"工单不存在：{ticket_id}")

        current_status = ticket["status"]
        expected_status = STATUS_FLOW.get(current_status)
        if expected_status is None:
            raise TicketError("CLOSED 状态的工单不能继续流转")
        if new_status != expected_status:
            raise TicketError(
                f"非法状态流转：{current_status} 只能修改为 {expected_status}"
            )

        if not database.update_status(
            connection, ticket_id, current_status, new_status, _now()
        ):
            raise TicketError("工单状态已被其他操作修改，请重新查询后再试")


def save_ai_suggestion(
    db_path: str | Path, ticket_id: int, result: "AnalysisResult"
) -> int:
    """保存建议；此函数不会更新工单的正式分类或优先级。"""
    category = _enum(result.category, "AI 建议分类", database.CATEGORIES)
    priority = _enum(result.priority, "AI 建议优先级", database.PRIORITIES)
    summary = _text(result.summary, "AI 建议摘要", 200)
    reason = _text(result.reason, "AI 建议理由", 1000)
    model = _text(result.model, "AI 模型", 200)
    raw_response = _text(result.raw_response, "AI 原始响应", 5000)

    with database.connect(db_path) as connection:
        if database.fetch_ticket(connection, ticket_id) is None:
            raise TicketError(f"工单不存在：{ticket_id}")
        return database.insert_ai_suggestion(
            connection,
            ticket_id=ticket_id,
            category=category,
            priority=priority,
            summary=summary,
            reason=reason,
            model=model,
            raw_response=raw_response,
            timestamp=_now(),
        )


def list_ai_suggestions(
    db_path: str | Path, ticket_id: int
) -> list[sqlite3.Row]:
    with database.connect(db_path) as connection:
        return database.fetch_ai_suggestions(connection, ticket_id)


SAMPLE_TICKETS = (
    {
        "title": "申请新员工 VPN 权限",
        "description": "新员工需要远程访问公司内网，请开通 VPN。",
        "submitter": "王敏",
        "category": "账号权限",
        "priority": "P2",
        "status": "OPEN",
    },
    {
        "title": "财务软件启动后闪退",
        "description": "升级系统后，财务软件打开约十秒即自动退出。",
        "submitter": "李娜",
        "category": "软件故障",
        "priority": "P1",
        "status": "IN_PROGRESS",
    },
    {
        "title": "三楼无线网络无法连接",
        "description": "三楼办公区所有员工均无法连接无线网络。",
        "submitter": "赵强",
        "category": "网络问题",
        "priority": "P1",
        "status": "RESOLVED",
    },
    {
        "title": "笔记本电脑无法开机",
        "description": "按下电源键无任何反应，电源指示灯不亮。",
        "submitter": "陈晨",
        "category": "硬件设备",
        "priority": "P0",
        "status": "CLOSED",
    },
    {
        "title": "会议室空调温度过高",
        "description": "二号会议室空调制冷效果较差，请安排检查。",
        "submitter": "周洁",
        "category": "其他",
        "priority": "P3",
        "status": "OPEN",
    },
)


def init_samples(db_path: str | Path) -> tuple[list[int], list[int]]:
    created_ids: list[int] = []
    existing_ids: list[int] = []

    for sample in SAMPLE_TICKETS:
        try:
            created_ids.append(create_ticket(db_path, **sample))
        except DuplicateTicketError as error:
            existing_ids.append(error.existing_id)

    return created_ids, existing_ids
