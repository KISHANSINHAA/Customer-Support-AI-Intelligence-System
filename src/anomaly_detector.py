from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import pandas as pd
import numpy as np
from pydantic import BaseModel, Field
from src.database import db, TABLE_NAME
from src.config import settings


class AnomalyRecord(BaseModel):
    ticket_id: str
    created_at: str
    category: str
    priority: str
    status: str
    agent_id: str
    anomaly_type: str
    severity: str = Field(..., description="CRITICAL, HIGH, or MEDIUM")
    metric_name: str
    metric_value: Optional[float] = None
    threshold: Optional[float] = None
    explanation: str
    recommended_action: str


class AnomalySummary(BaseModel):
    total_anomalies: int
    by_severity: Dict[str, int]
    by_type: Dict[str, int]
    anomalies: List[AnomalyRecord]


class AnomalyDetector:
    def __init__(self):
        self.db = db

    def get_dataset_df(self) -> pd.DataFrame:
        """Loads data from SQLite into pandas for statistical analysis."""
        with self.db.get_connection() as conn:
            df = pd.read_sql_query(f"SELECT * FROM {TABLE_NAME}", conn)
        df["created_at"] = pd.to_datetime(df["created_at"])
        return df

    def detect_all_anomalies(
        self,
        severity_filter: Optional[str] = None,
        anomaly_type_filter: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: Optional[int] = None
    ) -> AnomalySummary:
        """Runs both statistical and rule-based anomaly detection."""
        df = self.get_dataset_df()
        anomalies: List[AnomalyRecord] = []

        # Reference time: Use dataset's latest timestamp to calculate realistic SLA age
        ref_time = df["created_at"].max()

        # 1. Statistical Outliers: Resolution Time (IQR Method)
        resolved_df = df[df["status"] == "Resolved"].copy()
        if not resolved_df.empty:
            q1 = resolved_df["resolution_time_hrs"].quantile(0.25)
            q3 = resolved_df["resolution_time_hrs"].quantile(0.75)
            iqr = q3 - q1
            iqr_mult = settings.ANOMALY_IQR_MULTIPLIER
            upper_bound = q3 + (iqr_mult * iqr)  # ~48.15 hours

            resolution_outliers = resolved_df[resolved_df["resolution_time_hrs"] > upper_bound]

            for _, row in resolution_outliers.iterrows():
                val = float(row["resolution_time_hrs"])
                if val >= 72.0:
                    sev = "CRITICAL"
                elif val >= 48.0:
                    sev = "HIGH"
                else:
                    sev = "MEDIUM"

                anomalies.append(AnomalyRecord(
                    ticket_id=row["ticket_id"],
                    created_at=row["created_at"].strftime("%Y-%m-%d %H:%M:%S"),
                    category=row["category"],
                    priority=row["priority"],
                    status=row["status"],
                    agent_id=row["agent_id"],
                    anomaly_type="RESOLUTION_TIME_OUTLIER",
                    severity=sev,
                    metric_name="resolution_time_hrs",
                    metric_value=round(val, 2),
                    threshold=round(upper_bound, 2),
                    explanation=(
                        f"Ticket resolution time of {val:.1f} hours significantly exceeds the statistical "
                        f"upper threshold of {upper_bound:.1f} hours (IQR multiplier: {iqr_mult})."
                    ),
                    recommended_action="Review agent notes and ticket history to identify bottlenecks or complex dependencies."
                ))

        # 2. Rule-Based SLA Breach: Unresolved High or Critical priority tickets older than 24 hours
        urgent_unresolved = df[
            (df["priority"].isin(["High", "Critical"])) &
            (df["status"] != "Resolved")
        ].copy()

        for _, row in urgent_unresolved.iterrows():
            age_hours = (ref_time - row["created_at"]).total_seconds() / 3600.0
            threshold_hours = settings.ANOMALY_SLA_URGENT_HOURS

            if age_hours > threshold_hours:
                sev = "CRITICAL" if row["priority"] == "Critical" else "HIGH"
                anomalies.append(AnomalyRecord(
                    ticket_id=row["ticket_id"],
                    created_at=row["created_at"].strftime("%Y-%m-%d %H:%M:%S"),
                    category=row["category"],
                    priority=row["priority"],
                    status=row["status"],
                    agent_id=row["agent_id"],
                    anomaly_type="UNRESOLVED_URGENT_TICKET",
                    severity=sev,
                    metric_name="age_hours",
                    metric_value=round(age_hours, 1),
                    threshold=threshold_hours,
                    explanation=(
                        f"{row['priority']} priority ticket has remained {row['status']} for {age_hours:.1f} hours, "
                        f"breaching the {threshold_hours:.0f}-hour resolution target."
                    ),
                    recommended_action="Escalate immediately to senior technical lead or tier-2 support queue."
                ))

        # 3. Response Time Outlier: First response delay > 4.5 hours
        response_threshold = 4.5
        delayed_responses = df[df["response_time_hrs"] >= response_threshold].copy()
        for _, row in delayed_responses.iterrows():
            resp_time = float(row["response_time_hrs"])
            anomalies.append(AnomalyRecord(
                ticket_id=row["ticket_id"],
                created_at=row["created_at"].strftime("%Y-%m-%d %H:%M:%S"),
                category=row["category"],
                priority=row["priority"],
                status=row["status"],
                agent_id=row["agent_id"],
                anomaly_type="EXCESSIVE_FIRST_RESPONSE_TIME",
                severity="HIGH" if resp_time >= 4.8 else "MEDIUM",
                metric_name="response_time_hrs",
                metric_value=round(resp_time, 2),
                threshold=response_threshold,
                explanation=f"Initial agent response took {resp_time:.1f} hours, exceeding standard SLA ceiling of {response_threshold} hours.",
                recommended_action="Check agent dispatch queue balance and intake notifications."
            ))

        # 4. Satisfaction Quality Anomaly: Low rating (<=2) despite successful resolution
        low_rating_threshold = settings.ANOMALY_LOW_RATING_THRESHOLD
        low_ratings = df[(df["status"] == "Resolved") & (df["customer_rating"] <= low_rating_threshold)].copy()
        for _, row in low_ratings.iterrows():
            rating = int(row["customer_rating"])
            anomalies.append(AnomalyRecord(
                ticket_id=row["ticket_id"],
                created_at=row["created_at"].strftime("%Y-%m-%d %H:%M:%S"),
                category=row["category"],
                priority=row["priority"],
                status=row["status"],
                agent_id=row["agent_id"],
                anomaly_type="LOW_CUSTOMER_SATISFACTION",
                severity="HIGH" if rating == 1 else "MEDIUM",
                metric_name="customer_rating",
                metric_value=float(rating),
                threshold=float(low_rating_threshold),
                explanation=f"Ticket was marked resolved but received a poor satisfaction rating of {rating}/5.",
                recommended_action="Conduct customer follow-up to assess whether issue recurred or resolution was incomplete."
            ))

        # Filter by date if provided
        if start_date:
            s_dt = pd.to_datetime(start_date)
            anomalies = [a for a in anomalies if pd.to_datetime(a.created_at) >= s_dt]
        if end_date:
            e_dt = pd.to_datetime(end_date)
            anomalies = [a for a in anomalies if pd.to_datetime(a.created_at) <= e_dt]

        # Filter by severity
        if severity_filter:
            anomalies = [a for a in anomalies if a.severity.upper() == severity_filter.upper()]

        # Filter by anomaly type
        if anomaly_type_filter:
            anomalies = [a for a in anomalies if a.anomaly_type.upper() == anomaly_type_filter.upper()]

        # Sort by severity priority: CRITICAL > HIGH > MEDIUM, then by date descending
        sev_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2}
        anomalies.sort(key=lambda a: (sev_order.get(a.severity, 3), a.created_at), reverse=False)

        # Calculate counts before limit
        by_severity = {
            "CRITICAL": sum(1 for a in anomalies if a.severity == "CRITICAL"),
            "HIGH": sum(1 for a in anomalies if a.severity == "HIGH"),
            "MEDIUM": sum(1 for a in anomalies if a.severity == "MEDIUM")
        }
        by_type: Dict[str, int] = {}
        for a in anomalies:
            by_type[a.anomaly_type] = by_type.get(a.anomaly_type, 0) + 1

        total_count = len(anomalies)

        if limit and limit > 0:
            anomalies = anomalies[:limit]

        return AnomalySummary(
            total_anomalies=total_count,
            by_severity=by_severity,
            by_type=by_type,
            anomalies=anomalies
        )

    def detect_resolution_time_anomalies_in_window(self, days: int = 7) -> List[AnomalyRecord]:
        """Detects resolution time anomalies in the most recent N days of data (e.g., 'this week')."""
        df = self.get_dataset_df()
        max_date = df["created_at"].max()
        window_start = max_date - timedelta(days=days)

        summary = self.detect_all_anomalies(
            anomaly_type_filter="RESOLUTION_TIME_OUTLIER",
            start_date=window_start.strftime("%Y-%m-%d %H:%M:%S")
        )
        return summary.anomalies


anomaly_detector = AnomalyDetector()
