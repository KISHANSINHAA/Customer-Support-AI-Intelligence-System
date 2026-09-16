import pytest
from src.database import db, TABLE_NAME

def test_database_initialization():
    stats = db.get_stats()
    assert stats["total_tickets"] == 500
    assert stats["open_tickets"] == 111
    assert stats["resolved_tickets"] == 327
    assert stats["escalated_tickets"] == 62
    assert stats["unresolved_tickets"] == 173

def test_safe_read_query():
    res = db.execute_query("SELECT COUNT(*) AS c FROM support_tickets WHERE priority = 'Critical'")
    assert res["row_count"] == 1
    assert res["rows"][0]["c"] == 55

def test_sql_guardrail_blocks_drop():
    with pytest.raises(ValueError, match="read-only"):
        db.execute_query("DROP TABLE support_tickets")

def test_sql_guardrail_blocks_delete():
    with pytest.raises(ValueError, match="read-only"):
        db.execute_query("DELETE FROM support_tickets WHERE ticket_id = 'TKT-001'")

def test_sql_guardrail_blocks_multistatements():
    with pytest.raises(ValueError, match="Multiple SQL statements"):
        db.execute_query("SELECT * FROM support_tickets; SELECT * FROM support_tickets")
