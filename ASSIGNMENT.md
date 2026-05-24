# Engenharia de Contexto e Harness Engineering — Programação Distribuída e Paralela

**Professor:** Fabio Rocha de Araújo
**Disciplina:** Programação Distribuída e Paralela — CC7NA-2026.01
**Pontuação:** 100 pontos
**Data de Entrega:** Amanhã, 18:00 (25/05/2026)
**Equipe:** Até 3 alunos (solo permitido, mesmo escopo)

---

## Instruções Gerais

- Esta atividade deve ser desenvolvida em até 3 alunos
- A atividade deve ser entregue no tempo estabelecido
- A identificação de plágio resulta em anulação da prova (nota 0)
- **TODA ferramenta ou IA utilizada deve ser justificada**

---

## 1. Apresentação e Contextualização

Construir um sistema distribuído ou paralelo que utilize modelos de linguagem como componentes de processamento, aplicando conceitos da disciplina (concorrência, sincronização, troca de mensagens, MapReduce, balanceamento de carga, tolerância a falhas) sobre infraestrutura AWS Academy.

---

## 2. Objetivos de Aprendizagem

- Projetar sistema combinando paralelismo/distribuição com orquestração de LLMs
- Aplicar engenharia de contexto (prompts, tools, memória) em cenários multi-agente
- Avaliar trade-offs entre custo, latência e qualidade em inferência paralela de IA
- Utilizar serviços AWS para arquitetura escalável e tolerante a falhas
- Documentar decisões técnicas e analisar resultados empiricamente

---

## 3. Requisitos Técnicos Mínimos (OBRIGATÓRIOS)

### 4.1 Paralelismo ou Distribuição Real
- Pelo menos **2 nós ou processos** cooperando (paralelismo real)
- Mecanismo de comunicação distribuída: SQS, SNS, sockets, gRPC, Lambda assíncrono ou similar

### 4.2 Integração com Modelo de Linguagem
- Amazon Bedrock OU SLM auto-hospedado

### 4.3 Camada Explícita de Engenharia de Contexto
- System prompts versionados em arquivos separados do código
- Estratégia de chunking/particionamento
- Gestão de histórico/memória entre chamadas
- Definição de ferramentas (tools/function calling)

### 4.4 Métricas e Observabilidade
- Latência por requisição, throughput agregado, tokens consumidos, taxa de erro
- Logs estruturados

### 4.5 Tolerância a Falhas
- Retry com backoff
- Dead Letter Queue para mensagens com falha
- Estratégia de fallback documentada

---

## 4. Temas Disponíveis (ESCOLHER 1)

### TEMA 1 — Pipeline distribuído de análise de documentos
Receber lotes de PDFs e produzir resumos estruturados + extração de entidades + classificação.
Paralelismo: MapReduce (particionamento entre workers, reduce para consolidar).
Contexto: prompts coerentes entre chunks, cross-referencing, JSON schema.
**Conceitos:** MapReduce, particionamento, sincronização, agregação.

### TEMA 2 — Sistema multi-agente para resolução colaborativa
Múltiplos agentes (planejador, executor, crítico, revisor) em containers separados, comunicando via filas.
**Conceitos:** produtor-consumidor, deadlock, starvation, mensageria.

### TEMA 3 — Web scraping inteligente paralelo com extração via IA
Workers paralelos baixam páginas + extratores LLM interpretam HTML.
**Conceitos:** pool de workers, rate limiting, load balancing, backpressure.

### TEMA 4 — Tradutor e localizador distribuído de grandes volumes
Corpus extenso traduzido em paralelo com glossário compartilhado (DynamoDB/Redis).
**Conceitos:** memória compartilhada distribuída, exclusão mútua, consistência eventual.

### TEMA 5 — Sistema de Q&A (RAG distribuído)
Pipeline RAG: indexação paralela de documentos (embeddings) + pool de LLMs para queries.
**Conceitos:** paralelismo de dados, paralelismo de tarefas, cache distribuído.

### TEMA 6 — Moderação de conteúdo em tempo (quase) real
Stream de mensagens classificado por workers paralelos (toxicidade, spam).
**Conceitos:** stream processing, sliding windows, contadores distribuídos, race conditions.

### TEMA 7 — Gerador paralelo de testes e análise de código
Recebe repositório, distribui arquivos entre workers, cada um gera testes/identifica code smells.
**Conceitos:** embarrassingly parallel, agregação, particionamento.

### TEMA 8 — Simulador de enxame de agentes para benchmarking
Framework que executa N instâncias de um mesmo agente LLM em paralelo sobre benchmarks, comparando estratégias de prompting.
**Conceitos:** paralelismo de tarefas, votação majoritária, análise estatística.

---

## 5. Infraestrutura AWS

Serviços sugeridos: EC2, Lambda, SQS/SNS, DynamoDB, S3, Bedrock, ECS/Fargate, CloudWatch, ElastiCache.

### Plano Alternativo (SLM auto-hospedado)
Caso Bedrock não esteja disponível na conta AWS Academy, usar SLM.

**Opções:**
- Ollama em EC2 (GPU ou CPU)
- vLLM em EC2 (avançado)
- SageMaker JumpStart
- Execução local (plano B final)

**Modelos recomendados:** Phi-4 3.8B, Gemma 3, Qwen 2.5/3, Llama 3.2, Mistral 7B, SmolLM3

**BÔNUS:** SLM auto-hospedado = +10 pontos no critério de inovação/complexidade

---

## 6. Entregáveis

1. **Repositório Git** — código, IaC, scripts, README, prompts versionados
2. **Documento Técnico (8-15 páginas)** — arquitetura, justificativas, engenharia de contexto, análise com gráficos, limitações
3. **Apresentação (15-20 min)** — demonstração ao vivo, slides
4. **Relatório Individual (1-2 páginas)** — contribuição e aprendizados

---

## 7. Critérios de Avaliação

| Critério | Peso |
|---|---|
| Corretude e funcionamento | 25% |
| Aplicação de conceitos de PDP | 25% |
| Qualidade da engenharia de contexto e prompts | 20% |
| Análise experimental e métricas | 15% |
| Qualidade da documentação e apresentação | 10% |
| Inovação ou complexidade extra | 5% |
| **Bônus SLM auto-hospedado** | **+10 pts inovação** |
