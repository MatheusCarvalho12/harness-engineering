# Documento Técnico Sistema Multi-Agente Colaborativo

**Disciplina:** Programação Distribuída e Paralela — CC7NA-2026.01
**Tema 2:** Sistema multi-agente para resolução colaborativa
**Equipe:** [Nomes]


## 1. Visão geral

Sistema que recebe um problema via HTTP, decompõe em subtarefas, resolve em paralelo via LLMs, revisa e consolida a resposta. Quatro agentes cooperam via Redis:

1. **Planner** — lê o enunciado e gera 2-5 subtarefas independentes
2. **Executor** — resolve uma subtarefa (escala horizontalmente com N réplicas)
3. **Critic** — revisa as soluções e decide se precisa de nova rodada
4. **Aggregator** — consolida as soluções revisadas em resposta única

**Dois planos separados:**
- **Control plane (LangGraph):** descreve a ordem dos estágios + aresta condicional de revisão. Vive no gateway FastAPI.
- **Data plane (Redis + workers):** chamadas LLM acontecem em containers separados, comunicação exclusivamente por filas Redis.


## 2. Conceitos de PDP aplicados

| Conceito | Implementação |
|---|---|
| **Produtor-consumidor** | Orquestrador faz RPUSH na fila do estágio; workers fazem BLPOP |
| **Balanceamento de carga** | N réplicas do executor consomem a mesma fila (competing consumers) |
| **Troca de mensagens** | JSON serializado sobre listas Redis. Par fila + reply forma RPC |
| **Paralelismo real** | Fan-out: todas subtarefas despachadas de uma vez, resolvidas em containers diferentes |
| **Deadlock** | Sem locks — toda espera tem timeout de 180s |
| **Starvation** | Filas FIFO. Loop de revisão limitado por MAX_REVISION_ROUNDS |


## 3. Protocolo de mensagens

### TaskMessage (orquestrador → worker)

| Campo | Tipo | Descrição |
|---|---|---|
| `job_id` | str | Identifica a requisição /solve |
| `task_id` | str | Identifica esta unidade de trabalho |
| `stage` | str | planner / executor / critic / aggregator |
| `payload` | dict | Dados específicos do estágio |
| `reply_token` | str | Canal de resposta único |
| `attempt` | int | Número da tentativa |

### ResultMessage (worker → orquestrador)

| Campo | Tipo | Descrição |
|---|---|---|
| `succeeded` | bool | Se o estágio concluiu com sucesso |
| `output` | dict | Saída estruturada |
| `error` | str \| None | Mensagem de erro |
| `tokens_consumed` | int | Tokens da chamada LLM |
| `latency_ms` | float | Latência da chamada no worker |

### Filas

- `harness:queue:<stage>` — fila de trabalho por estágio
- `harness:reply:<token>` — resposta por tarefa (RPC)
- `harness:dlq` — dead letter queue


## 4. Ciclo de vida de uma requisição

```
START → plan → execute → critic → (aprovado?) → aggregate → END
                       ↑            |
                       └─(revisar)───┘
```

1. **Recepção.** Valida o corpo (1-8000 chars), gera job_id, invoca o grafo
2. **Plan.** Despacha 1 tarefa para planner. Retorna lista de subtarefas
3. **Execute (fan-out).** Despacha todas subtarefas de uma vez. Workers competem pela fila. `asyncio.gather` aguarda todas
4. **Critic.** Avalia o conjunto. Se aprovou → vai para aggregate. Se não → volta para execute com feedback
5. **Aggregate.** Consolida resposta final
6. **Resposta.** Devolve job_id, final_answer, subtasks, latência. Erro no pipeline → 502 Bad Gateway


## 5. Engenharia de contexto

### System prompts versionados

Cada agente carrega o prompt de `prompts/<role>.md` — fora do código, versionados no Git. A lógica do agente só monta o user prompt e interpreta a saída.

### Contratos de saída

| Agente | Formato | Motivo |
|---|---|---|
| Planner | JSON `{"subtasks": [...]}` | Parseável para fan-out |
| Executor | Texto livre | Resposta para consumo humano |
| Critic | JSON `{"approved": bool, "feedback": str}` | Decisão de roteamento tipada |
| Aggregator | Texto livre | Resposta final para o usuário |

### Tolerância a JSON mal formado

