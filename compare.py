"""
Script de comparação: roda o mesmo problema com Ollama (local) e GPT-5 nano (API)
e mostra os resultados lado a lado.

Uso:
    python compare.py "Explique como funciona um cache LRU e dê um exemplo."
"""

from __future__ import annotations

import asyncio
import json
import os
import time

import httpx


def print_comparison(ollama_result: dict, openai_result: dict) -> None:
    """Imprime a comparação formatada."""
    print("=" * 72)
    print("COMPARAÇÃO: Ollama Llama 3.2 3B  vs  GPT-5 nano")
    print("=" * 72)

    for label, result in [("OLLAMA (local)", ollama_result), ("GPT-5 NANO (API)", openai_result)]:
        print(f"\n{'─' * 36}")
        print(f"  {label}")
        print(f"{'─' * 36}")
        print(f"  Latência:          {result['latency_seconds']:.1f}s")
        print(f"  Revisões:          {result['revision_rounds']}")
        print(f"  Subtarefas:        {len(result['subtasks'])}")
        print(f"  Falhas:            {result['failed_subtasks']}")
        print(f"  Resposta (início): {result['final_answer'][:150]}...")

    print(f"\n{'=' * 72}")
    rapido = "Ollama" if ollama_result["latency_seconds"] < openai_result["latency_seconds"] else "GPT-5 nano"
    diferenca = abs(ollama_result["latency_seconds"] - openai_result["latency_seconds"])
    print(f"  Mais rápido: {rapido} ({diferenca:.1f}s de diferença)")
    print(f"{'=' * 72}")


async def solve_with(api_url: str, problem: str, tag: str) -> dict:
    """Envia um problema para a API e retorna o resultado."""
    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(
            f"{api_url}/solve",
            json={"problem_statement": problem},
            headers={"X-Compare-Tag": tag},
        )
        resp.raise_for_status()
        return resp.json()


async def main() -> None:
    import sys

    if len(sys.argv) < 2:
        print("Uso: python compare.py \"<problema>\"")
        sys.exit(1)

    problem = sys.argv[1]

    print(f"\nProblema: {problem}\n")

    # Roda os dois em paralelo
    t0 = time.perf_counter()
    ollama_task = solve_with("http://localhost:8001", problem, "ollama")
    openai_task = solve_with("http://localhost:8002", problem, "openai")

    results = await asyncio.gather(ollama_task, openai_task, return_exceptions=True)

    for i, r in enumerate(results):
        if isinstance(r, Exception):
            print(f"ERRO no {'Ollama' if i == 0 else 'OpenAI'}: {r}")

    if not any(isinstance(r, Exception) for r in results):
        print_comparison(results[0], results[1])


if __name__ == "__main__":
    asyncio.run(main())
