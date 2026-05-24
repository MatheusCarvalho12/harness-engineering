"""Agent workers and the registry that maps a role name to its implementation."""

from agents.aggregator import AggregatorAgent
from agents.base import BaseAgent
from agents.critic import CriticAgent
from agents.executor import ExecutorAgent
from agents.planner import PlannerAgent
from config import AGGREGATOR, CRITIC, EXECUTOR, PLANNER

AGENT_REGISTRY: dict[str, type[BaseAgent]] = {
    PLANNER: PlannerAgent,
    EXECUTOR: ExecutorAgent,
    CRITIC: CriticAgent,
    AGGREGATOR: AggregatorAgent,
}

__all__ = ["AGENT_REGISTRY", "BaseAgent"]
