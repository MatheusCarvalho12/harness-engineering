"""Fast unit tests for the multi-agent system.

Everything external is faked: no Redis, no LLM, no network. We exercise the
pure parsing/prompt-building logic of each agent, the message contracts, the
retry/dead-letter behaviour of BaseAgent, and the LangGraph orchestration with
a deterministic in-memory broker.
"""

from __future__ import annotations

import pytest

from agents import base
from agents.aggregator import AggregatorAgent
from agents.critic import CriticAgent
from agents.executor import ExecutorAgent
from agents.parsing import extract_json
from agents.planner import PlannerAgent
from agents.protocol import ResultMessage, TaskMessage
from config import AGGREGATOR, CRITIC, EXECUTOR, PLANNER, settings


# --------------------------------------------------------------------------- #
# Fakes / fixtures
# --------------------------------------------------------------------------- #


class FakeCompletion:
    """Stand-in for agents.llm.Completion."""

    def __init__(self, text: str, tokens_consumed: int = 7, provider: str = "fake") -> None:
        self.text = text
        self.tokens_consumed = tokens_consumed
        self.provider = provider


class StubBroker:
    """Minimal broker that only needs to satisfy BaseAgent._process_with_retry.

    Records the dead-letter and published-result calls so tests can assert on
    the fault-tolerance path without any Redis.
    """

    def __init__(self) -> None:
        self.dead_letters: list[tuple[TaskMessage, str]] = []
        self.published: list[tuple[str, ResultMessage]] = []

    async def send_to_dead_letter(self, task: TaskMessage, error: str) -> None:
        self.dead_letters.append((task, error))

    async def publish_result(self, reply_token: str, result: ResultMessage) -> None:
        self.published.append((reply_token, result))


def make_agent(agent_class):
    """Build an agent with a stub broker.

    BaseAgent.__init__ reads prompts/<role>.md (which exist in the repo) and
    stores the broker, so a stub broker is enough for the pure methods and the
    retry path.
    """
    return agent_class(StubBroker())


def make_task(stage: str, payload: dict | None = None) -> TaskMessage:
    return TaskMessage(
        job_id="job-1",
        task_id="task-1",
        stage=stage,
        payload=payload or {},
        reply_token="reply-1",
    )


# --------------------------------------------------------------------------- #
# 1. agents.parsing.extract_json
# --------------------------------------------------------------------------- #


def test_extract_json_parses_bare_object():
    assert extract_json('{"subtasks": ["a", "b"]}') == {"subtasks": ["a", "b"]}


def test_extract_json_parses_fenced_block():
    raw = 'Here you go:\n```json\n{"approved": true, "feedback": "ok"}\n```\nDone.'
    assert extract_json(raw) == {"approved": True, "feedback": "ok"}


def test_extract_json_parses_object_embedded_in_prose():
    raw = 'Sure! The result is {"answer": 42} and that is final.'
    assert extract_json(raw) == {"answer": 42}


def test_extract_json_parses_bare_array():
    assert extract_json('["step one", "step two"]') == ["step one", "step two"]


def test_extract_json_raises_when_no_json_present():
    with pytest.raises(ValueError):
        extract_json("there is absolutely nothing parseable here")


# --------------------------------------------------------------------------- #
# 2. agents.protocol round-trips
# --------------------------------------------------------------------------- #


def test_task_message_round_trip_preserves_all_fields():
    original = TaskMessage(
        job_id="job-42",
        task_id="task-7",
        stage=EXECUTOR,
        payload={"subtask": "do the thing", "n": 3},
        reply_token="tok-abc",
        attempt=2,
    )
    restored = TaskMessage.from_json(original.to_json())
    assert restored == original


def test_result_message_round_trip_preserves_all_fields():
    original = ResultMessage(
        job_id="job-42",
        task_id="task-7",
        stage=CRITIC,
        succeeded=False,
        output={"approved": False, "feedback": "needs work"},
        error="boom",
        tokens_consumed=123,
        latency_ms=45.6,
    )
    restored = ResultMessage.from_json(original.to_json())
    assert restored == original


def test_result_message_round_trip_with_defaults():
    original = ResultMessage(
        job_id="j",
        task_id="t",
        stage=PLANNER,
        succeeded=True,
    )
    restored = ResultMessage.from_json(original.to_json())
    assert restored == original
    assert restored.output == {}
    assert restored.error is None
    assert restored.tokens_consumed == 0
    assert restored.latency_ms == 0.0


# --------------------------------------------------------------------------- #
# 3. Pure agent methods (parse_output / build_user_prompt)
# --------------------------------------------------------------------------- #


def test_planner_parse_output_from_object():
    agent = make_agent(PlannerAgent)
    parsed = agent.parse_output('{"subtasks": ["one", "two"]}')
    assert parsed == {"subtasks": ["one", "two"]}


def test_planner_parse_output_from_bare_array():
    agent = make_agent(PlannerAgent)
    parsed = agent.parse_output('["one", 2, "three"]')
    # All entries coerced to str.
    assert parsed == {"subtasks": ["one", "2", "three"]}


def test_planner_build_user_prompt_includes_problem_statement():
    agent = make_agent(PlannerAgent)
    prompt = agent.build_user_prompt({"problem_statement": "Sort a list"})
    assert "Sort a list" in prompt


def test_executor_build_user_prompt_includes_subtask_without_feedback():
    agent = make_agent(ExecutorAgent)
    prompt = agent.build_user_prompt(
        {"problem_statement": "Overall", "subtask": "Write the loop"}
    )
    assert "Write the loop" in prompt
    assert "Overall" in prompt
    assert "reviewer" not in prompt


