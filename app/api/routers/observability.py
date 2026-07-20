from __future__ import annotations

"""Section 11.7 — observability endpoints: per-LLM-call token/cost, latency, stage traces."""

from fastapi import APIRouter

from app.observability import recorder
from app.shared.responses import ok

router = APIRouter(prefix="/observability", tags=["Observability"])


@router.get("/summary")
def obs_summary():
    return ok(data=recorder.summary())


@router.get("/llm-calls")
def llm_calls(limit: int = 50):
    return ok(data={"calls": recorder.llm_calls(limit), "summary": recorder.summary()})


@router.get("/stage-spans")
def stage_spans(limit: int = 20):
    return ok(data={"spans": recorder.stage_spans(limit)})
