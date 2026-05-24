# Harness Engineering — Programação Distribuída e Paralela

## Project Overview
Sistema multi-agente para resolução colaborativa usando LangGraph.
Entrega: Amanhã 25/05/2026 18:00. Nota alvo: 10/10.

## Architecture
- **LangGraph StateGraph** orquestrando 3-4 agentes especializados
- **Redis** como message broker e state store entre agentes
- **Docker Compose**: cada agente em container separado (paralelismo real)
- **LLM**: Ollama local (modelo leve tipo Llama 3.2 1B/3B ou Phi-4) + suporte a OpenAI API
- **FastAPI** como API gateway REST

## Agents
1. **Planner Agent** — recebe o problema, decompõe em subtarefas
2. **Executor Agent** — executa cada subtarefa chamando o LLM
3. **Critic Agent** — revisa e valida resultados, sugere correções
4. **Aggregator Agent** — consolida resposta final

## Key Requirements (from ASSIGNMENT.md)
- 2+ processos cooperando (check — Docker containers)
- Comunicação distribuída via Redis/pub-sub (check)
- Integração com LLM (check — Ollama local)
- System prompts versionados em arquivos separados (prompts/)
- Gestão de memória/estado entre chamadas (LangGraph + Redis)
- Métricas: latência, throughput, tokens consumidos, taxa de erro
- Logs estruturados (JSON)
- Retry com backoff, DLQ, fallback
- IaC: Docker Compose

## Code Style
- Python puro, tipado, módulos separados por responsabilidade
- Nomes de variáveis DESCRITIVOS (nada de `x`, `tmp`, `func1`)
- Máximo de clareza — o código vai ser apresentado em sala
- Comentários só onde a intenção não é óbvia
- Quanto menos código, melhor — sem abstrações desnecessárias

## File Structure Expected
```
/Volumes/CORSAIR/dev/cesupa/harness-engineering/
├── agents/
│   ├── __init__.py
│   ├── planner.py
│   ├── executor.py
│   ├── critic.py
│   └── aggregator.py
├── prompts/
│   ├── planner.md
│   ├── executor.md
│   ├── critic.md
│   └── aggregator.md
├── metrics/
│   ├── __init__.py
│   └── collector.py
├── docker/
│   ├── Dockerfile.agent
│   ├── Dockerfile.api
│   └── docker-compose.yml
├── tests/
│   └── test_agents.py
├── docs/
│   └── architecture.md
├── main.py
├── graph.py
├── requirements.txt
├── CLAUDE.md (this file)
├── ASSIGNMENT.md (full assignment spec)
├── README.md
└── .env.example
```

## Tech Stack
- Python 3.11+
- LangGraph + LangChain
- Redis (redis-py)
- FastAPI + uvicorn
- Ollama (local LLM)
- httpx (for Ollama/OpenAI API calls)
- Docker + Docker Compose
- langsmith (tracing + observability)

## Commands
- `docker compose up --build` — run full system
- `curl http://localhost:8000/solve` — API endpoint
- `pytest tests/` — run tests

## Always check for latest
When implementing, search the internet for:
- Latest LangGraph patterns (StateGraph, node/edge API)
- Latest LangChain patterns (ChatOllama, ChatOpenAI)
- Best practices for multi-agent orchestration
