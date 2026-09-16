import sqlite3
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
from src.config import settings

TABLE_NAME = "support_tickets"

CREATE_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
    ticket_id TEXT PRIMARY KEY,
    created_at TIMESTAMP NOT NULL,
    category TEXT NOT NULL,
    priority TEXT NOT NULL,
    status TEXT NOT NULL,
    response_time_hrs REAL NOT NULL,
    resolution_time_hrs REAL,
    agent_id TEXT NOT NULL,
    customer_rating INTEGER,
    issue_summary TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tickets_status ON {TABLE_NAME}(status);
CREATE INDEX IF NOT EXISTS idx_tickets_priority ON {TABLE_NAME}(priority);
CREATE INDEX IF NOT EXISTS idx_tickets_category ON {TABLE_NAME}(category);
CREATE INDEX IF NOT EXISTS idx_tickets_agent_id ON {TABLE_NAME}(agent_id);
CREATE INDEX IF NOT EXISTS idx_tickets_created_at ON {TABLE_NAME}(created_at);
"""

# Regex pattern to ensure queries are strictly read-only
FORBIDDEN_SQL_PATTERN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|REPLACE|ATTACH|DETACH|PRAGMA|GRANT|REVOKE)\b",
    re.IGNORECASE
)


class DatabaseManager:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or settings.DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_database()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def init_database(self, force_reload: bool = False) -> None:
        """Initialize database schema and ingest CSV if table is empty or forced."""
        with self.get_connection() as conn:
            conn.executescript(CREATE_TABLE_SQL)
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}")
            count = cursor.fetchone()[0]

            if count == 0 or force_reload:
                if force_reload and count > 0:
                    cursor.execute(f"DELETE FROM {TABLE_NAME}")
                self._ingest_csv(conn)

    def _ingest_csv(self, conn: sqlite3.Connection) -> int:
        """Ingests support_tickets.csv into SQLite with cleaned types."""
        if not settings.CSV_PATH.exists():
            raise FileNotFoundError(f"CSV file not found at {settings.CSV_PATH}")

        df = pd.read_csv(settings.CSV_PATH)

        # Standardize column names
        df.columns = [col.strip() for col in df.columns]

        # Clean types
        df["created_at"] = pd.to_datetime(df["created_at"]).dt.strftime("%Y-%m-%d %H:%M:%S")
        df["response_time_hrs"] = pd.to_numeric(df["response_time_hrs"], errors="coerce")
        df["resolution_time_hrs"] = pd.to_numeric(df["resolution_time_hrs"], errors="coerce")
        df["customer_rating"] = pd.to_numeric(df["customer_rating"], errors="coerce")
        
        # Replace NaN with None for SQLite NULL compatibility
        df = df.where(pd.notnull(df), None)

        # Write to SQLite
        df.to_sql(TABLE_NAME, conn, if_exists="append", index=False)
        conn.commit()
        return len(df)

    def execute_query(self, query: str, params: Optional[Tuple[Any, ...]] = None) -> Dict[str, Any]:
        """Safely executes a read-only SQL query with guardrails."""
        clean_query = query.strip().rstrip(";")

        # Security check 1: Disallow multi-statements
        if ";" in clean_query:
            raise ValueError("Multiple SQL statements are not permitted.")

        # Security check 2: Strict read-only statement check
        if FORBIDDEN_SQL_PATTERN.search(clean_query):
            raise ValueError("Only read-only queries (SELECT) are permitted.")

        if not (clean_query.upper().startswith("SELECT") or clean_query.upper().startswith("WITH")):
            raise ValueError("Query must begin with SELECT or WITH.")

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(clean_query, params or ())
            rows = cursor.fetchall()
            columns = [col[0] for col in cursor.description] if cursor.description else []
            data = [dict(row) for row in rows]

            return {
                "columns": columns,
                "rows": data,
                "row_count": len(data),
                "sql": clean_query
            }

    def get_schema_context(self) -> str:
        """Returns concise DDL and column descriptions for LLM prompting."""
        return f"""
Table Name: {TABLE_NAME}
Schema:
- ticket_id (TEXT, PRIMARY KEY): Unique ticket identifier (e.g. 'TKT-001')
- created_at (TIMESTAMP): Ticket creation date and time (format: 'YYYY-MM-DD HH:MM:SS')
- category (TEXT): Ticket domain ('Billing', 'Technical', 'General')
- priority (TEXT): Urgency level ('Low', 'Medium', 'High', 'Critical')
- status (TEXT): Current ticket state ('Open', 'Resolved', 'Escalated')
- response_time_hrs (REAL): Hours elapsed until first agent response
- resolution_time_hrs (REAL, NULLABLE): Hours from creation to resolution (NULL if status is 'Open' or 'Escalated')
- agent_id (TEXT): Assigned support agent (e.g. 'AGT-01' to 'AGT-12')
- customer_rating (INTEGER, NULLABLE): Post-resolution rating from 1 to 5 (NULL if unresolved)
- issue_summary (TEXT): Brief descriptive summary of the customer's problem

Important Data Properties:
- The dataset records span from January 2024 through March 2024.
- If a query refers to "this month", it refers to the latest month in the dataset: March 2024 (strftime('%Y-%m', created_at) = '2024-03').
- Tickets are considered unresolved when status IN ('Open', 'Escalated') or status != 'Resolved'.
- When calculating averages on customer_rating or resolution_time_hrs, SQLite automatically skips NULL values.
"""

    def get_stats(self) -> Dict[str, Any]:
        """Returns quick overview stats about the loaded dataset."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) as total FROM {TABLE_NAME}")
            total = cursor.fetchone()["total"]

            cursor.execute(f"SELECT COUNT(*) as open_count FROM {TABLE_NAME} WHERE status = 'Open'")
            open_count = cursor.fetchone()["open_count"]

            cursor.execute(f"SELECT COUNT(*) as resolved_count FROM {TABLE_NAME} WHERE status = 'Resolved'")
            resolved_count = cursor.fetchone()["resolved_count"]

            cursor.execute(f"SELECT COUNT(*) as escalated_count FROM {TABLE_NAME} WHERE status = 'Escalated'")
            escalated_count = cursor.fetchone()["escalated_count"]

            cursor.execute(f"SELECT MIN(created_at) as min_date, MAX(created_at) as max_date FROM {TABLE_NAME}")
            date_row = cursor.fetchone()

            cursor.execute(f"SELECT AVG(customer_rating) as avg_rating FROM {TABLE_NAME} WHERE customer_rating IS NOT NULL")
            avg_rating = cursor.fetchone()["avg_rating"]

            cursor.execute(f"SELECT AVG(resolution_time_hrs) as avg_resolution FROM {TABLE_NAME} WHERE resolution_time_hrs IS NOT NULL")
            avg_resolution = cursor.fetchone()["avg_resolution"]

            return {
                "total_tickets": total,
                "open_tickets": open_count,
                "resolved_tickets": resolved_count,
                "escalated_tickets": escalated_count,
                "unresolved_tickets": open_count + escalated_count,
                "date_range": {
                    "start": date_row["min_date"],
                    "end": date_row["max_date"]
                },
                "avg_customer_rating": round(avg_rating, 2) if avg_rating else None,
                "avg_resolution_time_hrs": round(avg_resolution, 2) if avg_resolution else None,
            }

db = DatabaseManager()
