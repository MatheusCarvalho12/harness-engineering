"""Base class for every agent worker.

Subclasses only declare how to turn a task payload into an LLM prompt and how
to parse the response. Everything operational — the consume loop, retry with
exponential backoff, structured logging, metrics, and dead-lettering — lives
here so all four agents behave identically under failure.
"""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from pathlib import Path

from agents import llm
from agents.broker import Broker
from agents.protocol import ResultMessage, TaskMessage
from config import settings
from logging_config import get_logger, log_error, log_event

PROMPTS_DIRECTORY = Path(__file__).resolve().parent.parent / "prompts"


class BaseAgent(ABC):
    role: str

    def __init__(self, broker: Broker) -> None:
        self._broker = broker
        self._logger = get_logger(self.role)
        self._system_prompt = (PROMPTS_DIRECTORY / f"{self.role}.md").read_text()

    @abstractmethod
    def build_user_prompt(self, payload: dict) -> str:
        """Render the task payload into the user message for the LLM."""

    @abstractmethod
    def parse_output(self, completion_text: str) -> dict:
        """Turn the raw LLM text into the structured output for this stage."""

    async def _attempt_once(self, task: TaskMessage) -> ResultMessage:
        started_at = time.perf_counter()
        completion = await llm.complete(
            self._system_prompt,
            self.build_user_prompt(task.payload),
            force_provider=task.payload.get("_provider"),
        )
        latency_ms = (time.perf_counter() - started_at) * 1000.0
        return ResultMessage(
            job_id=task.job_id,
            task_id=task.task_id,
            stage=self.role,
            succeeded=True,
            output=self.parse_output(completion.text),
            tokens_consumed=completion.tokens_consumed,
            latency_ms=latency_ms,
        )

    async def _process_with_retry(self, task: TaskMessage) -> ResultMessage:
        delay_seconds = settings.retry_base_delay_seconds
        last_error: Exception | None = None

        for attempt in range(1, settings.retry_max_attempts + 1):
            try:
                result = await self._attempt_once(task)
                log_event(
                    self._logger,
                    "task_succeeded",
                    job_id=task.job_id,
                    task_id=task.task_id,
                    attempt=attempt,
                    latency_ms=round(result.latency_ms, 1),
                    tokens=result.tokens_consumed,
                )
                return result
            except Exception as error:
                last_error = error
                log_error(
                    self._logger,
                    "task_attempt_failed",
                    exc=error,
                    job_id=task.job_id,
                    task_id=task.task_id,
                    attempt=attempt,
                )
                if attempt < settings.retry_max_attempts:
                    await asyncio.sleep(delay_seconds)
                    delay_seconds *= settings.retry_backoff_multiplier

        log_error(
            self._logger,
            "task_dead_lettered",
            exc=last_error,
            job_id=task.job_id,
            task_id=task.task_id,
            attempts=settings.retry_max_attempts,
        )
        try:
            await self._broker.send_to_dead_letter(task, str(last_error))
        except Exception as dead_letter_error:
            log_error(
                self._logger,
                "dead_letter_write_failed",
                exc=dead_letter_error,
                job_id=task.job_id,
                task_id=task.task_id,
            )
        return ResultMessage(
            job_id=task.job_id,
            task_id=task.task_id,
            stage=self.role,
            succeeded=False,
            error=str(last_error),
        )

    async def run_forever(self) -> None:
        log_event(self._logger, "agent_started", role=self.role)
        while True:
            try:
                task = await self._broker.consume(self.role)
                result = await self._process_with_retry(task)
                await self._broker.publish_result(task.reply_token, result)
            except Exception as loop_error:
                log_error(self._logger, "consume_loop_error", exc=loop_error)
                await asyncio.sleep(settings.retry_base_delay_seconds)
