"""Entry point for an agent worker container.

The role is chosen by the AGENT_ROLE environment variable, so a single image
serves all four agents — Docker Compose just sets a different role per service.
"""

from __future__ import annotations

import asyncio
import os
import sys

from agents import AGENT_REGISTRY
from agents.broker import Broker
from config import AGENT_ROLES


async def main() -> None:
    role = os.environ.get("AGENT_ROLE", "")
    if role not in AGENT_REGISTRY:
        sys.exit(f"AGENT_ROLE must be one of {AGENT_ROLES}, got {role!r}")

    broker = Broker.connect()
    agent = AGENT_REGISTRY[role](broker)
    try:
        await agent.run_forever()
    finally:
        await broker.close()


if __name__ == "__main__":
    asyncio.run(main())
