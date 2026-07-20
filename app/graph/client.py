from __future__ import annotations

import json
import time
from typing import Any, Callable, Protocol

import httpx

from app.config.settings import get_settings
from app.graph.foundation_store import FoundationGraphStore, get_foundation_store
from app.graph.tier_log import get_tier_log
from app.shared.adapter_logging import logged_adapter_call
from app.shared.logging import get_logger

_tg_log = get_logger("app.graph.tigergraph")


def _mask(value: str | None) -> str:
    """Log-safe fingerprint of a secret/token — never the value itself."""
    if not value:
        return "<none>"
    return f"<set:{len(value)} chars, …{value[-4:]}>" if len(value) >= 4 else "<set>"


def _record_direct(tier: int, operation: str, target: str, start: float, ok: bool, error: str | None = None) -> None:
    """Tier-usage recording for clients used DIRECTLY (mock/real modes without the
    tiered wrapper). No-op while TieredGraphClient is dispatching, so tiered
    requests are recorded exactly once (by the dispatcher). Never raises."""
    log = get_tier_log()
    if log.dispatch_active():
        return
    log.record(tier, operation, target, ok=ok, duration_ms=(time.perf_counter() - start) * 1000, error=error)


class GraphClientError(RuntimeError):
    pass


class PartialUpsertError(GraphClientError):
    def __init__(self, message: str, response: dict, accepted: int, requested: int):
        super().__init__(message)
        self.response = response
        self.accepted = accepted
        self.requested = requested


class GraphClient(Protocol):
    """Adapter interface every service depends on (Section 2 of the rebuild brief).

    Implementations must never leak transport specifics: business logic sees only
    query names from the GSQL_Queries catalog (GQ-###) plus generic upsert/health.
    """

    def run_query(self, query_name: str, params: dict | None = None) -> dict: ...

    def upsert(self, entry: dict, records: list[dict]) -> dict: ...

    def health(self) -> dict: ...

    def statistics(self, kind: str = "vertex", target_type: str = "*") -> dict: ...


