"""Aggregator agent: consolidates the reviewed subtask solutions into one
coherent final answer for the original problem."""

from __future__ import annotations

from agents.base import BaseAgent
from config import AGGREGATOR


class AggregatorAgent(BaseAgent):
    role = AGGREGATOR

    def build_user_prompt(self, payload: dict) -> str:
        solutions = "\n\n".join(
            f"Subtask: {item['subtask']}\nSolution: {item['solution']}"
            for item in payload["solved_subtasks"]
        )
        return (
            f"Original problem:\n{payload['problem_statement']}\n\n"
            f"Reviewed subtask solutions:\n{solutions}"
        )

    def parse_output(self, completion_text: str) -> dict:
        return {"final_answer": completion_text.strip()}
