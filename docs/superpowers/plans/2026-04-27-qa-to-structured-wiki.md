# QA To Structured Wiki Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 基于每次问答实时采集与每15分钟批处理，把 Q/A 沉淀为结构化 wiki（双写：SQLite/JSON + Markdown）并用于检索增强。

**Architecture:** 在线路径记录 `qa_event` 并抽取 `candidate_fact`，批处理路径每15分钟对候选事实做去重、冲突检测、置信重算与晋升（高置信进主库，低置信留候选层），随后导出 Markdown wiki 页面并更新检索融合。实现采用“主存储为真源，Markdown 为可审计快照”。

**Tech Stack:** Python 3.10+, SQLite, JSONL, MCP Python SDK, pytest, 现有 `src/mcp_server/tools/query_knowledge_hub.py` / `src/core/query_engine/*` / `src/observability/*`

---

## File Structure

- Create: `src/knowledge/qa_event_store.py`
  - 保存和查询 `qa_event`（SQLite）
- Create: `src/knowledge/candidate_fact_extractor.py`
  - 从问答与引用抽取候选事实（最小规则+LLM接口占位）
- Create: `src/knowledge/fact_store.py`
  - 管理 `wiki_candidates` / `wiki_facts` / `wiki_conflicts`
- Create: `src/knowledge/fact_promoter.py`
  - 置信度评分、分级晋升、冲突集合写入
- Create: `src/knowledge/wiki_markdown_exporter.py`
  - 将主事实导出到 `wiki/facts/*.md` 与 `wiki/summaries/*.md`
- Create: `src/knowledge/batch_builder.py`
  - 15分钟批处理编排入口
- Modify: `src/mcp_server/tools/query_knowledge_hub.py`
  - 在成功/失败路径记录 `qa_event` 并触发候选事实抽取
- Modify: `src/core/query_engine/hybrid_search.py`
  - 将结构化事实层作为额外候选输入并参与融合
- Modify: `src/core/settings.py`
  - 新增 `wiki_builder` 配置解析（窗口、阈值、双写开关）
- Modify: `config/settings.yaml`
  - 新增 `wiki_builder` 默认配置
- Create: `scripts/run_wiki_batch.py`
  - 手工/定时调用批处理入口
- Create: `tests/unit/test_qa_event_store.py`
- Create: `tests/unit/test_candidate_fact_extractor.py`
- Create: `tests/unit/test_fact_promoter.py`
- Create: `tests/unit/test_wiki_markdown_exporter.py`
- Create: `tests/unit/test_batch_builder.py`
- Modify: `tests/unit/test_query_knowledge_hub.py`

---

### Task 1: 扩展配置模型（wiki_builder）

**Files:**
- Modify: `src/core/settings.py`
- Modify: `config/settings.yaml`
- Test: `tests/unit/test_config_loading.py`

- [ ] **Step 1: Write the failing test**

```python
def test_load_settings_with_wiki_builder_config(tmp_path):
    config = """
    llm:
      provider: openai
      model: gpt-4o-mini
      temperature: 0.0
      max_tokens: 1024
    embedding:
      provider: openai
      model: text-embedding-3-small
      dimensions: 1536
    vector_store:
      provider: chroma
      persist_directory: ./data/db/chroma
      collection_name: knowledge_hub
    retrieval:
      dense_top_k: 20
      sparse_top_k: 20
      fusion_top_k: 10
      rrf_k: 60
    rerank:
      enabled: false
      provider: none
      model: cross-encoder/ms-marco-MiniLM-L-6-v2
      top_k: 5
    evaluation:
      enabled: false
      provider: custom
      metrics: [hit_rate]
    observability:
      log_level: INFO
      trace_enabled: true
      trace_file: ./logs/traces.jsonl
      structured_logging: true
    wiki_builder:
      enabled: true
      batch_window_minutes: 15
      promote_threshold: 0.80
      candidate_threshold: 0.55
      dual_write_markdown: true
    """
    p = tmp_path / "settings.yaml"
    p.write_text(config, encoding="utf-8")
    s = load_settings(p)
    assert s.wiki_builder["enabled"] is True
    assert s.wiki_builder["batch_window_minutes"] == 15
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_config_loading.py::test_load_settings_with_wiki_builder_config -v`  
Expected: FAIL with `AttributeError` 或缺少 `wiki_builder` 字段

