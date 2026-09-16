import time
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.config import settings
from src.database import db, TABLE_NAME
from src.anomaly_detector import anomaly_detector, AnomalySummary
from src.llm_engine import llm_engine
from src.query_service import query_service, QueryRequest, QueryResponse

app = FastAPI(
    title="Customer Support AI Intelligence System",
    description="End-to-End AI System for customer support ticket ingestion, natural language querying (Text-to-SQL), and operational anomaly detection.",
    version="1.0.0"
)

# Enable CORS for external frontend or evaluator tools
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static and templates
app.mount("/static", StaticFiles(directory=str(settings.STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(settings.TEMPLATES_DIR))

APP_START_TIME = time.time()


# ==============================================================================
# REST API Endpoints (Required Deliverables)
# ==============================================================================

@app.get("/health", tags=["System"])
def health_check() -> Dict[str, Any]:
    """Health check endpoint validating system status, database connectivity, and LLM readiness."""
    try:
        stats = db.get_stats()
        uptime_sec = round(time.time() - APP_START_TIME, 1)
        return {
            "status": "healthy",
            "service": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "uptime_seconds": uptime_sec,
            "database": {
                "connected": True,
                "table": TABLE_NAME,
                "total_tickets": stats["total_tickets"]
            },
            "llm_provider": llm_engine.get_provider_name()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")


@app.post("/query", response_model=QueryResponse, tags=["Query"])
def handle_nl_query(request: QueryRequest) -> QueryResponse:
    """Natural language query endpoint. Translates text to SQL, executes query safely, and summarizes answer."""
    if not request.query or not request.query.strip():
        raise HTTPException(status_code=400, detail="Query string cannot be empty.")
    
    return query_service.execute_nl_query(request.query)


@app.get("/anomalies", response_model=AnomalySummary, tags=["Anomalies"])
def get_anomalies(
    severity: Optional[str] = Query(None, description="Filter by severity: CRITICAL, HIGH, MEDIUM"),
    anomaly_type: Optional[str] = Query(None, description="Filter by type: RESOLUTION_TIME_OUTLIER, UNRESOLVED_URGENT_TICKET, etc."),
    start_date: Optional[str] = Query(None, description="Start date filter (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date filter (YYYY-MM-DD)"),
    limit: Optional[int] = Query(50, description="Max anomalies to return (default 50)")
) -> AnomalySummary:
    """Anomaly detection endpoint. Identifies resolution time outliers, stalled urgent tickets, SLA breaches, and quality gaps."""
    try:
        return anomaly_detector.detect_all_anomalies(
            severity_filter=severity,
            anomaly_type_filter=anomaly_type,
            start_date=start_date,
            end_date=end_date,
            limit=limit
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Anomaly detection failed: {str(e)}")


# ==============================================================================
# Operational Analytics & Data Endpoints
# ==============================================================================

@app.get("/analytics/summary", tags=["Analytics"])
def get_analytics_summary() -> Dict[str, Any]:
    """Returns aggregated operational KPIs, category distributions, priority breakdowns, and SLA metrics."""
    stats = db.get_stats()

    # Category breakdown
    cat_res = db.execute_query(
        f"SELECT category, COUNT(*) as count, ROUND(AVG(customer_rating), 2) as avg_rating FROM {TABLE_NAME} GROUP BY category"
    )
    # Priority breakdown
    pri_res = db.execute_query(
        f"SELECT priority, COUNT(*) as count FROM {TABLE_NAME} GROUP BY priority ORDER BY count DESC"
    )
    # Top agents
    agent_res = db.execute_query(
        f"""SELECT agent_id, 
                   COUNT(*) as total_handled, 
                   SUM(CASE WHEN status = 'Resolved' THEN 1 ELSE 0 END) as resolved_count,
                   ROUND(AVG(customer_rating), 2) as avg_rating 
            FROM {TABLE_NAME} 
            GROUP BY agent_id 
            ORDER BY resolved_count DESC 
            LIMIT 5"""
    )

    anomalies_summary = anomaly_detector.detect_all_anomalies(limit=10)

    return {
        "kpis": stats,
        "categories": cat_res["rows"],
        "priorities": pri_res["rows"],
        "top_agents": agent_res["rows"],
        "anomalies_count": anomalies_summary.total_anomalies,
        "anomalies_by_severity": anomalies_summary.by_severity
    }


@app.get("/tickets", tags=["Data"])
def list_tickets(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    priority: Optional[str] = None,
    category: Optional[str] = None
) -> Dict[str, Any]:
    """Paginated ticket exploration endpoint with optional filters."""
    where_clauses = []
    params: List[Any] = []

    if status:
        where_clauses.append("status = ?")
        params.append(status)
    if priority:
        where_clauses.append("priority = ?")
        params.append(priority)
    if category:
        where_clauses.append("category = ?")
        params.append(category)

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    offset = (page - 1) * page_size

    count_res = db.execute_query(f"SELECT COUNT(*) as total FROM {TABLE_NAME} {where_sql}", tuple(params))
    total_records = count_res["rows"][0]["total"]

    data_query = f"SELECT * FROM {TABLE_NAME} {where_sql} ORDER BY created_at DESC LIMIT {page_size} OFFSET {offset}"
    data_res = db.execute_query(data_query, tuple(params))

    return {
        "page": page,
        "page_size": page_size,
        "total_records": total_records,
        "total_pages": (total_records + page_size - 1) // page_size,
        "tickets": data_res["rows"]
    }


# ==============================================================================
# Minimal UI Endpoint (Dashboard)
# ==============================================================================

@app.get("/", response_class=HTMLResponse, tags=["UI"])
def dashboard(request: Request):
    """Serves the interactive web UI dashboard."""
    stats = db.get_stats()
    provider_name = llm_engine.get_provider_name()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "app_name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "stats": stats,
            "provider_name": provider_name
        }
    )
