"""智能工单协同系统的命令行入口。"""

import argparse
from pathlib import Path

import database
import ticket_service


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="智能工单协同系统")
    parser.add_argument(
        "--db",
        default=str(database.DEFAULT_DB_PATH),
        help="SQLite 数据库路径（默认：tickets.db）",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init", help="初始化 5 条示例工单")

    create_parser = subparsers.add_parser("create", help="创建工单")
    create_parser.add_argument("--title", required=True, help="工单标题")
    create_parser.add_argument("--description", required=True, help="工单描述")
    create_parser.add_argument("--submitter", required=True, help="提交人")
    create_parser.add_argument(
        "--category", required=True, choices=database.CATEGORIES, help="分类"
    )
    create_parser.add_argument(
        "--priority", required=True, choices=database.PRIORITIES, help="优先级"
    )

    list_parser = subparsers.add_parser("list", help="列出或筛选工单")
    list_parser.add_argument("--status", choices=database.STATUSES)
    list_parser.add_argument("--category", choices=database.CATEGORIES)
    list_parser.add_argument("--priority", choices=database.PRIORITIES)
    list_parser.add_argument("--submitter")

    show_parser = subparsers.add_parser("show", help="查看工单详情")
    show_parser.add_argument("ticket_id", type=int, metavar="ID")

    status_parser = subparsers.add_parser("status", help="修改工单状态")
    status_parser.add_argument("ticket_id", type=int, metavar="ID")
    status_parser.add_argument("new_status", choices=database.STATUSES)

    return parser


def print_ticket_line(ticket) -> None:
    print(
        f"[{ticket['id']}] {ticket['priority']} {ticket['status']} | "
        f"{ticket['category']} | {ticket['title']} | 提交人：{ticket['submitter']}"
    )


def run_command(args: argparse.Namespace) -> None:
    db_path = Path(args.db)
    database.init_db(db_path)

    if args.command == "init":
        created_ids, existing_ids = ticket_service.init_samples(db_path)
        print(
            f"初始化完成：新建 {len(created_ids)} 条，已有 {len(existing_ids)} 条；"
            f"数据库：{db_path.resolve()}"
        )
        return

    if args.command == "create":
        ticket_id = ticket_service.create_ticket(
            db_path,
            title=args.title,
            description=args.description,
            submitter=args.submitter,
            category=args.category,
            priority=args.priority,
        )
        print(f"工单创建成功，ID：{ticket_id}")
        return

    if args.command == "list":
        tickets = ticket_service.list_tickets(
            db_path,
            status=args.status,
            category=args.category,
            priority=args.priority,
            submitter=args.submitter,
        )
        if not tickets:
            print("没有符合条件的工单。")
            return
        for ticket in tickets:
            print_ticket_line(ticket)
        print(f"共 {len(tickets)} 条工单。")
        return

    if args.command == "show":
        ticket = ticket_service.get_ticket(db_path, args.ticket_id)
        print(f"工单 ID：{ticket['id']}")
        print(f"标题：{ticket['title']}")
        print(f"描述：{ticket['description']}")
        print(f"提交人：{ticket['submitter']}")
        print(f"分类：{ticket['category']}")
        print(f"优先级：{ticket['priority']}")
        print(f"状态：{ticket['status']}")
        print(f"创建时间：{ticket['created_at']}")
        print(f"更新时间：{ticket['updated_at']}")
        return

    if args.command == "status":
        ticket_service.change_status(db_path, args.ticket_id, args.new_status)
        print(f"工单 {args.ticket_id} 状态已修改为 {args.new_status}")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        run_command(args)
    except ticket_service.TicketError as error:
        print(f"错误：{error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
