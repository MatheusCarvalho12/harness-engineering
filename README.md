# Harness Engineering Sistema Multi-Agente Colaborativo

**Disciplina:** Programação Distribuída e Paralela — CC7NA-2026.01
**Tema 2:** Sistema multi-agente para resolução colaborativa

## O que é

Gateway FastAPI que orquestra 4 agentes via LangGraph + Redis. Cada agente roda em container Docker separado. O executor escala horizontalmente (várias réplicas processam subtarefas em paralelo).

**Fluxo:** `POST /solve` → Planner → Executor × N → Critic → (revisa?) → Aggregator → resposta final

## Stack

| Componente | O que faz |
|---|---|
| **LangGraph** | Orquestra o grafo de agentes (control plane) |
| **Redis** | Filas + RPC + DLQ entre os processos (data plane) |
| **Ollama (Llama 3.2 3B)** | LLM local, gratuito, offline |
| **GPT-5 nano (fallback)** | LLM via API, ~5x mais rápido, $0.05/1M tokens |
| **FastAPI** | Gateway REST |
| **Docker Compose** | Infra como código |
| **LangSmith** | Tracing turno a turno de cada requisição |
| **Claude Opus 4.6** | Executou o desenvolvimento (ideias e decisões: equipe) |

## Pré-requisitos

```bash
docker --version
ollama pull llama3.2:3b
# Opcional: OPENAI_API_KEY no .env para fallback/comparação
```

## Como rodar

```bash
git clone https://github.com/MatheusCarvalho12/harness-engineering
cd harness-engineering
cp .env.example .env
docker compose up --build --scale executor=3
curl http://localhost:8000/health
```

## Uso da API

### `POST /solve` resolver um problema

```bash
curl -X POST http://localhost:8000/solve \
  -H "Content-Type: application/json" \
  -d '{"problem_statement": "Explique cache LRU com exemplo em Python."}'
```

**Parâmetros:**

`problem_statement` (obrigatório, 1-8000 chars) / `provider` (opcional: `"auto"`, `"ollama"`, `"openai"`)

**Resposta:** `job_id`, `final_answer`, `subtasks`, `solved_subtasks`, `failed_subtasks`, `revision_rounds`, `latency_seconds`, `provider`

### `POST /compare` comparar Ollama vs GPT-5 nano

```bash
curl -X POST http://localhost:8000/compare \
  -H "Content-Type: application/json" \
  -d '{"problem_statement": "Explique cache LRU."}'
```

Retorna dois resultados idênticos ao `/solve`, um de cada provedor.

### `GET /health`

```bash
curl http://localhost:8000/health
# {"status": "ok", "broker": true}
```

## Provedores

| provider | Ollama | GPT-5 nano |
|---|---|---|
| `"auto"` | tenta primeiro | fallback se erro |
| `"ollama"` | obrigatório | não usa |
| `"openai"` | não usa | obrigatório |

Benchmark típico: Ollama ~68s / gratuito / offline. GPT-5 nano ~12s / ~$0.001 por req / online.

## LangSmith

Projeto **Harness-cesupa**. Cada requisição gera run trees. O `/compare` gera duas independentes com metadados de provider. Dashboard em [smith.langchain.com](https://smith.langchain.com).

## Tolerância a falhas

- Retry exponencial: 3 tentativas (1s → 2s → 4s)
- DLQ: mensagens que falharam vão pra `harness:dlq`
- Fallback de LLM: Ollama → GPT-5 nano automático
- Degradação graciosa: subtarefa que falha vira `"[unsolved: ...]"`
- Timeout de 180s por estágio (sem deadlock)

## Arquitetura

```
POST /solve  →  FastAPI + LangGraph  →  Redis  →  workers (planner, executor ×N, critic, aggregator)
                                                  │
                                             Ollama ← fallback → GPT-5 nano
```

## Testes

```bash
pytest tests/ -v    # 21/21 passando
```

## Desenvolvimento

**Execução:** Claude Opus 4.6 — código, testes, Dockerfiles, prompts e documentação foram gerados e revisados por IA.

**Direção:** todas as ideias arquiteturais, decisões técnicas, escolha de tema e planejamento foram da equipe. A IA foi ferramenta de execução, não de concepção.

## Ferramentas usadas

- **LangGraph + LangChain** — orquestração declarativa do fluxo multi-agente
- **LangSmith** — tracing automático para apresentação
- **Ollama (Llama 3.2 3B)** — SLM auto-hospedado (bônus inovação +10 pts)
- **GPT-5 nano** — comparação de desempenho e fallback automático
- **FastAPI + Uvicorn** — gateway REST
- **Redis** — broker de mensagens entre processos
- **Claude Opus 4.6** — assistência na execução
