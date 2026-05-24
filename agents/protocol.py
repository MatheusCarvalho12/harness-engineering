"""Message contracts exchanged between the orchestrator and the agent workers.

Both sides serialize these to JSON before pushing onto Redis, so the schema
here is the single agreed-upon wire format for the whole system.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field


@dataclass
class TaskMessage:
    """A unit of work the orchestrator hands to an agent worker."""

    job_id: str
    task_id: str
    stage: str
    payload: dict
    reply_token: str
    attempt: int = 1

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, raw: str) -> "TaskMessage":
        return cls(**json.loads(raw))


@dataclass
class ResultMessage:
    """The outcome a worker publishes back on the reply channel."""

    job_id: str
    task_id: str
    stage: str
    succeeded: bool
    output: dict = field(default_factory=dict)
    error: str | None = None
    tokens_consumed: int = 0
    latency_ms: float = 0.0

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, raw: str) -> "ResultMessage":
        return cls(**json.loads(raw))
