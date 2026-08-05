# Implementation roadmap

## Milestone 0 - foundation

- freeze scope and architecture;
- create a tested API skeleton;
- define configuration without committing secrets.

Exit condition: the health endpoint passes an automated test.

## Milestone 1 - ingestion and baseline retrieval

- define document and chunk schemas;
- parse PDF, Markdown, and text files;
- preserve page and source metadata;
- implement a baseline dense retriever;
- expose ingestion and search endpoints.

Exit condition: a question returns relevant chunks with traceable sources.

## Milestone 2 - hybrid retrieval and evaluation

- add lexical retrieval and result fusion;
- add reranking;
- create at least 50 labelled retrieval questions;
- report Recall@5, MRR, and latency.

Exit condition: the hybrid system beats the recorded baseline on the fixed set.

## Milestone 3 - tools and agent workflow

- add incident-history lookup;
- add deterministic sensor-summary analysis;
- implement a bounded state graph;
- expose tool calls and evidence in the response.

Exit condition: representative scenarios use the correct tools and cite evidence.

## Milestone 4 - complete application

- add the demo UI;
- add authentication, rate limiting, and upload validation;
- add structured logs, health checks, and error handling;
- add integration tests.

Exit condition: a new user can complete the main workflow without developer help.

## Milestone 5 - deployment and portfolio package

- build containers and CI checks;
- deploy the application;
- run load, quality, and cost evaluations;
- publish architecture, evaluation, and demo documentation;
- write honest resume bullets from measured results.

Exit condition: public demo or recorded fallback, reproducible repository, and
final evaluation report are available.

