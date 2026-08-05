# Architecture

## Target request flow

```text
Web demo
   |
FastAPI application
   |
Agent orchestrator
   |-- knowledge search tool ---> hybrid retriever ---> vector store
   |-- incident lookup tool ----> relational database
   |-- sensor analysis tool ----> deterministic Python analysis
   |
Answer composer ---> cited response + tool trace + confidence signals
   |
Evaluation and observability store
```

## Planned technology choices

- API: FastAPI and Pydantic
- Relational data: PostgreSQL
- Vector and lexical retrieval: Qdrant with dense and sparse representations
- LLM access: provider-neutral OpenAI-compatible client
- Agent workflow: explicit state graph rather than a free-running agent loop
- Demo UI: Streamlit initially
- Packaging: `uv`
- Deployment: Docker images and Compose for local infrastructure
- Quality: Pytest, Ruff, structured logs, evaluation scripts

## Design principles

1. Retrieval and tool execution must be independently testable.
2. Agent decisions must be visible in the demo.
3. Answers must distinguish evidence from model inference.
4. Safety-critical actions must always remain recommendations for a human.
5. Provider-specific code stays behind small interfaces.

