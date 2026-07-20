from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlparse

import requests

from app.config import get_runtime_config


class TigerGraphRestAdapter:
    """TigerGraph RESTPP fallback adapter.

    Correct fallback assumptions:
    - RESTPP installed queries use: GET/POST {restpp_base}/query/{graph}/{query_name}
    - Graph upserts use: POST {restpp_base}/graph/{graph}
    - restpp_base may be:
        * TG_HOST + TG_RESTPP_PORT
        * TIGERGRAPH_RESTPP_URL
        * TIGERGRAPH_HOST if already points at RESTPP
    - Auth can be TG_API_TOKEN / TIGERGRAPH_TOKEN / TG_JWT_TOKEN.
    """

    def __init__(self) -> None:
        self.config = get_runtime_config()
        self.enabled = os.getenv(
            "TIGERGRAPH_REST_ENABLED",
            str(getattr(self.config, "tigergraph_rest_enabled", False)),
        ).lower() == "true"

        self.graph_name = (
            os.getenv("TG_GRAPHNAME")
            or os.getenv("TIGERGRAPH_GRAPH")
            or getattr(self.config, "tigergraph_graph", "iPerformInsights")
        )

        self.timeout = int(
            os.getenv(
                "TIGERGRAPH_TIMEOUT_SECONDS",
                str(getattr(self.config, "tigergraph_timeout_seconds", 30)),
            )
        )

        self.base_url = self._build_restpp_base_url()

    def _build_restpp_base_url(self) -> str:
        explicit = os.getenv("TIGERGRAPH_RESTPP_URL")
        if explicit:
            return explicit.rstrip("/")

        host = (
            os.getenv("TG_HOST")
            or os.getenv("TIGERGRAPH_HOST")
            or getattr(self.config, "tigergraph_host", "")
            or "http://127.0.0.1"
        ).rstrip("/")

        # If caller already provided a RESTPP URL/path, do not mutate it.
        if host.endswith("/restpp") or "/restpp/" in host:
            return host.rstrip("/")

        parsed = urlparse(host)
        has_port = bool(parsed.port)

        # Local/VM TigerGraph often exposes RESTPP on 9000.
        # Some enterprise/cloud routes proxy RESTPP through 443 and should not add a port.
        restpp_port = os.getenv("TG_RESTPP_PORT") or os.getenv("TIGERGRAPH_RESTPP_PORT")
        tgcloud = os.getenv("TG_TGCLOUD", "false").lower() == "true"

        if restpp_port and not has_port and not tgcloud:
            scheme = parsed.scheme or "http"
            netloc = parsed.netloc or parsed.path
            return f"{scheme}://{netloc}:{restpp_port}".rstrip("/")

        return host

    def is_available(self) -> bool:
        return bool(self.enabled and self.base_url and self.graph_name)

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}

        token = (
            os.getenv("TG_API_TOKEN")
            or os.getenv("TIGERGRAPH_TOKEN")
            or getattr(self.config, "tigergraph_token", "")
        )
        jwt = os.getenv("TG_JWT_TOKEN")

        if jwt:
            headers["Authorization"] = f"Bearer {jwt}"
        elif token:
            headers["Authorization"] = f"Bearer {token}"

        return headers

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "base_url": self.base_url,
            "graph_name": self.graph_name,
            "auth_mode": "jwt" if os.getenv("TG_JWT_TOKEN") else "api_token" if (os.getenv("TG_API_TOKEN") or os.getenv("TIGERGRAPH_TOKEN")) else "none",
        }

    def _result(self, operation: str, response: requests.Response) -> dict[str, Any]:
        try:
            data = response.json()
        except Exception:
            data = {"text": response.text}
        return {
            "operation": operation,
            "http_status": response.status_code,
            "url": response.url,
            "data": data,
        }

    def execute_query(self, query_name: str, params: dict[str, Any]) -> dict[str, Any]:
        if not self.is_available():
            raise RuntimeError("TigerGraph RESTPP fallback is not enabled or not configured")

        graph = params.pop("graph_name", None) or self.graph_name
        url = f"{self.base_url}/query/{graph}/{query_name}"

        # Installed queries generally accept parameters as query string for GET.
        # POST fallback is available for larger parameter payloads.
        method = os.getenv("TIGERGRAPH_REST_QUERY_METHOD", "GET").upper()
        if method == "POST":
            response = requests.post(url, json=params, headers=self._headers(), timeout=self.timeout)
        else:
            response = requests.get(url, params=params, headers=self._headers(), timeout=self.timeout)

        response.raise_for_status()
        return self._result("execute_query", response)

    def upsert_vertex(self, vertex_type: str, vertex_id: str, attributes: dict[str, Any]) -> dict[str, Any]:
        if not self.is_available():
            raise RuntimeError("TigerGraph RESTPP fallback is not enabled or not configured")

        url = f"{self.base_url}/graph/{self.graph_name}"
        payload = {
            "vertices": {
                vertex_type: {
                    vertex_id: attributes or {}
                }
            }
        }
        response = requests.post(url, json=payload, headers=self._headers(), timeout=self.timeout)
        response.raise_for_status()
        return self._result("upsert_vertex", response)

    def upsert_edge(
        self,
        edge_type: str,
        from_type: str,
        from_id: str,
        to_type: str,
        to_id: str,
        attributes: dict[str, Any],
    ) -> dict[str, Any]:
        if not self.is_available():
            raise RuntimeError("TigerGraph RESTPP fallback is not enabled or not configured")

        url = f"{self.base_url}/graph/{self.graph_name}"

        # RESTPP graph edge upsert payload shape:
        # edges: { sourceVertexType: { sourceId: { edgeType: { targetVertexType: { targetId: attrs }}}}}
        payload = {
            "edges": {
                from_type: {
                    from_id: {
                        edge_type: {
                            to_type: {
                                to_id: attributes or {}
                            }
                        }
                    }
                }
            }
        }

        response = requests.post(url, json=payload, headers=self._headers(), timeout=self.timeout)
        response.raise_for_status()
        return self._result("upsert_edge", response)

    def ping(self) -> dict[str, Any]:
        if not self.is_available():
            return {"status": "not_available", **self.status()}

        candidates = [
            f"{self.base_url}/echo",
            f"{self.base_url}/version",
        ]

        results = []
        for url in candidates:
            try:
                response = requests.get(url, headers=self._headers(), timeout=self.timeout)
                results.append({
                    "url": url,
                    "http_status": response.status_code,
                    "ok": response.ok,
                    "preview": response.text[:200],
                })
                if response.ok:
                    return {"status": "success", "base_url": self.base_url, "result": results[-1], "all_results": results}
            except Exception as exc:
                results.append({"url": url, "ok": False, "error": str(exc)})

        return {"status": "failed", "base_url": self.base_url, "all_results": results}