class RealGraphClient:
    """RESTPP-backed client, ported from the TigerGraph Foundation package
    (docs/tigergraph_foundation/backend/app/services/tigergraph_client.py).

    Used both for GRAPH_CLIENT_MODE=local_real (Docker Community Edition on
    localhost) and GRAPH_CLIENT_MODE=real (client site) — only env config differs.
    """

    def __init__(self) -> None:
        settings = get_settings()
        base = settings.tigergraph_restpp_url.rstrip("/")
        self.base = base if base.endswith("/restpp") else base + "/restpp"
        self.graph_name = settings.tigergraph_graph
        self.verify_ssl = settings.tigergraph_verify_ssl
        self.timeout = settings.tigergraph_timeout_seconds
        self.use_ssl = self.base.startswith("https://")
        self.token = settings.tigergraph_token or ""
        self.secret = settings.tigergraph_secret or ""
        self.token_lifetime = getattr(settings, "tg_token_lifetime_seconds", 0)
        self.headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.token:
            self.headers["Authorization"] = f"Bearer {self.token}"
        self._auth_ready = bool(self.token) or not self.secret  # only need getToken if a secret & no token
        _tg_log.info(
            "TigerGraph(RESTPP) client initialized",
            extra={"restpp_url": self.base, "graph": self.graph_name, "use_ssl": self.use_ssl,
                   "verify_ssl": self.verify_ssl,
                   "auth": ("token" if self.token else "secret->requesttoken" if self.secret else "none"),
                   "secret": _mask(self.secret), "token": _mask(self.token)},
        )

    def _client(self) -> httpx.Client:
        return httpx.Client(verify=self.verify_ssl, timeout=self.timeout)

    def _ensure_auth(self) -> None:
        """Acquire a REST++ token from the secret when no static token was provided
        (getToken equivalent for the httpx RESTPP path). Runs once, logs the outcome."""
        if self._auth_ready:
            return
        params = {"secret": self.secret}
        if self.token_lifetime:
            params["lifetime"] = str(self.token_lifetime)
        try:
            with self._client() as client:
                response = client.get(f"{self.base}/requesttoken", params=params)
                response.raise_for_status()
                data = response.json()
            token = data.get("token") or (data.get("results") or {}).get("token")
            if not token:
                raise GraphClientError(f"requesttoken returned no token: {data}")
            self.token = token
            self.headers["Authorization"] = f"Bearer {token}"
            self._auth_ready = True
            _tg_log.info(
                "TigerGraph(RESTPP) token acquired via requesttoken(secret)",
                extra={"token": _mask(token), "expires": str(data.get("expiration", "server-default")),
                       "graph": self.graph_name},
            )
        except Exception as exc:  # noqa: BLE001
            _tg_log.error(
                "TigerGraph(RESTPP) token acquisition FAILED: %s: %s",
                type(exc).__name__, exc, exc_info=True,
                extra={"restpp_url": self.base, "graph": self.graph_name, "secret": _mask(self.secret)},
            )
            raise

    def health(self) -> dict:
        try:
            self._ensure_auth()
            with self._client() as client:
                response = client.get(f"{self.base}/echo", headers=self.headers)
                response.raise_for_status()
            _tg_log.info("TigerGraph(RESTPP) connection established (echo ok)",
                         extra={"restpp_url": self.base, "graph": self.graph_name})
            return {"healthy": True, "mode": "real", "graph": self.graph_name, "restpp_url": self.base}
        except Exception as exc:
            _tg_log.error("TigerGraph(RESTPP) health/echo FAILED: %s: %s", type(exc).__name__, exc,
                          exc_info=True, extra={"restpp_url": self.base, "graph": self.graph_name})
            return {"healthy": False, "mode": "real", "graph": self.graph_name, "restpp_url": self.base, "error": str(exc)}

    @logged_adapter_call("graph")
    def run_query(self, query_name: str, params: dict | None = None) -> dict:
        start = time.perf_counter()
        try:
            self._ensure_auth()
            with self._client() as client:
                response = client.get(
                    f"{self.base}/query/{self.graph_name}/{query_name}",
                    headers=self.headers,
                    params=params or {},
                )
                response.raise_for_status()
                data = response.json()
            if data.get("error"):
                raise GraphClientError(data.get("message") or f"TigerGraph query failed: {query_name}")
        except Exception as exc:
            _record_direct(3, "run_query", query_name, start, ok=False, error=str(exc))
            raise
        _record_direct(3, "run_query", query_name, start, ok=True)
        return data

    def _attributes(self, entry: dict, row: dict, excluded: set[str]) -> dict:
        attributes: dict[str, dict[str, Any]] = {}
        for source_column, graph_attribute in entry.get("columns", {}).items():
            if source_column in excluded:
                continue
            value = row.get(source_column)
            if value in ("", None):
                continue
            attributes[graph_attribute] = {"value": _coerce(value)}
        return attributes

    def build_payload(self, entry: dict, records: list[dict]) -> dict:
        if entry["kind"] == "vertex":
            target = entry["target"]
            id_col = entry["id_column"]
            vertices: dict[str, dict] = {target: {}}
            for row in records:
                vertex_id = str(row[id_col]).strip()
                if not vertex_id:
                    raise GraphClientError(f"Blank vertex id in {entry['file']}")
                vertices[target][vertex_id] = self._attributes(entry, row, {id_col})
            return {"vertices": vertices}

        edge_name = entry["target"]
        edges: dict = {entry["from_type"]: {}}
        for row in records:
            from_id = str(row[entry["from_column"]]).strip()
            to_id = str(row[entry["to_column"]]).strip()
            if not from_id or not to_id:
                raise GraphClientError(f"Blank edge endpoint in {entry['file']}")
            target_map = (
                edges.setdefault(entry["from_type"], {})
                .setdefault(from_id, {})
                .setdefault(edge_name, {})
                .setdefault(entry["to_type"], {})
            )
            target_map[to_id] = self._attributes(entry, row, {entry["from_column"], entry["to_column"]})
        return {"edges": edges}

    @staticmethod
    def _accepted_count(data: dict, kind: str) -> int:
        key = "accepted_vertices" if kind == "vertex" else "accepted_edges"
        if isinstance(data.get(key), int):
            return int(data[key])
        total = 0
        results = data.get("results", [])
        if isinstance(results, list):
            for item in results:
                if isinstance(item, dict):
                    value = item.get(key)
                    if isinstance(value, int):
                        total += value
        return total

    @logged_adapter_call("graph")
    def upsert(self, entry: dict, records: list[dict]) -> dict:
        if not records:
            return {"accepted_vertices": 0, "accepted_edges": 0, "errors": []}
        start = time.perf_counter()
        try:
            result = self._upsert(entry, records)
        except Exception as exc:
            _record_direct(3, "upsert", entry.get("target", "?"), start, ok=False, error=str(exc))
            raise
        _record_direct(3, "upsert", entry.get("target", "?"), start, ok=True)
        return result

    def _upsert(self, entry: dict, records: list[dict]) -> dict:
        self._ensure_auth()
        payload = self.build_payload(entry, records)
        params = {"vertex_must_exist": "true"} if entry["kind"] == "edge" else None
        with self._client() as client:
            response = client.post(
                f"{self.base}/graph/{self.graph_name}",
                headers=self.headers,
                params=params,
                content=json.dumps(payload),
            )
            response.raise_for_status()
            data = response.json()
        if data.get("error"):
            _tg_log.error(
                "TigerGraph(RESTPP) upsert rejected for %s: %s",
                entry.get("target"), data.get("message"),
                extra={"kind": entry.get("kind"), "target": entry.get("target"), "requested": len(records)},
            )
            raise GraphClientError(data.get("message") or f"TigerGraph upsert failed for {entry['target']}")
        accepted = self._accepted_count(data, entry["kind"])
        _tg_log.info(
            "TigerGraph(RESTPP) %s batch upserted",
            entry["kind"],
            extra={"kind": entry["kind"], "target": entry["target"],
                   "requested": len(records), "accepted": accepted, "graph": self.graph_name},
        )
        if accepted != len(records):
            _tg_log.error(
                "TigerGraph(RESTPP) upsert PARTIAL: %s of %s for %s",
                accepted, len(records), entry["target"],
                extra={"kind": entry["kind"], "target": entry["target"],
                       "requested": len(records), "accepted": accepted},
            )
            raise PartialUpsertError(
                f"TigerGraph accepted {accepted} of {len(records)} requested {entry['kind']} records for {entry['target']}",
                data,
                accepted,
                len(records),
            )
        return data

    def statistics(self, kind: str = "vertex", target_type: str = "*") -> dict:
        if kind not in {"vertex", "edge"}:
            raise ValueError("kind must be vertex or edge")
        function = "stat_vertex_number" if kind == "vertex" else "stat_edge_number"
        payload = {"function": function, "type": target_type}
        with self._client() as client:
            response = client.post(
                f"{self.base}/builtins/{self.graph_name}", headers=self.headers, content=json.dumps(payload)
            )
            response.raise_for_status()
            data = response.json()
        if data.get("error"):
            raise GraphClientError(data.get("message") or f"TigerGraph builtin failed: {function}")
        return data