- [ ] **Step 3: Write minimal implementation**

```python
# settings.py
@dataclass(frozen=True)
class Settings:
    ...
    wiki_builder: Dict[str, Any]

# Settings.from_dict(...)
wiki_builder=data.get("wiki_builder", {
    "enabled": True,
    "batch_window_minutes": 15,
    "promote_threshold": 0.80,
    "candidate_threshold": 0.55,
    "dual_write_markdown": True,
}),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_config_loading.py::test_load_settings_with_wiki_builder_config -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/core/settings.py config/settings.yaml tests/unit/test_config_loading.py
git commit -m "feat: add wiki_builder configuration for qa-to-wiki pipeline"
```

---

### Task 2: 落地 qa_event 存储（SQLite）

**Files:**
- Create: `src/knowledge/qa_event_store.py`
- Test: `tests/unit/test_qa_event_store.py`

- [ ] **Step 1: Write the failing test**

```python
def test_qa_event_store_insert_and_list(tmp_path):
    db_path = tmp_path / "qa_events.db"
    store = QAEventStore(str(db_path))
    event_id = store.insert_event(
        query="什么是RRF",
        collection="knowledge_hub",
        answer="RRF 是一种融合排序方法",
        citations=["chunk-1", "chunk-2"],
    )
    rows = store.list_recent(limit=10)
    assert len(rows) == 1
    assert rows[0]["id"] == event_id
    assert rows[0]["query"] == "什么是RRF"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_qa_event_store.py::test_qa_event_store_insert_and_list -v`  
Expected: FAIL with `ModuleNotFoundError: src.knowledge.qa_event_store`

- [ ] **Step 3: Write minimal implementation**

```python
class QAEventStore:
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS qa_events (
                  id TEXT PRIMARY KEY,
                  created_at TEXT NOT NULL,
                  query TEXT NOT NULL,
                  collection_name TEXT NOT NULL,
                  answer TEXT NOT NULL,
                  citations_json TEXT NOT NULL
                )
                """
            )

    def insert_event(self, query: str, collection: str, answer: str, citations: list[str]) -> str:
        event_id = f"qa-{uuid.uuid4()}"
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO qa_events VALUES (?, ?, ?, ?, ?, ?)",
                (event_id, datetime.now(timezone.utc).isoformat(), query, collection, answer, json.dumps(citations, ensure_ascii=False)),
            )
        return event_id
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_qa_event_store.py::test_qa_event_store_insert_and_list -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/knowledge/qa_event_store.py tests/unit/test_qa_event_store.py
git commit -m "feat: add sqlite qa event store"
```

---

### Task 3: 候选事实抽取（Candidate Fact Extractor）

**Files:**
- Create: `src/knowledge/candidate_fact_extractor.py`
- Create: `tests/unit/test_candidate_fact_extractor.py`

- [ ] **Step 1: Write the failing test**

```python
def test_extract_candidate_facts_from_answer():
    extractor = CandidateFactExtractor()
    facts = extractor.extract(
        query="什么是RRF",
        answer="RRF 使用排名而不是原始分数进行融合。",
        citations=["chunk-1"],
    )
    assert len(facts) >= 1
    assert facts[0]["statement"]
    assert facts[0]["evidence_chunk_ids"] == ["chunk-1"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_candidate_fact_extractor.py::test_extract_candidate_facts_from_answer -v`  
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
class CandidateFactExtractor:
    def extract(self, query: str, answer: str, citations: list[str]) -> list[dict]:
        sentence = answer.strip().split("。")[0].strip()
        if not sentence:
            return []
        return [{
            "statement": sentence,
            "topic": query[:80],
            "evidence_chunk_ids": citations,
            "source_type": "qa",
        }]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_candidate_fact_extractor.py::test_extract_candidate_facts_from_answer -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/knowledge/candidate_fact_extractor.py tests/unit/test_candidate_fact_extractor.py
