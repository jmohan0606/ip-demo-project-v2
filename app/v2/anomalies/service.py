"""Anomaly reads (R6 Y) — retrieval only; detection lives in detection.py.

Both tiers return anomalies ordered by anomaly_id ASC (so they stay
byte-comparable); THIS layer applies the display ranking the screen wants:
severity HIGH > MEDIUM > LOW > INFO, then |impact| descending.
"""
from __future__ import annotations

from app.graph.client import get_graph_client
from app.graph.queries.common import v2_served_by_tier
from app.v2.anomalies.detection import SEVERITY_ORDER, thresholds_in_force


def _num(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


class V2AnomalyService:
    def __init__(self) -> None:
        self.graph = get_graph_client()

    def _run(self, query_name: str, params: dict) -> tuple[list[dict], int]:
        result = self.graph.run_query(query_name, params)
        if not isinstance(result, dict) or result.get("error"):
            raise RuntimeError(f"{query_name} returned an error envelope")
        return result.get("results", []), v2_served_by_tier(result)

    def anomalies(self, advisor_id: str = "", scan_id: str = "",
                  severity: str = "", result_limit: int = 500) -> dict:
        results, tier = self._run("get_anomalies", {
            "advisor_id": advisor_id, "scan_id": scan_id,
            "severity": severity, "result_limit": result_limit})
        scan_id_used, rows = "", []
        for obj in results:
            if "scan_id_used" in obj:
                scan_id_used = str(obj["scan_id_used"])
            if "anomalies" in obj:
                rows = [r.get("attributes", {}) for r in obj["anomalies"]]
        rows.sort(key=lambda a: (SEVERITY_ORDER.get(str(a.get("severity")), 9),
                                 -abs(_num(a.get("impact_amt"))),
                                 str(a.get("anomaly_id"))))
        scan = self._scan_row(scan_id_used)
        return {"scan_id_used": scan_id_used, "scan": scan, "anomalies": rows,
                "thresholds_in_force": thresholds_in_force(), "served_by_tier": tier}

    def scans(self) -> dict:
        results, tier = self._run("get_anomaly_scans", {})
        rows = [r.get("attributes", {}) for obj in results
                for r in obj.get("scans", [])]
        return {"scans": rows, "served_by_tier": tier}

    def _scan_row(self, scan_id: str) -> dict:
        if not scan_id:
            return {}
        for s in self.scans()["scans"]:
            if str(s.get("scan_id")) == scan_id:
                return s
        return {}