# Registry of Python implementations of the GQ-### catalog queries, keyed by the
# installed query name (e.g. "get_org_hierarchy"). Populated by app/graph/queries/
# modules via the @mock_query decorator (Phase 3).
MOCK_QUERY_IMPLS: dict[str, Callable[[FoundationGraphStore, dict], list[dict]]] = {}


def mock_query(name: str):
    def register(fn: Callable[[FoundationGraphStore, dict], list[dict]]):
        MOCK_QUERY_IMPLS[name] = fn
        return fn

    return register


class MockGraphClient:
    """Same interface and result envelope as RealGraphClient, backed by the
    foundation package's 185 verified CSVs loaded into FoundationGraphStore.

    Each GQ-### query has a Python equivalent registered in MOCK_QUERY_IMPLS that
    traverses the same vertices/edges the GSQL version traverses, returning the
    same result keys, so services cannot tell which mode is active.
    """

    def __init__(self, store: FoundationGraphStore | None = None) -> None:
        import app.graph.queries  # noqa: F401 — registers every GQ implementation

        self.store = store or get_foundation_store()
        # runtime upserts (AI artifacts written back to the graph) — kept separate
        # from the seeded foundation data so statistics can distinguish them.
        self.runtime_vertices: dict[str, dict[str, dict]] = {}
        self.runtime_edges: list[dict] = []

    def health(self) -> dict:
        return {
            "healthy": self.store.loaded,
            "mode": "mock",
            "graph": get_settings().tigergraph_graph,
            "load_report": self.store.load_report,
        }

    @logged_adapter_call("graph")
    @logged_adapter_call("graph")
    def run_query(self, query_name: str, params: dict | None = None) -> dict:
        start = time.perf_counter()
        impl = MOCK_QUERY_IMPLS.get(query_name)
        if impl is None:
            error = (
                f"MockGraphClient has no implementation registered for query '{query_name}'. "
                f"Registered: {sorted(MOCK_QUERY_IMPLS)}"
            )
            _record_direct(4, "run_query", query_name, start, ok=False, error=error)
            raise GraphClientError(error)
        results = impl(self.store, params or {})
        _record_direct(4, "run_query", query_name, start, ok=True)
        return {"error": False, "results": results, "mode": "mock", "query": query_name}

    @logged_adapter_call("graph")
    def upsert(self, entry: dict, records: list[dict]) -> dict:
        """Writes into the same indexes the query implementations traverse —
        mirroring real TigerGraph, where upserted artifacts are immediately
        visible to installed queries (the traceability chain depends on this)."""
        start = time.perf_counter()
        result = self._upsert(entry, records)
        _record_direct(4, "upsert", entry.get("target", "?"), start, ok=True)
        return result

    def _upsert(self, entry: dict, records: list[dict]) -> dict:
        accepted = 0
        if entry["kind"] == "vertex":
            vertex_type = entry["target"]
            id_col = entry["id_column"]
            for row in records:
                vertex_id = str(row[id_col])
                attrs = {graph_attr: row.get(src) for src, graph_attr in entry.get("columns", {}).items()}
                existing = self.store.vertices[vertex_type].get(vertex_id, {})
                self.store.vertices[vertex_type][vertex_id] = {**existing, **attrs}
                self.runtime_vertices.setdefault(vertex_type, {})[vertex_id] = attrs
                accepted += 1
            return {"error": False, "accepted_vertices": accepted, "accepted_edges": 0, "mode": "mock"}
        edge_name = entry["target"]
        from_col, to_col = entry["from_column"], entry["to_column"]
        for row in records:
            from_id, to_id = str(row[from_col]), str(row[to_col])
            attrs = {
                graph_attr: row.get(src)
                for src, graph_attr in entry.get("columns", {}).items()
                if src not in (from_col, to_col)
            }
            already = any(t == to_id for t, _ in self.store.out_index[edge_name].get(from_id, []))
            if not already:
                self.store.edges[edge_name].append(
                    {"from_type": entry["from_type"], "from_id": from_id,
                     "to_type": entry["to_type"], "to_id": to_id, "attrs": attrs}
                )
                self.store.out_index[edge_name][from_id].append((to_id, attrs))
                self.store.in_index[edge_name][to_id].append((from_id, attrs))
            self.runtime_edges.append({"edge": edge_name, **row})
            accepted += 1
        return {"error": False, "accepted_vertices": 0, "accepted_edges": accepted, "mode": "mock"}

    def statistics(self, kind: str = "vertex", target_type: str = "*") -> dict:
        stats = self.store.statistics()
        counts = stats["vertex_counts"] if kind == "vertex" else stats["edge_counts"]
        if target_type != "*":
            counts = {target_type: counts.get(target_type, 0)}
        return {"error": False, "results": [{"counts": counts}], "mode": "mock"}


