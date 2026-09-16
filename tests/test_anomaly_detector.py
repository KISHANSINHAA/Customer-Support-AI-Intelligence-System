import pytest
from src.anomaly_detector import anomaly_detector

def test_detect_all_anomalies():
    summary = anomaly_detector.detect_all_anomalies()
    assert summary.total_anomalies > 0
    assert "RESOLUTION_TIME_OUTLIER" in summary.by_type
    assert "UNRESOLVED_URGENT_TICKET" in summary.by_type
    assert summary.by_severity["CRITICAL"] > 0
    assert summary.by_severity["HIGH"] > 0

def test_resolution_time_outliers():
    summary = anomaly_detector.detect_all_anomalies(anomaly_type_filter="RESOLUTION_TIME_OUTLIER")
    # All resolution time outliers must exceed 48.15 hrs
    assert summary.total_anomalies == 21
    for a in summary.anomalies:
        assert a.metric_value > 48.0

def test_urgent_unresolved_sla_breach():
    summary = anomaly_detector.detect_all_anomalies(anomaly_type_filter="UNRESOLVED_URGENT_TICKET")
    assert summary.total_anomalies > 0
    for a in summary.anomalies:
        assert a.priority in ("High", "Critical")
        assert a.status != "Resolved"
        assert a.metric_value > 24.0

def test_weekly_resolution_anomalies():
    weekly_anomalies = anomaly_detector.detect_resolution_time_anomalies_in_window(days=7)
    assert len(weekly_anomalies) == 6
