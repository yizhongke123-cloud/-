"""SQLite 数据访问层。"""

from pathlib import Path
import sqlite3


DEFAULT_DB_PATH = Path(__file__).with_name("tickets.db")

CATEGORIES = ("账号权限", "软件故障", "网络问题", "硬件设备", "其他")
PRIORITIES = ("P0", "P1", "P2", "P3")
STATUSES = ("OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED")


AI_SUGGESTIONS_SCHEMA = """
CREATE TABLE ai_suggestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL,
    ai_category TEXT NOT NULL
        CHECK (ai_category IN ('账号权限', '软件故障', '网络问题', '硬件设备', '其他')),
    ai_priority TEXT NOT NULL
        CHECK (ai_priority IN ('P0', 'P1', 'P2', 'P3')),
    ai_summary TEXT NOT NULL,
    ai_reason TEXT NOT NULL,
    decision TEXT NOT NULL DEFAULT 'PENDING'
        CHECK (decision IN ('PENDING', 'CONFIRMED', 'REJECTED')),
    final_category TEXT
        CHECK (final_category IS NULL OR final_category IN ('账号权限', '软件故障', '网络问题', '硬件设备', '其他')),
    final_priority TEXT
        CHECK (final_priority IS NULL OR final_priority IN ('P0', 'P1', 'P2', 'P3')),
    created_at TEXT NOT NULL,
    decided_at TEXT,
    FOREIGN KEY (ticket_id) REFERENCES tickets(id)
)
"""


def connect(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """连接数据库，并让查询结果可以按列名读取。"""
    connection = sqlite3.connect(str(db_path), timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db(db_path: str | Path = DEFAULT_DB_PATH) -> None:
    """创建工单表；重复调用不会清空已有数据。"""
    with connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                submitter TEXT NOT NULL,
                category TEXT NOT NULL
                    CHECK (category IN ('账号权限', '软件故障', '网络问题', '硬件设备', '其他')),
                priority TEXT NOT NULL
                    CHECK (priority IN ('P0', 'P1', 'P2', 'P3')),
                status TEXT NOT NULL
                    CHECK (status IN ('OPEN', 'IN_PROGRESS', 'RESOLVED', 'CLOSED')),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE (title, description)
            )
            """
        )
        _init_ai_suggestions(connection)


def _init_ai_suggestions(connection: sqlite3.Connection) -> None:
    """创建阶段 4 建议表，并无损迁移阶段 3 的建议内容。"""
    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(ai_suggestions)")
    }
    if not columns:
        connection.execute(AI_SUGGESTIONS_SCHEMA)
        return
    if "ai_category" in columns:
        return

    connection.execute("ALTER TABLE ai_suggestions RENAME TO ai_suggestions_stage3")
    connection.execute(AI_SUGGESTIONS_SCHEMA)
    connection.execute(
        """
        INSERT INTO ai_suggestions (
            id, ticket_id, ai_category, ai_priority, ai_summary, ai_reason,
            decision, created_at
        )
        SELECT id, ticket_id, category, priority, summary, reason,
               'PENDING', created_at
        FROM ai_suggestions_stage3
        """
    )
    connection.execute("DROP TABLE ai_suggestions_stage3")


def find_by_content(
    connection: sqlite3.Connection, title: str, description: str
) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM tickets WHERE title = ? AND description = ?",
        (title, description),
    ).fetchone()


def insert_ticket(
    connection: sqlite3.Connection,
    *,
    title: str,
    description: str,
    submitter: str,
    category: str,
    priority: str,
    status: str,
    timestamp: str,
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO tickets (
            title, description, submitter, category, priority, status,
            created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            title,
            description,
            submitter,
            category,
            priority,
            status,
            timestamp,
            timestamp,
        ),
    )
    return int(cursor.lastrowid)


def fetch_ticket(
    connection: sqlite3.Connection, ticket_id: int
) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM tickets WHERE id = ?", (ticket_id,)
    ).fetchone()


def fetch_tickets(
    connection: sqlite3.Connection, filters: dict[str, str]
) -> list[sqlite3.Row]:
    allowed_columns = {"status", "category", "priority", "submitter"}
    clauses: list[str] = []
    values: list[str] = []

    for column, value in filters.items():
        if column not in allowed_columns:
            raise ValueError(f"不支持的筛选字段：{column}")
        clauses.append(f"{column} = ?")
        values.append(value)

    sql = "SELECT * FROM tickets"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY id"

    return list(connection.execute(sql, values).fetchall())


def update_status(
    connection: sqlite3.Connection,
    ticket_id: int,
    current_status: str,
    new_status: str,
    timestamp: str,
) -> bool:
    cursor = connection.execute(
        """
        UPDATE tickets
        SET status = ?, updated_at = ?
        WHERE id = ? AND status = ?
        """,
        (new_status, timestamp, ticket_id, current_status),
    )
    return cursor.rowcount == 1


def insert_ai_suggestion(
    connection: sqlite3.Connection,
    *,
    ticket_id: int,
    ai_category: str,
    ai_priority: str,
    ai_summary: str,
    ai_reason: str,
    timestamp: str,
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO ai_suggestions (
            ticket_id, ai_category, ai_priority, ai_summary, ai_reason,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            ticket_id,
            ai_category,
            ai_priority,
            ai_summary,
            ai_reason,
            timestamp,
        ),
    )
    return int(cursor.lastrowid)


def fetch_ai_suggestions(
    connection: sqlite3.Connection, ticket_id: int
) -> list[sqlite3.Row]:
    return list(
        connection.execute(
            """
            SELECT * FROM ai_suggestions
            WHERE ticket_id = ?
            ORDER BY id
            """,
            (ticket_id,),
        ).fetchall()
    )


def fetch_ai_suggestion(
    connection: sqlite3.Connection, suggestion_id: int
) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM ai_suggestions WHERE id = ?", (suggestion_id,)
    ).fetchone()


def fetch_latest_pending_ai_suggestion(
    connection: sqlite3.Connection, ticket_id: int
) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT * FROM ai_suggestions
        WHERE ticket_id = ? AND decision = 'PENDING'
        ORDER BY id DESC
        LIMIT 1
        """,
        (ticket_id,),
    ).fetchone()


def confirm_ai_suggestion(
    connection: sqlite3.Connection,
    *,
    suggestion_id: int,
    ticket_id: int,
    final_category: str,
    final_priority: str,
    timestamp: str,
) -> bool:
    """在同一事务中应用人工最终值，并把原始 AI 建议标记为已确认。"""
    cursor = connection.execute(
        """
        UPDATE ai_suggestions
        SET decision = 'CONFIRMED', final_category = ?, final_priority = ?,
            decided_at = ?
        WHERE id = ? AND ticket_id = ? AND decision = 'PENDING'
        """,
        (final_category, final_priority, timestamp, suggestion_id, ticket_id),
    )
    if cursor.rowcount != 1:
        return False
    connection.execute(
        """
        UPDATE tickets
        SET category = ?, priority = ?, updated_at = ?
        WHERE id = ?
        """,
        (final_category, final_priority, timestamp, ticket_id),
    )
    return True


def reject_ai_suggestion(
    connection: sqlite3.Connection,
    *,
    suggestion_id: int,
    ticket_id: int,
    timestamp: str,
) -> bool:
    cursor = connection.execute(
        """
        UPDATE ai_suggestions
        SET decision = 'REJECTED', decided_at = ?
        WHERE id = ? AND ticket_id = ? AND decision = 'PENDING'
        """,
        (timestamp, suggestion_id, ticket_id),
    )
    return cursor.rowcount == 1
