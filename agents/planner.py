"""Planner agent: decomposes a problem statement into ordered subtasks."""

from __future__ import annotations

from agents.base import BaseAgent
from agents.parsing import extract_json
from config import PLANNER


class PlannerAgent(BaseAgent):
    role = PLANNER

    def build_user_prompt(self, payload: dict) -> str:
        return f"Problem statement:\n{payload['problem_statement']}"

    def parse_output(self, completion_text: str) -> dict:
        parsed = extract_json(completion_text)
        subtasks = parsed["subtasks"] if isinstance(parsed, dict) else parsed
        return {"subtasks": [str(subtask) for subtask in subtasks]}