_graph_client: GraphClient | None = None


def get_graph_client() -> GraphClient:
    """Select the GraphClient per GRAPH_CLIENT_MODE.

    mode=mock                → MockGraphClient directly (Tier 4 only) — the working
                               default; behavior identical to before Section 9.4.
    mode=auto|tiered|mcp     → TieredGraphClient with the full 4-tier chain
                               (tigergraph-mcp → pyTigerGraph → RESTPP → mock).
    mode=local_real|real     → TieredGraphClient with the non-agent chain
                               (pyTigerGraph → RESTPP → mock) — real engine first,
                               automatic fallback to mock if it is unreachable.
    """
    global _graph_client
    if _graph_client is None:
        mode = get_settings().graph_client_mode.lower()
        if mode == "mock":
            _graph_client = MockGraphClient()
        elif mode in {"auto", "tiered", "mcp", "local_real", "real"}:
            from app.graph.tiered_client import TieredGraphClient  # lazy: avoids import cycle

            _graph_client = TieredGraphClient.for_mode(mode)
        else:
            raise GraphClientError(
                f"Unknown GRAPH_CLIENT_MODE '{mode}' (expected mock|auto|tiered|mcp|local_real|real)"
            )
    return _graph_client


def reset_graph_client() -> None:
    global _graph_client
    _graph_client = None


def _coerce(value: Any):
    if isinstance(value, (bool, int, float)) or value is None:
        return value
    text = str(value).strip()
    if text.lower() in {"true", "false"}:
        return text.lower() == "true"
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        return text
