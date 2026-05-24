"""Redis-backed message broker implementing the distributed communication layer.

Work travels on per-stage queues (Redis lists). Multiple worker replicas
BLPOP the same queue, which gives competing-consumer load balancing for free.
Each task carries a unique reply token; the worker pushes its result onto the
matching reply list, turning the queue pair into a simple RPC channel. Messages
that exhaust their retries land in a dead-letter queue for inspection.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict

from redis.asyncio import Redis

from agents.protocol import ResultMessage, TaskMessage
from config import DEAD_LETTER_QUEUE, queue_name, reply_channel, settings


class Broker:
    def __init__(self, redis_client: Redis) -> None:
        self._redis = redis_client

    @classmethod
    def connect(cls) -> "Broker":
        return cls(Redis.from_url(settings.redis_url, decode_responses=True))

    async def close(self) -> None:
        await self._redis.aclose()

    async def ping(self) -> bool:
        return await self._redis.ping()

    async def dispatch(self, stage: str, payloads: list[dict], job_id: str) -> list[str]:
        reply_tokens: list[str] = []
        for payload in payloads:
            reply_token = uuid.uuid4().hex
            task = TaskMessage(
                job_id=job_id,
                task_id=uuid.uuid4().hex,
                stage=stage,
                payload=payload,
                reply_token=reply_token,
            )
            await self._redis.rpush(queue_name(stage), task.to_json())
            reply_tokens.append(reply_token)
        return reply_tokens

    async def await_result(self, reply_token: str) -> ResultMessage:
        timeout = settings.result_wait_timeout_seconds
        popped = await self._redis.blpop([reply_channel(reply_token)], timeout=timeout)
        if popped is None:
            raise TimeoutError(
                f"No result for reply token {reply_token} within {timeout}s"
            )
        _, raw_result = popped
        return ResultMessage.from_json(raw_result)

    async def consume(self, stage: str) -> TaskMessage:
        _, raw_task = await self._redis.blpop([queue_name(stage)])
        return TaskMessage.from_json(raw_task)

    async def publish_result(self, reply_token: str, result: ResultMessage) -> None:
        await self._redis.rpush(reply_channel(reply_token), result.to_json())

    async def send_to_dead_letter(self, task: TaskMessage, error: str) -> None:
        record = {"task": asdict(task), "error": error}
        await self._redis.rpush(DEAD_LETTER_QUEUE, json.dumps(record))
