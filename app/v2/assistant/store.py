"""Conversation persistence for Ask iPerform (FIX_SPEC_R7 A5).

TigerGraph is the system of record, the SQLite/CSV local tier is the fallback
— the same TieredGraphClient + TigerGraphUpsertClient path every other write
uses, so chat still works when the graph is unavailable and the serving tier
is recorded on every read.

Writes mirror the anomaly-scan pattern: vertex/edge upserts through the active
GraphClient plus an append to the data-set CSVs (workflow artifacts — header
files exist from the dataset builder, preserved on regeneration).

PII NOTE: message text arrives here ALREADY redacted by the guardrail gate
(A9) — raw SSN/card values never reach this module.

Reads go through catalogued queries (GQ-020 get_conversations / GQ-021
get_conversation_messages) — never ad-hoc traversals.
"""
from __future__ import annotations

import csv
import json
import uuid
from datetime import datetime, timezone

from app.config.settings import get_settings
from app.graph.client import get_graph_client
from app.graph.queries.common import v2_served_by_tier
from app.ingestion.tigergraph_upsert import TigerGraphUpsertClient
from app.shared.logging import get_logger
from app.v2.dataset.builder import csv_file_for

_log = get_logger("app.v2.assistant.store")

DATA_SOURCE = "DERIVED"  # runtime artifacts computed by us over real/loaded data

# Full column set for the conversation row. Empty-string attributes are
# dropped by the upsert/read-back path, so rows are re-normalized before every
# write to keep the record complete (ColumnMismatchError otherwise).
_CONVERSATION_DEFAULTS = {
    "conversation_id": "", "title": "", "created_at": "", "last_message_at": "",
    "message_count": 0, "scope_json": "", "data_source": DATA_SOURCE,
}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _csv_append(file_rel: str, rows: list[dict]) -> None:
    """Append to the workflow CSV so the local tier survives a restart. The
    header row is authoritative (written by the dataset builder). Conversation
    updates append a fresh full row — the store loads by primary id, so the
    last row wins (same additive semantics as anomaly scans)."""
    if not rows:
        return
    path = get_settings().resolved_data_set_dir / file_rel
    if not path.exists():
        _log.warning("workflow CSV missing, skipping local append: %s", path)
        return
    with path.open(newline="", encoding="utf-8-sig") as f:
        header = next(csv.reader(f))
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=header, extrasaction="ignore", lineterminator="\n")
        for r in rows:
            writer.writerow(r)


class AssistantStore:
    def __init__(self) -> None:
        self.graph = get_graph_client()
        self.upsert = TigerGraphUpsertClient()

    # ------------------------------------------------------------ writes

    def create_conversation(self, title: str, advisor_sid: str = "",
                            scope_json: str = "") -> dict:
        conversation = {
            "conversation_id": uuid.uuid4().hex[:12],
            "title": (title or "New conversation")[:80],
            "created_at": _now(),
            "last_message_at": _now(),
            "message_count": 0,
            "scope_json": scope_json or "",
            "data_source": DATA_SOURCE,
        }
        self.upsert.upsert_vertex_rows("phx_dm_v2_conversation", [conversation], "conversation_id")
        _csv_append(csv_file_for("vertex", "conversation"), [conversation])
        if advisor_sid:
            edge = {"from_id": conversation["conversation_id"], "to_id": advisor_sid}
            self.upsert.upsert_edge_rows("phx_dm_v2_conversation_for_advisor", [edge])
            _csv_append(csv_file_for("edge", "conversation_for_advisor"), [edge])
        return conversation

    def append_message(self, conversation: dict, *, role: str, text: str,
                       resolved_context: dict | None = None,
                       queries_run: list[dict] | None = None,
                       figures: list[dict] | None = None,
                       llm_provider: str = "", status: str = "OK",
                       guardrail_status: str = "PASS",
                       guardrail_json: str = "") -> dict:
        seq = int(conversation.get("message_count") or 0) + 1
        message = {
            "message_id": f"{conversation['conversation_id']}|{seq}",
            "conversation_id": conversation["conversation_id"],
            "seq": seq,
            "role": role,
            "text": text,
            "resolved_context_json": json.dumps(resolved_context) if resolved_context else "",
            "queries_run_json": json.dumps(queries_run) if queries_run else "",
            "figures_json": json.dumps(figures) if figures else "",
            "llm_provider": llm_provider,
            "status": status,
            "guardrail_status": guardrail_status,
            "guardrail_json": guardrail_json,
            "created_at": _now(),
            "data_source": DATA_SOURCE,
        }
        self.upsert.upsert_vertex_rows("phx_dm_v2_message", [message], "message_id")
        _csv_append(csv_file_for("vertex", "message"), [message])
        edge = {"from_id": message["message_id"], "to_id": conversation["conversation_id"]}
        self.upsert.upsert_edge_rows("phx_dm_v2_message_in_conversation", [edge])
        _csv_append(csv_file_for("edge", "message_in_conversation"), [edge])

        conversation["message_count"] = seq
        conversation["last_message_at"] = _now()
        row = {**_CONVERSATION_DEFAULTS, **conversation}
        self.upsert.upsert_vertex_rows("phx_dm_v2_conversation", [row], "conversation_id")
        _csv_append(csv_file_for("vertex", "conversation"), [row])
        return message

    # ------------------------------------------------------------ reads (catalogued queries)

    def conversation(self, conversation_id: str) -> dict | None:
        """One conversation's header row, via the same catalogued list query."""
        for row in self.conversations(days=0)["conversations"]:
            if str(row.get("conversation_id")) == conversation_id:
                return {**_CONVERSATION_DEFAULTS, **row}
        return None

    def conversations(self, advisor_id: str = "", days: int | None = None,
                      result_limit: int = 200) -> dict:
        if days is None:
            days = get_settings().assistant_history_days
        result = self.graph.run_query("get_conversations", {
            "advisor_id": advisor_id, "days": int(days), "result_limit": result_limit})
        rows: list[dict] = []
        for obj in result.get("results", []):
            if "conversations" in obj:
                rows = [r.get("attributes", {}) for r in obj["conversations"]]
        return {"conversations": rows, "served_by_tier": v2_served_by_tier(result)}

    def messages(self, conversation_id: str) -> dict:
        result = self.graph.run_query("get_conversation_messages",
                                      {"conversation_id": conversation_id})
        rows: list[dict] = []
        for obj in result.get("results", []):
            if "messages" in obj:
                rows = [r.get("attributes", {}) for r in obj["messages"]]
        return {"messages": rows, "served_by_tier": v2_served_by_tier(result)}
