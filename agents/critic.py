"""Critic agent: reviews the collected subtask solutions and decides whether
they are good enough or need another execution round."""

from __future__ import annotations

from agents.base import BaseAgent
from agents.parsing import extract_json
from config import CRITIC


class CriticAgent(BaseAgent):
    role = CRITIC

    def build_user_prompt(self, payload: dict) -> str:
        solutions = "\n\n".join(
            f"Subtask: {item['subtask']}\nSolution: {item['solution']}"
            for item in payload["solved_subtasks"]
        )
        return (
            f"Overall problem:\n{payload['problem_statement']}\n\n"
            f"Proposed solutions:\n{solutions}"
        )

    def parse_output(self, completion_text: str) -> dict:
        parsed = extract_json(completion_text)
        return {
            "approved": bool(parsed.get("approved", True)),
            "feedback": str(parsed.get("feedback", "")),
        }
