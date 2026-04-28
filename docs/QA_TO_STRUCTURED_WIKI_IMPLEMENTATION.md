# QA to Structured Wiki - Implementation Notes

## Scope implemented in this iteration

- Added `wiki_builder` config section in `config/settings.yaml` and parsed via `Settings`.
- Added SQLite QA event persistence via `src/knowledge/qa_event_store.py`.
- Added candidate fact extraction via `src/knowledge/candidate_fact_extractor.py`.
- Added tiered confidence classifier via `src/knowledge/fact_promoter.py`.
- Added batch primitives via `src/knowledge/batch_builder.py` and `src/knowledge/batch_orchestrator.py`.
- Added markdown dual-write export via `src/knowledge/markdown_exporter.py`.
- Integrated query tool side effects in `query_knowledge_hub`:
  - persist QA event
  - extract candidate facts
  - side effects are non-blocking (main query path is not broken when they fail)

## Security and resilience hardening

- Prompt registry now validates prompt names (`[A-Za-z0-9_-]+`) to prevent path traversal.
- QA persistence and extraction side effects are wrapped in exception handling to avoid main path regression.

## Test coverage added

- `tests/unit/test_config_loading.py`: wiki_builder config loading.
- `tests/unit/test_qa_event_store.py`: SQLite insert/list flow.
- `tests/unit/test_wiki_pipeline.py`: extractor/promoter/exporter.
- `tests/unit/test_batch_orchestrator.py`: 15-minute window representation.
- `tests/unit/test_query_knowledge_hub.py`: QA persist/extract + non-blocking behavior.
- `tests/unit/test_resource_prompt_registry.py`: prompt name traversal rejection.

## Next recommended step

- Add periodic scheduler wiring (real 15-min trigger loop) to invoke `BatchBuilder.run(...)` over queued candidate facts.
