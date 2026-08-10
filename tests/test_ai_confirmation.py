"""阶段 4：AI 建议人工确认、拒绝和追溯测试。"""

from pathlib import Path
import sqlite3

import pytest

import ai_service
import database
import ticket_service


@pytest.fixture
def ticket_with_suggestion(tmp_path: Path) -> tuple[Path, int]:
    db_path = tmp_path / "confirmation.db"
    database.init_db(db_path)
    ticket_id = ticket_service.create_ticket(
        db_path,
        title="办公区无法上网",
        description="三楼多台电脑无法访问网络",
        submitter="张三",
        category="其他",
        priority="P3",
    )
    result = ai_service.AnalysisResult(
        category="网络问题",
        priority="P1",
        summary="三楼办公区网络中断",
        reason="多台电脑同时无法访问网络",
        model="test-model",
        raw_response="只用于测试，不应存入数据库",
    )
    ticket_service.save_ai_suggestion(db_path, ticket_id, result)
    return db_path, ticket_id


def test_confirm_applies_suggestion_and_preserves_ai_original(
    ticket_with_suggestion: tuple[Path, int],
) -> None:
    db_path, ticket_id = ticket_with_suggestion

    confirmed = ticket_service.confirm_ai_suggestion(db_path, ticket_id)
    ticket = ticket_service.get_ticket(db_path, ticket_id)

    assert ticket["category"] == "网络问题"
    assert ticket["priority"] == "P1"
    assert confirmed["ai_category"] == "网络问题"
    assert confirmed["ai_priority"] == "P1"
    assert confirmed["ai_summary"] == "三楼办公区网络中断"
    assert confirmed["ai_reason"] == "多台电脑同时无法访问网络"
    assert confirmed["decision"] == "CONFIRMED"
    assert confirmed["final_category"] == "网络问题"
    assert confirmed["final_priority"] == "P1"
    assert confirmed["decided_at"] is not None
    assert "model" not in confirmed.keys()
    assert "raw_response" not in confirmed.keys()


def test_manual_final_values_are_saved_separately(
    ticket_with_suggestion: tuple[Path, int],
) -> None:
    db_path, ticket_id = ticket_with_suggestion

    confirmed = ticket_service.confirm_ai_suggestion(
        db_path,
        ticket_id,
        final_category="其他",
        final_priority="P2",
    )

    assert confirmed["ai_category"] == "网络问题"
    assert confirmed["ai_priority"] == "P1"
    assert confirmed["final_category"] == "其他"
    assert confirmed["final_priority"] == "P2"
    ticket = ticket_service.get_ticket(db_path, ticket_id)
    assert ticket["category"] == "其他"
    assert ticket["priority"] == "P2"


def test_reject_preserves_official_ticket(
    ticket_with_suggestion: tuple[Path, int],
) -> None:
    db_path, ticket_id = ticket_with_suggestion

    rejected = ticket_service.reject_ai_suggestion(db_path, ticket_id)
    ticket = ticket_service.get_ticket(db_path, ticket_id)

    assert rejected["decision"] == "REJECTED"
    assert rejected["ai_category"] == "网络问题"
    assert rejected["final_category"] is None
    assert rejected["decided_at"] is not None
    assert ticket["category"] == "其他"
    assert ticket["priority"] == "P3"


def test_processed_suggestion_cannot_be_confirmed_twice(
    ticket_with_suggestion: tuple[Path, int],
) -> None:
    db_path, ticket_id = ticket_with_suggestion
    ticket_service.confirm_ai_suggestion(db_path, ticket_id)

    with pytest.raises(ticket_service.TicketError, match="没有待确认"):
        ticket_service.confirm_ai_suggestion(db_path, ticket_id)


def test_invalid_manual_value_is_rejected_without_partial_update(
    ticket_with_suggestion: tuple[Path, int],
) -> None:
    db_path, ticket_id = ticket_with_suggestion

    with pytest.raises(ticket_service.TicketError, match="人工最终分类非法"):
        ticket_service.confirm_ai_suggestion(
            db_path, ticket_id, final_category="错误分类"
        )

    ticket = ticket_service.get_ticket(db_path, ticket_id)
    suggestion = ticket_service.list_ai_suggestions(db_path, ticket_id)[0]
    assert ticket["category"] == "其他"
    assert suggestion["decision"] == "PENDING"


def test_stage3_database_is_migrated_without_losing_suggestion(tmp_path: Path) -> None:
    db_path = tmp_path / "stage3.db"
    with sqlite3.connect(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE tickets (
                id INTEGER PRIMARY KEY,
                title TEXT, description TEXT, submitter TEXT,
                category TEXT, priority TEXT, status TEXT,
                created_at TEXT, updated_at TEXT
            );
            INSERT INTO tickets VALUES (
                1, '旧工单', '旧描述', '张三', '其他', 'P3', 'OPEN', 't1', 't1'
            );
            CREATE TABLE ai_suggestions (
                id INTEGER PRIMARY KEY,
                ticket_id INTEGER,
                category TEXT,
                priority TEXT,
                summary TEXT,
                reason TEXT,
                model TEXT,
                raw_response TEXT,
                created_at TEXT
            );
            INSERT INTO ai_suggestions VALUES (
                7, 1, '网络问题', 'P1', '旧摘要', '旧理由',
                'old-model', '{"old":true}', 't2'
            );
            """
        )

    database.init_db(db_path)
    suggestions = ticket_service.list_ai_suggestions(db_path, 1)

    assert len(suggestions) == 1
    assert suggestions[0]["id"] == 7
    assert suggestions[0]["ai_category"] == "网络问题"
    assert suggestions[0]["ai_summary"] == "旧摘要"
    assert suggestions[0]["decision"] == "PENDING"
    assert "model" not in suggestions[0].keys()
    assert "raw_response" not in suggestions[0].keys()
