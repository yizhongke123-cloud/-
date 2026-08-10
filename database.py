"""SQLite 数据访问层。"""

from pathlib import Path
import sqlite3


DEFAULT_DB_PATH = Path(__file__).with_name("tickets.db")

CATEGORIES = ("账号权限", "软件故障", "网络问题", "硬件设备", "其他")
PRIORITIES = ("P0", "P1", "P2", "P3")
STATUSES = ("OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED")


def connect(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """连接数据库，并让查询结果可以按列名读取。"""
    connection = sqlite3.connect(str(db_path), timeout=5)
    connection.row_factory = sqlite3.Row
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