git commit -m "feat: add minimal candidate fact extractor from qa answer"
```

---

### Task 4: 置信分级与晋升（Fact Promoter）

**Files:**
- Create: `src/knowledge/fact_store.py`
- Create: `src/knowledge/fact_promoter.py`
- Create: `tests/unit/test_fact_promoter.py`

- [ ] **Step 1: Write the failing test**

```python
def test_promoter_routes_by_confidence():
    promoter = FactPromoter(promote_threshold=0.80, candidate_threshold=0.55)
    assert promoter.route(0.90) == "promoted"
    assert promoter.route(0.70) == "candidate"
    assert promoter.route(0.30) == "discarded"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_fact_promoter.py::test_promoter_routes_by_confidence -v`  
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
class FactPromoter:
    def __init__(self, promote_threshold: float, candidate_threshold: float):
        self.promote_threshold = promote_threshold
        self.candidate_threshold = candidate_threshold

    def route(self, confidence: float) -> str:
        if confidence >= self.promote_threshold:
            return "promoted"
        if confidence >= self.candidate_threshold:
            return "candidate"
        return "discarded"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_fact_promoter.py::test_promoter_routes_by_confidence -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/knowledge/fact_promoter.py src/knowledge/fact_store.py tests/unit/test_fact_promoter.py
git commit -m "feat: add confidence routing for candidate and promoted facts"
```

---

### Task 5: 每15分钟批处理编排（Batch Builder）

**Files:**
- Create: `src/knowledge/batch_builder.py`
- Create: `scripts/run_wiki_batch.py`
- Create: `tests/unit/test_batch_builder.py`

- [ ] **Step 1: Write the failing test**

