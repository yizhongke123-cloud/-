"""阶段 2：工单系统业务规则和持久化测试。"""

from pathlib import Path
import os
import subprocess
import sys

import pytest

import database
import ticket_service


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "test_tickets.db"
    database.init_db(path)
    return path


def create_example(db_path: Path, **overrides) -> int:
    values = {
        "title": "邮箱无法登录",
        "description": "输入正确密码后仍提示登录失败",
        "submitter": "张三",
        "category": "账号权限",
        "priority": "P1",
    }
    values.update(overrides)
    return ticket_service.create_ticket(db_path, **values)


def test_create_ticket_successfully(db_path: Path) -> None:
    ticket_id = create_example(db_path)

    ticket = ticket_service.get_ticket(db_path, ticket_id)
    assert ticket["title"] == "邮箱无法登录"
    assert ticket["priority"] == "P1"
    assert ticket["status"] == "OPEN"


def test_empty_title_is_rejected(db_path: Path) -> None:
    with pytest.raises(ticket_service.TicketError, match="标题不能为空"):
        create_example(db_path, title="   ")


def test_invalid_priority_is_rejected(db_path: Path) -> None:
    with pytest.raises(ticket_service.TicketError, match="优先级非法"):
        create_example(db_path, priority="P9")


def test_invalid_status_is_rejected(db_path: Path) -> None:
    ticket_id = create_example(db_path)

    with pytest.raises(ticket_service.TicketError, match="状态非法"):
        ticket_service.change_status(db_path, ticket_id, "UNKNOWN")


def test_duplicate_ticket_returns_existing_id(db_path: Path) -> None:
    first_id = create_example(db_path)

    with pytest.raises(ticket_service.DuplicateTicketError) as caught:
        create_example(db_path, submitter="李四", priority="P3")

    assert caught.value.existing_id == first_id
    assert f"已有工单 ID：{first_id}" in str(caught.value)


def test_normal_status_flow(db_path: Path) -> None:
    ticket_id = create_example(db_path)

    for expected_status in ("IN_PROGRESS", "RESOLVED", "CLOSED"):
        ticket_service.change_status(db_path, ticket_id, expected_status)
        assert ticket_service.get_ticket(db_path, ticket_id)["status"] == expected_status


def test_illegal_status_flow_is_rejected(db_path: Path) -> None:
    ticket_id = create_example(db_path)

    with pytest.raises(ticket_service.TicketError, match="OPEN 只能修改为 IN_PROGRESS"):
        ticket_service.change_status(db_path, ticket_id, "RESOLVED")

    assert ticket_service.get_ticket(db_path, ticket_id)["status"] == "OPEN"


def test_two_filters_are_combined(db_path: Path) -> None:
    expected_id = create_example(db_path)
    ticket_service.change_status(db_path, expected_id, "IN_PROGRESS")
    create_example(
        db_path,
        title="办公软件闪退",
        description="保存文件时软件自动退出",
        category="软件故障",
        priority="P2",
    )

    tickets = ticket_service.list_tickets(
        db_path, status="IN_PROGRESS", category="账号权限"
    )

    assert [ticket["id"] for ticket in tickets] == [expected_id]


def test_data_persists_across_connections(db_path: Path) -> None:
    ticket_id = create_example(db_path)

    with database.connect(db_path) as new_connection:
        persisted = database.fetch_ticket(new_connection, ticket_id)

    assert persisted is not None
    assert persisted["description"] == "输入正确密码后仍提示登录失败"


def test_init_samples_is_idempotent(db_path: Path) -> None:
    first_created, first_existing = ticket_service.init_samples(db_path)
    second_created, second_existing = ticket_service.init_samples(db_path)

    assert len(first_created) == 5
    assert first_existing == []
    assert second_created == []
    assert sorted(second_existing) == sorted(first_created)
    assert len(ticket_service.list_tickets(db_path)) == 5


def test_cli_hides_database_traceback(tmp_path: Path) -> None:
    directory_instead_of_database = tmp_path / "not-a-database-file"
    directory_instead_of_database.mkdir()
    app_path = Path(__file__).parents[1] / "app.py"
    environment = os.environ.copy()
    environment["PYTHONIOENCODING"] = "utf-8"

    result = subprocess.run(
        [
            sys.executable,
            str(app_path),
            "--db",
            str(directory_instead_of_database),
            "list",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=environment,
        check=False,
    )

    assert result.returncode == 1
    assert "数据库操作失败" in result.stderr
    assert "Traceback" not in result.stderr
