# Project brief

## Problem

Maintenance engineers often search across long manuals, scattered incident
records, and sensor exports before deciding what to inspect. Generic chatbots
can produce plausible but unsupported advice, which is unsafe in a maintenance
workflow.

## User

The primary user is a junior maintenance engineer responsible for connected
industrial equipment. The user needs fast evidence retrieval and a structured
inspection plan, not autonomous control of machinery.

## Core user story

Given a fault description and optional recent sensor readings, the assistant:

1. retrieves relevant manual passages;
2. looks up similar historical incidents;
3. invokes an analysis tool when structured readings are supplied;
4. proposes likely causes and an ordered inspection plan;
5. cites its evidence and states uncertainty.

## In scope

- PDF, Markdown, and text ingestion;
- metadata-aware dense and lexical retrieval;
- reranking and source citations;
- structured fault-history lookup;
- deterministic sensor-summary tool;
- agent orchestration with visible tool traces;
- offline retrieval and answer evaluation;
- API, demo UI, containerization, logging, and deployment.

## Out of scope

- controlling real equipment;
- safety-critical automated decisions;
- training a foundation model;
- accepting arbitrary executable uploads;
- claiming diagnostic certainty.

## Portfolio value

This project is designed to demonstrate AI application engineering and backend
engineering. It deliberately includes evaluation and operations work so it is
more than a thin chat interface around an LLM API.

