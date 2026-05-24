"""LangGraph orchestration of the four agents over the Redis broker.

The graph is the control plane: each node hands work to a distributed agent
queue and waits for the reply. The executor node fans a list of subtasks out
to the shared executor queue at once, so independent subtasks are solved in
parallel by whatever executor replicas are available. A critic node can send
the work back for one or more revision rounds before the aggregator produces
the final answer.

    START -> plan -> execute -> critic --(approved)--> aggregate -> END
                        ^                  |
                        +---(needs work)---+
"""

from __future__ import annotations

import asyncio
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from agents.broker import Broker
from agents.protocol import ResultMessage
from config import AGGREGATOR, CRITIC, EXECUTOR, PLANNER, settings
from logging_config import get_logger, log_error

logger = get_logger("graph")


class SolveState(TypedDict):
    job_id: str
    problem_statement: str
    subtasks: list[str]
    solved_subtasks: list[dict]
    approved: bool
    critic_feedback: str
    revision_rounds: int
    final_answer: str
    _provider: str | None  # "ollama", "openai", or None for auto


def _require_success(result: ResultMessage) -> dict:
    if not result.succeeded:
        raise RuntimeError(f"Stage '{result.stage}' failed: {result.error}")
    return result.output


def build_graph(broker: Broker):
    async def dispatch_single(stage: str, payload: dict, job_id: str) -> ResultMessage:
        (reply_token,) = await broker.dispatch(stage, [payload], job_id)
        return await broker.await_result(reply_token)

    async def plan(state: SolveState) -> dict:
        provider = state.get("_provider")
        payload = {"problem_statement": state["problem_statement"]}
        if provider:
            payload["_provider"] = provider
        result = await dispatch_single(PLANNER, payload, state["job_id"])
        return {"subtasks": _require_success(result)["subtasks"]}

    async def execute(state: SolveState) -> dict:
        provider = state.get("_provider")
        payloads = [
            {
                "problem_statement": state["problem_statement"],
                "subtask": subtask,
                "critic_feedback": state.get("critic_feedback", ""),
            }
            for subtask in state["subtasks"]
        ]
        if provider:
            for p in payloads:
                p["_provider"] = provider
        reply_tokens = await broker.dispatch(EXECUTOR, payloads, state["job_id"])
        results = await asyncio.gather(
            *(broker.await_result(token) for token in reply_tokens),
            return_exceptions=True,
        )

        solved_subtasks = []
        for subtask, result in zip(state["subtasks"], results):
            succeeded = isinstance(result, ResultMessage) and result.succeeded
            if succeeded:
                solution = result.output.get("solution")
            else:
                reason = result.error if isinstance(result, ResultMessage) else result
                log_error(
                    logger,
                    "subtask_unsolved",
                    job_id=state["job_id"],
                    subtask=subtask,
                    error=str(reason),
                )
                solution = f"[unsolved: {reason}]"
            solved_subtasks.append(
                {"subtask": subtask, "solution": solution, "succeeded": succeeded}
            )

        return {
            "solved_subtasks": solved_subtasks,
            "revision_rounds": state.get("revision_rounds", 0) + 1,
        }

    async def critic(state: SolveState) -> dict:
        provider = state.get("_provider")
        payload = {
            "problem_statement": state["problem_statement"],
            "solved_subtasks": state["solved_subtasks"],
        }
        if provider:
            payload["_provider"] = provider
        result = await dispatch_single(CRITIC, payload, state["job_id"])
        review = _require_success(result)
        return {"approved": review["approved"], "critic_feedback": review["feedback"]}

    async def aggregate(state: SolveState) -> dict:
        provider = state.get("_provider")
        payload = {
            "problem_statement": state["problem_statement"],
            "solved_subtasks": state["solved_subtasks"],
        }
        if provider:
            payload["_provider"] = provider
        result = await dispatch_single(AGGREGATOR, payload, state["job_id"])
        return {"final_answer": _require_success(result)["final_answer"]}

    def route_after_critic(state: SolveState) -> str:
        needs_revision = not state["approved"]
        rounds_left = state["revision_rounds"] <= settings.max_revision_rounds
        return "execute" if needs_revision and rounds_left else "aggregate"

    builder = StateGraph(SolveState)
    builder.add_node("plan", plan)
    builder.add_node("execute", execute)
    builder.add_node("critic", critic)
    builder.add_node("aggregate", aggregate)

    builder.add_edge(START, "plan")
    builder.add_edge("plan", "execute")
    builder.add_edge("execute", "critic")
    builder.add_conditional_edges(
        "critic", route_after_critic, {"execute": "execute", "aggregate": "aggregate"}
    )
    builder.add_edge("aggregate", END)

    return builder.compile()
