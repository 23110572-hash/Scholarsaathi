from __future__ import annotations

import uuid
from functools import lru_cache
from typing import Any, Protocol, TypedDict

from langgraph.graph import END, START, StateGraph


class ApplicationFlowRuntime(Protocol):
    def resolve_target(self) -> dict[str, Any]: ...

    def authentication_gate(self) -> dict[str, Any]: ...

    def validate_window(self) -> dict[str, Any]: ...

    def load_readiness(self) -> dict[str, Any]: ...

    def persist_readiness(self) -> dict[str, Any]: ...

    def create_or_reuse_application(self) -> dict[str, Any]: ...

    def submit_application(self) -> dict[str, Any]: ...

    def finalize(self) -> dict[str, Any]: ...


class ApplicationFlowState(TypedDict, total=False):
    intent_id: str
    runtime: ApplicationFlowRuntime
    halted: bool
    status: str
    application_id: str | None


def _run_runtime_step(
    state: ApplicationFlowState,
    method_name: str,
) -> dict[str, Any]:
    if state.get("halted"):
        return {}
    runtime = state["runtime"]
    method = getattr(runtime, method_name)
    return method()


def _resolve_target(state: ApplicationFlowState) -> dict[str, Any]:
    return _run_runtime_step(state, "resolve_target")


def _authentication_gate(state: ApplicationFlowState) -> dict[str, Any]:
    return _run_runtime_step(state, "authentication_gate")


def _validate_window(state: ApplicationFlowState) -> dict[str, Any]:
    return _run_runtime_step(state, "validate_window")


def _load_readiness(state: ApplicationFlowState) -> dict[str, Any]:
    return _run_runtime_step(state, "load_readiness")


def _persist_readiness(state: ApplicationFlowState) -> dict[str, Any]:
    return _run_runtime_step(state, "persist_readiness")


def _create_or_reuse_application(state: ApplicationFlowState) -> dict[str, Any]:
    return _run_runtime_step(state, "create_or_reuse_application")


def _submit_application(state: ApplicationFlowState) -> dict[str, Any]:
    return _run_runtime_step(state, "submit_application")


def _finalize(state: ApplicationFlowState) -> dict[str, Any]:
    return _run_runtime_step(state, "finalize")


@lru_cache
def _application_flow_graph():
    graph = StateGraph(ApplicationFlowState)
    graph.add_node("resolve_current_target", _resolve_target)
    graph.add_node("authentication_gate", _authentication_gate)
    graph.add_node("validate_current_window", _validate_window)
    graph.add_node("load_profile_and_documents", _load_readiness)
    graph.add_node("persist_readiness", _persist_readiness)
    graph.add_node("create_or_reuse_application", _create_or_reuse_application)
    graph.add_node("submit_to_internal_provider_queue", _submit_application)
    graph.add_node("finalize_intent", _finalize)
    graph.add_edge(START, "resolve_current_target")
    graph.add_edge("resolve_current_target", "authentication_gate")
    graph.add_edge("authentication_gate", "validate_current_window")
    graph.add_edge("validate_current_window", "load_profile_and_documents")
    graph.add_edge("load_profile_and_documents", "persist_readiness")
    graph.add_edge("persist_readiness", "create_or_reuse_application")
    graph.add_edge("create_or_reuse_application", "submit_to_internal_provider_queue")
    graph.add_edge("submit_to_internal_provider_queue", "finalize_intent")
    graph.add_edge("finalize_intent", END)
    # Business state is persisted in ApplicationIntent. No graph checkpointer is required.
    return graph.compile()


def run_application_flow(
    runtime: ApplicationFlowRuntime,
    intent_id: uuid.UUID,
) -> ApplicationFlowState:
    return _application_flow_graph().invoke(
        {"intent_id": str(intent_id), "runtime": runtime, "halted": False},
        config={"configurable": {"thread_id": str(intent_id)}},
    )