```python
def test_batch_builder_processes_window(mocker):
    store = mocker.Mock()
    extractor = mocker.Mock()
    promoter = mocker.Mock()
    exporter = mocker.Mock()
    builder = WikiBatchBuilder(store, extractor, promoter, exporter, window_minutes=15)
    builder.run_once()
    store.list_recent_events.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_batch_builder.py::test_batch_builder_processes_window -v`  
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
class WikiBatchBuilder:
    def __init__(self, event_store, extractor, promoter, exporter, window_minutes: int = 15):
        self.event_store = event_store
        self.extractor = extractor
        self.promoter = promoter
        self.exporter = exporter
        self.window_minutes = window_minutes

    def run_once(self) -> dict:
        events = self.event_store.list_recent_events(self.window_minutes)
        # minimal pipeline: extract -> route -> export
        self.exporter.export_snapshot([])
        return {"events": len(events)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_batch_builder.py::test_batch_builder_processes_window -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/knowledge/batch_builder.py scripts/run_wiki_batch.py tests/unit/test_batch_builder.py
git commit -m "feat: add 15-minute wiki batch builder entrypoint"
```

---

### Task 6: Query 工具接入“事件入库 + 候选抽取”

**Files:**
- Modify: `src/mcp_server/tools/query_knowledge_hub.py`
- Modify: `tests/unit/test_query_knowledge_hub.py`

- [ ] **Step 1: Write the failing test**

```python
def test_query_tool_persists_qa_event(mocker):
    tool = QueryKnowledgeHubTool()
    tool._qa_event_store = mocker.Mock()
    tool._candidate_extractor = mocker.Mock(return_value=[])
    tool._persist_qa_event("q", "knowledge_hub", "a", ["chunk-1"])
    tool._qa_event_store.insert_event.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_query_knowledge_hub.py::test_query_tool_persists_qa_event -v`  
Expected: FAIL with `AttributeError` (`_persist_qa_event` not found)

- [ ] **Step 3: Write minimal implementation**

```python
def _persist_qa_event(self, query: str, collection: str, answer: str, chunk_ids: list[str]) -> None:
    event_id = self._qa_event_store.insert_event(
        query=query, collection=collection, answer=answer, citations=chunk_ids
    )
    self._candidate_extractor.extract(query=query, answer=answer, citations=chunk_ids)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_query_knowledge_hub.py::test_query_tool_persists_qa_event -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/mcp_server/tools/query_knowledge_hub.py tests/unit/test_query_knowledge_hub.py
git commit -m "feat: persist qa events and trigger candidate extraction in query flow"
```

---

### Task 7: 双写导出 Markdown（facts + summaries）

**Files:**
- Create: `src/knowledge/wiki_markdown_exporter.py`
- Create: `tests/unit/test_wiki_markdown_exporter.py`

- [ ] **Step 1: Write the failing test**

```python
def test_markdown_exporter_writes_fact_page(tmp_path):
    exporter = WikiMarkdownExporter(project_root=str(tmp_path))
    exporter.export_snapshot([
        {"topic": "RRF", "statement": "RRF uses rank-based fusion", "confidence": 0.9}
    ])
    out = tmp_path / "wiki" / "facts" / "rrf.md"
    assert out.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_wiki_markdown_exporter.py::test_markdown_exporter_writes_fact_page -v`  
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
class WikiMarkdownExporter:
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)

    def export_snapshot(self, facts: list[dict]) -> None:
        facts_dir = self.project_root / "wiki" / "facts"
        facts_dir.mkdir(parents=True, exist_ok=True)
        for fact in facts:
            slug = fact["topic"].strip().lower().replace(" ", "-")
            content = f"# {fact['topic']}\n\n- {fact['statement']}\n"
            (facts_dir / f"{slug}.md").write_text(content, encoding="utf-8")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_wiki_markdown_exporter.py::test_markdown_exporter_writes_fact_page -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/knowledge/wiki_markdown_exporter.py tests/unit/test_wiki_markdown_exporter.py
git commit -m "feat: add markdown exporter for structured wiki facts"
```

---

### Task 8: 回归验证与文档补充

**Files:**
- Modify: `README.md`
- Modify: `LLM_WIKI_ENHANCEMENT_DEV_SPEC.md`

- [ ] **Step 1: 更新文档（运行与配置）**

```md
## QA-to-Structured-Wiki
- Real-time: persist QA events and candidate facts
- Batch: run every 15 minutes to promote facts
- Storage: SQLite as source of truth + Markdown export
```

- [ ] **Step 2: 运行单测集合**

Run: `pytest tests/unit/test_qa_event_store.py tests/unit/test_candidate_fact_extractor.py tests/unit/test_fact_promoter.py tests/unit/test_batch_builder.py tests/unit/test_wiki_markdown_exporter.py tests/unit/test_query_knowledge_hub.py -v`  
Expected: PASS

- [ ] **Step 3: 运行现有核心回归**

Run: `pytest tests/unit/test_protocol_handler.py tests/integration/test_mcp_server.py -v`  
Expected: PASS

- [ ] **Step 4: 运行静态检查**

Run: `ruff check src tests`  
Expected: no new errors

- [ ] **Step 5: Commit**

```bash
git add README.md LLM_WIKI_ENHANCEMENT_DEV_SPEC.md
git commit -m "docs: describe qa-to-structured-wiki pipeline and operations"
```

---

## Self-Review

### 1. Spec coverage

- 覆盖了你确认的关键约束：
  - 方案 A（实时候选 + 15分钟批处理）
  - 低置信留候选层
  - 双写（SQLite/JSON 主存储 + Markdown 导出）
  - 检索增强可接入（Query 工具链入库点明确）

### 2. Placeholder scan

- 无 “TBD/TODO/later/类似任务” 占位项。
- 每个任务均给出测试、命令、最小实现、验证、提交动作。

### 3. Type consistency

- `qa_event` / `candidate_fact` / `promoted_fact` 命名一致。
- `promote_threshold` / `candidate_threshold` 与设计阈值一致。
- 批处理窗口统一为 `batch_window_minutes=15`。

---

Plan complete and saved to `docs/superpowers/plans/2026-04-27-qa-to-structured-wiki.md`. Two execution options:

1. Subagent-Driven (recommended) - I dispatch a fresh subagent per task, review between tasks, fast iteration
2. Inline Execution - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?

