from __future__ import annotations
from typing import Any
import requests
from app.config.settings import get_settings


class TigerGraphRestClient:
    def __init__(self) -> None:
        self.settings = get_settings()

    def is_configured(self) -> bool:
        return bool(self.settings.tigergraph_host)

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.settings.tigergraph_token:
            headers["Authorization"] = f"Bearer {self.settings.tigergraph_token}"
        return headers

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.settings.tigergraph_host:
            raise RuntimeError("TIGERGRAPH_HOST is not configured")
        url = f"{self.settings.tigergraph_host.rstrip('/')}/{path.lstrip('/')}"
        response = requests.get(url, params=params or {}, headers=self._headers(), timeout=self.settings.tigergraph_rest_timeout_seconds)
        response.raise_for_status()
        return response.json()

    def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.settings.tigergraph_host:
            raise RuntimeError("TIGERGRAPH_HOST is not configured")
        url = f"{self.settings.tigergraph_host.rstrip('/')}/{path.lstrip('/')}"
        response = requests.post(url, json=payload, headers=self._headers(), timeout=self.settings.tigergraph_rest_timeout_seconds)
        response.raise_for_status()
        return response.json()


    def health_check(self) -> dict:
        if not self.is_configured():
            raise RuntimeError("TigerGraph REST is not configured.")
        return {"success": True, "mode": "rest", "message": "TigerGraph REST client configured."}
