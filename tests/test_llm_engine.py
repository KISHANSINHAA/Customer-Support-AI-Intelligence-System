import pytest
from src.llm_engine import llm_engine
from src.database import db

SAMPLE_QUERIES = [
    ("How many tickets are currently open?", 1),
    ("Which agent resolved the most tickets this month?", 1),
    ("Show me all Critical tickets not resolved within 12 hours.", 34),
    ("What is the average customer rating for Technical category tickets?", 1),
    ("Are there any anomalies in resolution times this week?", 6)
]

@pytest.mark.parametrize("query,expected_rows", SAMPLE_QUERIES)
def test_sample_queries_execution(query, expected_rows):
    sql = llm_engine.generate_sql(query)
    assert sql.strip().upper().startswith("SELECT")
    
    res = db.execute_query(sql)
    assert res["row_count"] == expected_rows
    
    summary = llm_engine.synthesize_answer(query, sql, res["rows"])
    assert len(summary) > 10

def test_query_1_open_tickets_count():
    sql = llm_engine.generate_sql("How many tickets are currently open?")
    res = db.execute_query(sql)
    assert res["rows"][0]["open_tickets_count"] == 111

def test_query_2_top_agent_this_month():
    sql = llm_engine.generate_sql("Which agent resolved the most tickets this month?")
    res = db.execute_query(sql)
    assert res["rows"][0]["agent_id"] == "AGT-01"
    assert res["rows"][0]["resolved_count"] == 16

def test_query_4_technical_avg_rating():
    sql = llm_engine.generate_sql("What is the average customer rating for Technical category tickets?")
    res = db.execute_query(sql)
    assert res["rows"][0]["avg_customer_rating"] == 3.74
