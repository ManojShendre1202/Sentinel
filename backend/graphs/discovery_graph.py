"""
Graph 1 — Weekly Discovery & Shortlist (LangGraph).

fetch_jobs -> normalize_and_store_jobs -> build_scoring_batch ->
score_with_claude -> persist_shortlist. Linear, no branching, no
human-in-the-loop pause (that starts at Graph 2).
"""
import os
from typing import TypedDict

import django
from django.apps import apps as django_apps

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
if not django_apps.ready:
    django.setup()

from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph

from backend.graphs.nodes import build_scoring_batch, fetch_jobs, normalize_and_store_jobs, persist_shortlist, score_with_claude

CHECKPOINT_DB_PATH = Path(__file__).resolve().parent / "checkpoints.sqlite"


class DiscoveryState(TypedDict, total=False):
    raw_jobs: list[dict]
    fetch_errors: list[str]
    normalized_jobs: list[dict]
    batch_json_path: str
    results_json_path: str
    shortlisted_count: int


def _fetch_jobs_node(state: DiscoveryState) -> dict:
    raw_jobs, errors = fetch_jobs.fetch_all()
    return {"raw_jobs": raw_jobs, "fetch_errors": errors}


def _normalize_and_store_jobs_node(state: DiscoveryState) -> dict:
    return {"normalized_jobs": normalize_and_store_jobs.normalize_and_dedup(state["raw_jobs"])}


def _build_scoring_batch_node(state: DiscoveryState) -> dict:
    return {"batch_json_path": build_scoring_batch.build_batch_json(state["normalized_jobs"])}


def _score_with_claude_node(state: DiscoveryState) -> dict:
    return {"results_json_path": score_with_claude.score_batch(state["batch_json_path"])}


def _persist_shortlist_node(state: DiscoveryState) -> dict:
    return {"shortlisted_count": persist_shortlist.persist_results(state["results_json_path"])}


def _wire_graph() -> StateGraph:
    graph = StateGraph(DiscoveryState)
    graph.add_node("fetch_jobs", _fetch_jobs_node)
    graph.add_node("normalize_and_store_jobs", _normalize_and_store_jobs_node)
    graph.add_node("build_scoring_batch", _build_scoring_batch_node)
    graph.add_node("score_with_claude", _score_with_claude_node)
    graph.add_node("persist_shortlist", _persist_shortlist_node)

    graph.set_entry_point("fetch_jobs")
    graph.add_edge("fetch_jobs", "normalize_and_store_jobs")
    graph.add_edge("normalize_and_store_jobs", "build_scoring_batch")
    graph.add_edge("build_scoring_batch", "score_with_claude")
    graph.add_edge("score_with_claude", "persist_shortlist")
    graph.add_edge("persist_shortlist", END)
    return graph


def _build_graph_with_checkpointer(checkpointer):
    return _wire_graph().compile(checkpointer=checkpointer)


def run(*, trigger: str = "scheduled", thread_id: str, resume: bool = False) -> DiscoveryState:
    """Entry point called by weekly_discovery_job.py. `trigger` is for
    logging context only. `thread_id` should be the AgentRun's id, so a
    failed run can be resumed later with the same thread_id + resume=True
    instead of restarting from fetch_jobs (protects API credits already
    spent on that step)."""
    with SqliteSaver.from_conn_string(str(CHECKPOINT_DB_PATH)) as checkpointer:
        compiled = _build_graph_with_checkpointer(checkpointer)
        config = {"configurable": {"thread_id": thread_id}}
        return compiled.invoke(None if resume else {}, config=config)
