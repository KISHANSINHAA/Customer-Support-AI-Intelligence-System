import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from src.database import db
from src.llm_engine import llm_engine


class QueryRequest(BaseModel):
    query: str = Field(..., json_schema_extra={"example": "How many tickets are currently open?"})


class QueryResponse(BaseModel):
    query: str
    sql: str
    row_count: int
    columns: List[str]
    results: List[Dict[str, Any]]
    summary: str
    execution_time_ms: float
    provider: str
    success: bool = True
    error_message: Optional[str] = None


class QueryService:
    def __init__(self):
        self.db = db
        self.llm = llm_engine

    def execute_nl_query(self, user_query: str) -> QueryResponse:
        start_time = time.perf_counter()
        provider_name = self.llm.get_provider_name()

        try:
            # 1. Translate NL to SQL
            sql = self.llm.generate_sql(user_query)

            # 2. Execute SQL with guardrails
            db_res = self.db.execute_query(sql)

            # 3. Synthesize natural language answer
            summary = self.llm.synthesize_answer(user_query, sql, db_res["rows"])

            elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

            return QueryResponse(
                query=user_query,
                sql=sql,
                row_count=db_res["row_count"],
                columns=db_res["columns"],
                results=db_res["rows"],
                summary=summary,
                execution_time_ms=elapsed_ms,
                provider=provider_name,
                success=True,
                error_message=None
            )

        except Exception as e:
            elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
            return QueryResponse(
                query=user_query,
                sql="",
                row_count=0,
                columns=[],
                results=[],
                summary="An error occurred while processing your query.",
                execution_time_ms=elapsed_ms,
                provider=provider_name,
                success=False,
                error_message=str(e)
            )


query_service = QueryService()
