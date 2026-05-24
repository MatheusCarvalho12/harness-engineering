"""Executor agent: solves a single subtask in isolation.

Many executor replicas consume the same queue, so independent subtasks are
worked on in parallel across containers.
"""

from __future__ import annotations

from agents.base import BaseAgent
from config import EXECUTOR


class ExecutorAgent(BaseAgent):
    role = EXECUTOR

    def build_user_prompt(self, payload: dict) -> str:
        prompt = (
            f"Overall problem:\n{payload['problem_statement']}\n\n"
            f"Your assigned subtask:\n{payload['subtask']}"
        )
        critic_feedback = payload.get("critic_feedback")
        if critic_feedback:
            prompt += f"\n\nA reviewer asked you to revise based on:\n{critic_feedback}"
        return prompt

    def parse_output(self, completion_text: str) -> dict:
        return {"solution": completion_text.strip()}
