"""FastAPI gateway exposing the multi-agent solver.

The gateway owns one compiled LangGraph and a single broker connection, both
created at startup and reused across requests. Routes stay thin: validate the
request, run the graph, shape the response.
"""

from __future__ import annotations

import os
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from agents.broker import Broker
from config import settings
from graph import build_graph
from langsmith import Client as LangSmithClient
from logging_config import get_logger, log_error, log_event

logger = get_logger("api")


class SolveRequest(BaseModel):
    problem_statement: str = Field(min_length=1, max_length=8000)
    provider: str = Field(
        default="auto",
        pattern=r"^(auto|ollama|openai)$",
        description="'auto' tenta Ollama com fallback OpenAI, "
        "'ollama' força só local, 'openai' força só API",
    )


class SolvedSubtask(BaseModel):
    subtask: str
    solution: str
    succeeded: bool


class SolveResponse(BaseModel):
    job_id: str
    final_answer: str
    subtasks: list[str]
    solved_subtasks: list[SolvedSubtask]
    failed_subtasks: int
    revision_rounds: int
    latency_seconds: float
    provider: str


class CompareResponse(BaseModel):
    ollama: SolveResponse | None
    openai: SolveResponse | None
    problem_statement: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    broker = Broker.connect()
    app.state.broker = broker
    app.state.graph = build_graph(broker)

    # LangSmith: tracing is automatic via env vars, this is just a startup check
    ls_api_key = os.environ.get("LANGSMITH_API_KEY", "")
    if ls_api_key:
        try:
            LangSmithClient(api_key=ls_api_key)
            log_event(logger, "langsmith_connected")
        except Exception:
            log_error(logger, "langsmith_connect_failed")
    else:
        log_event(logger, "langsmith_disabled_set_LANGSMITH_API_KEY")

    log_event(logger, "api_started")
    try:
        yield
    finally:
        await broker.close()


app = FastAPI(title="Harness Engineering Multi-Agent Solver", lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    try:
        reachable = await app.state.broker.ping()
    except Exception:
        reachable = False
    return {"status": "ok" if reachable else "degraded", "broker": reachable}


def _build_solve_response(
    final_state: dict, started_at: float
) -> SolveResponse:
    solved_subtasks = final_state["solved_subtasks"]
    return SolveResponse(
        job_id=final_state["job_id"],
        final_answer=final_state["final_answer"],
        subtasks=final_state["subtasks"],
        solved_subtasks=solved_subtasks,
        failed_subtasks=sum(
            1 for item in solved_subtasks if not item["succeeded"]
        ),
        revision_rounds=final_state["revision_rounds"],
        latency_seconds=time.perf_counter() - started_at,
        provider=final_state.get("_provider") or "auto",
    )


@app.post("/solve")
async def solve(request: SolveRequest) -> SolveResponse:
    job_id = uuid.uuid4().hex
    started_at = time.perf_counter()
    log_event(logger, "solve_received", job_id=job_id, provider=request.provider)

    try:
        provider_value = (
            None if request.provider == "auto" else request.provider
        )
        final_state = await app.state.graph.ainvoke(
            {
                "job_id": job_id,
                "problem_statement": request.problem_statement,
                "revision_rounds": 0,
                "_provider": provider_value,
            }
        )
        response = _build_solve_response(final_state, started_at)
        log_event(
            logger,
            "solve_completed",
            job_id=job_id,
            latency_seconds=round(response.latency_seconds, 2),
            failed_subtasks=response.failed_subtasks,
            provider=response.provider,
        )
        return response
    except Exception as error:
        latency_seconds = time.perf_counter() - started_at
        log_error(logger, "solve_failed", exc=error, job_id=job_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The agent pipeline could not complete this request.",
        ) from error


@app.post("/compare")
async def compare(request: SolveRequest) -> CompareResponse:
    """Runs the same problem with both Ollama and GPT-5 nano side by side."""
    log_event(logger, "compare_received")

    async def run(provider: str) -> SolveResponse | None:
        try:
            job_id = uuid.uuid4().hex
            started_at = time.perf_counter()
            final_state = await app.state.graph.ainvoke(
                {
                    "job_id": job_id,
                    "problem_statement": request.problem_statement,
                    "revision_rounds": 0,
                    "_provider": provider,
                }
            )
            return _build_solve_response(final_state, started_at)
        except Exception as error:
            log_error(
                logger, f"compare_{provider}_failed", exc=error
            )
            return None

    import asyncio

    ollama_result, openai_result = await asyncio.gather(
        run("ollama"), run("openai")
    )

    return CompareResponse(
        ollama=ollama_result,
        openai=openai_result,
        problem_statement=request.problem_statement,
    )
