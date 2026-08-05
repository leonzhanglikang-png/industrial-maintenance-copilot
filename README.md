# Industrial Maintenance Copilot

An end-to-end portfolio project that combines retrieval-augmented generation,
tool-using agents, backend engineering, evaluation, and deployment in an
industrial IoT maintenance scenario.

## Project outcome

The completed application will:

1. ingest maintenance manuals and historical incident records;
2. answer maintenance questions with traceable citations;
3. query structured fault history and analyze sensor readings through tools;
4. generate an evidence-based diagnosis and inspection plan;
5. report retrieval, answer-quality, latency, and cost metrics;
6. run locally and in a deployed environment from reproducible configuration.

## Current milestone

Milestone 0 establishes a tested API skeleton and freezes the project scope.
See `docs/ROADMAP.md` for the implementation sequence.

Progress is recorded in `docs/DEVLOG.md`. Each completed milestone is committed
separately so reviewers can follow the engineering decisions and test evidence.

## Local setup

```bash
cp .env.example .env
uv sync
uv run pytest
uv run uvicorn backend.app.main:app --reload
```

After startup:

- API health check: `http://127.0.0.1:8000/api/v1/health`
- Interactive API docs: `http://127.0.0.1:8000/docs`

## Repository layout

```text
backend/        FastAPI application and domain services
data/           versioned samples and ignored runtime data
docs/           scope, architecture, decisions, and roadmap
frontend/       interactive demo UI (added in the application stage)
tests/          automated tests
```

## Project rule

Every feature must be demonstrable, testable, and tied to a measurable result.
A framework name alone does not count as a feature.