def test_executor_build_user_prompt_includes_feedback_when_present():
    agent = make_agent(ExecutorAgent)
    prompt = agent.build_user_prompt(
        {
            "problem_statement": "Overall",
            "subtask": "Write the loop",
            "critic_feedback": "Handle the empty case",
        }
    )
    assert "Write the loop" in prompt
    assert "Handle the empty case" in prompt


def test_executor_build_user_prompt_ignores_empty_feedback():
    agent = make_agent(ExecutorAgent)
    prompt = agent.build_user_prompt(
        {"problem_statement": "Overall", "subtask": "Write the loop", "critic_feedback": ""}
    )
    assert "reviewer" not in prompt


def test_executor_parse_output_strips_solution():
    agent = make_agent(ExecutorAgent)
    assert agent.parse_output("  the answer is 42  \n") == {"solution": "the answer is 42"}


def test_critic_parse_output_reads_approved_and_feedback():
    agent = make_agent(CriticAgent)
    parsed = agent.parse_output('{"approved": false, "feedback": "fix edge cases"}')
    assert parsed == {"approved": False, "feedback": "fix edge cases"}


def test_critic_parse_output_defaults_when_keys_missing():
    agent = make_agent(CriticAgent)
    parsed = agent.parse_output("{}")
    assert parsed == {"approved": True, "feedback": ""}


def test_aggregator_parse_output_returns_final_answer():
    agent = make_agent(AggregatorAgent)
    assert agent.parse_output("  final result  ") == {"final_answer": "final result"}


# --------------------------------------------------------------------------- #
# 4. BaseAgent retry / fault tolerance
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_process_with_retry_succeeds_on_first_attempt(monkeypatch):
    agent = make_agent(PlannerAgent)
    calls = {"count": 0}

    async def fake_complete(system_prompt, user_prompt, force_provider=None):
        calls["count"] += 1
        return FakeCompletion('{"subtasks": ["a"]}', tokens_consumed=11)

    monkeypatch.setattr(base.llm, "complete", fake_complete)

    task = make_task(PLANNER, {"problem_statement": "do it"})
    result = await agent._process_with_retry(task)

    assert calls["count"] == 1
    assert result.succeeded is True
    assert result.output == {"subtasks": ["a"]}
    assert result.tokens_consumed == 11
    assert agent._broker.dead_letters == []


@pytest.mark.asyncio
async def test_process_with_retry_exhausts_and_dead_letters(monkeypatch):
    agent = make_agent(PlannerAgent)
    calls = {"count": 0}

    async def always_fails(system_prompt, user_prompt, force_provider=None):
        calls["count"] += 1
        raise RuntimeError("llm exploded")

    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr(base.llm, "complete", always_fails)
    # Keep the test fast: skip the exponential backoff waits entirely.
    monkeypatch.setattr(base.asyncio, "sleep", no_sleep)

    task = make_task(PLANNER, {"problem_statement": "do it"})
    result = await agent._process_with_retry(task)

    assert calls["count"] == settings.retry_max_attempts
    assert result.succeeded is False
    assert result.error is not None
    assert "llm exploded" in result.error
    assert len(agent._broker.dead_letters) == 1
    dead_task, dead_error = agent._broker.dead_letters[0]
    assert dead_task is task
    assert "llm exploded" in dead_error


# --------------------------------------------------------------------------- #
# 5. Graph orchestration with a deterministic fake broker
# --------------------------------------------------------------------------- #


class FakeGraphBroker:
    """Deterministic broker for graph.build_graph.

    dispatch() returns one reply token per payload, each token encoding the
    stage so await_result() can return the canned ResultMessage for that stage.
    """

    CANNED = {
        PLANNER: {"subtasks": ["subtask A", "subtask B"]},
        EXECUTOR: {"solution": "solved"},
        CRITIC: {"approved": True, "feedback": ""},
        AGGREGATOR: {"final_answer": "the consolidated answer"},
    }

    def __init__(self) -> None:
        self.dispatched: list[tuple[str, int]] = []

    async def dispatch(self, stage: str, payloads: list[dict], job_id: str) -> list[str]:
        self.dispatched.append((stage, len(payloads)))
        return [f"{stage}:{index}" for index in range(len(payloads))]

    async def await_result(self, reply_token: str) -> ResultMessage:
        stage = reply_token.split(":", 1)[0]
        return ResultMessage(
            job_id="job-1",
            task_id="task-1",
            stage=stage,
            succeeded=True,
            output=self.CANNED[stage],
        )


@pytest.mark.asyncio
async def test_build_graph_runs_full_pipeline():
    from graph import build_graph

    broker = FakeGraphBroker()
    compiled = build_graph(broker)

    final_state = await compiled.ainvoke(
        {
            "job_id": "job-1",
            "problem_statement": "Build the thing",
        }
    )

    assert final_state["final_answer"] == "the consolidated answer"
    assert final_state["subtasks"] == ["subtask A", "subtask B"]
    assert final_state["approved"] is True
    # One execute round because the critic approved immediately.
    assert final_state["revision_rounds"] == 1
    assert len(final_state["solved_subtasks"]) == 2
    assert all(item["solution"] == "solved" for item in final_state["solved_subtasks"])
    # Executor was fanned out once per subtask in a single dispatch call.
    assert ("executor", 2) in broker.dispatched