Modelos pequenos (Llama 3.2 3B) frequentemente embrulham JSON em prosa. `parsing.py: extract_json` tenta: cerca ```json → texto cru → primeiro par `{}` ou `[]` balanceado. Se nada funciona, levanta ValueError → aciona retry.

### Estado entre chamadas

`SolveState` (TypedDict no LangGraph) carrega `critic_feedback` de volta para o executor na revisão — sem persistência externa por requisição.

### Provedor selecionável

O campo `_provider` no `SolveState` (ollama / openai / None) é propagado para todas as task payloads. O `BaseAgent` lê `payload["_provider"]` e passa para `llm.complete(force_provider=...)`, que:
- `"ollama"`: chama só Ollama, sem fallback
- `"openai"`: chama só GPT-5 nano direto
- `None` / `"auto"`: tenta Ollama, cai pra OpenAI em erro


## 6. Observabilidade

### LangSmith

Tracing automático via env vars (`LANGSMITH_TRACING`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT=Harness-cesupa`). O dashboard expõe:
- Run tree completa do LangGraph
- Cada chamada LLM com modelo, provedor, tokens, latência
- Metadados por run: job_id, provider
- Comparação lado a lado via `/compare` (duas run trees independentes)

### Logs estruturados

Todos os componentes emitem JSON no stdout: `timestamp`, `level`, `component`, `message`, mais contexto (`job_id`, `latency_ms`, etc.). Funciona offline, sem dependência do LangSmith.


## 7. Tolerância a falhas

### Retry com backoff exponencial

Centralizado em `BaseAgent._process_with_retry`:
```
tentativa 1 → falha → espera 1s
tentativa 2 → falha → espera 2s  
tentativa 3 → falha → DLQ
```

### Dead Letter Queue

Mensagens que esgotaram tentativas vão pra `harness:dlq` com o erro anexado. Saem da fila de trabalho em vez de reprocessar eternamente.

### Fallback de LLM

`llm.py`: primário = Ollama. Em exceção → registra log → tenta GPT-5 nano (se `OPENAI_API_KEY` configurada). Sem chave → propaga erro para retry/DLQ.

### Degradação graciosa

No fan-out, subtarefa que falha vira `"[unsolved: <erro>]"`. Critic e aggregator continuam com o que deu certo.


## 8. Comparação de provedores

### Benchmark (problema: "Explique cache LRU")

| Métrica | Ollama Llama 3.2 3B | GPT-5 nano |
|---|---|---|
| Latência | ~68s | ~12s |
| Custo | 0 (local) | $0.05/1M tokens input |
| Offline | Sim | Não (requer internet) |
| RAM | ~2 GB | 0 (servidor) |
| Provider flag | `provider=ollama` | `provider=openai` |

O endpoint `POST /compare` roda ambos em paralelo e retorna os dois resultados com métricas independentes.

### Trade-offs

- **Local vs cloud:** Ollama é gratuito e offline, mas 5x mais lento. GPT-5 nano é rápido e pago. O modo `auto` combina os dois: tenta local primeiro, cai pra API se falhar.
- **Preço GPT-5 nano:** $0.05/1M tokens input, $0.25/1M tokens output. Uma requisição típica (~2K tokens) custa centavos.
- **Latência vs qualidade:** modelos pequenos (3B) são mais rápidos que modelos grandes (70B+) mas menos precisos. A etapa de crítica/revisão mitiga parte da perda de qualidade.


## 9. Limitações

- **Contagem de tokens aproximada.** Sem `usage_metadata` do provedor, estima por caracteres/4
- **Uma rodada de revisão por padrão.** Configurável via `MAX_REVISION_ROUNDS`
- **Decomposição depende do planner.** Problemas sequenciais não se beneficiam do paralelismo
- **Estado por requisição.** Sem histórico entre chamadas
- **RPC via listas.** Suficiente para request-reply, mas sem broadcast


## 10. Desenvolvimento

**Execução:** Claude Opus 4.6 foi usado para gerar e revisar o código, testes, Dockerfiles, prompts e documentação.

**Direção:** todas as decisões arquiteturais, escolha de tema 2, definição de requisitos, planejamento das etapas e validação dos resultados foram da equipe. A IA atuou como ferramenta de execução e aceleração do desenvolvimento, não como fonte das decisões de projeto.


## 11. Ferramentas (justificativa obrigatória)

| Ferramenta | Justificativa |
|---|---|
| **LangGraph + LangChain** | Orquestração declarativa do fluxo multi-agente com suporte nativo a grafo + tracing |
| **LangSmith** | Dashboard de run trees para apresentar em sala; tracing automático sem instrumentação extra |
| **Ollama + Llama 3.2 3B** | SLM auto-hospedado local (plano B do enunciado, sem dependência AWS) = bônus +10 pts inovação |
| **GPT-5 nano** | Comparação de desempenho com modelo de API; fallback automático quando Ollama falha |
| **FastAPI + Uvicorn** | Gateway REST com validação na borda via Pydantic |
| **Redis** | Broker de mensagens entre processos; filas, RPC e DLQ com primitivas simples |
| **Claude Opus 4.6** | Assistência na execução do desenvolvimento (código, testes, docs) |
