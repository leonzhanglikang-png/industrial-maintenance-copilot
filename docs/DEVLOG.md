# Development log

This log records meaningful progress, decisions, verification, and the next
engineering step. Git commits remain the source of truth for code changes.

## 2026-08-05 - Project foundation

### Completed

- Defined the industrial IoT maintenance user problem and safety boundary.
- Chose a provider-neutral RAG and bounded-agent architecture.
- Created the FastAPI application factory and configuration layer.
- Added a typed health endpoint and its first automated test.
- Documented the milestone roadmap and measurable exit conditions.

### Verification

- `uv run pytest`: 1 test passed.
- `uv run ruff check .`: configured to check project code while excluding local caches.

### Decision

The first retrieval milestone will preserve page and source metadata from the
start. Citation support will not be added as a cosmetic feature at the end.

### Next

Define the document/chunk domain models and implement text and Markdown
ingestion before introducing embeddings or an LLM dependency.

