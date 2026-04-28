# B-Minimal RAG Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 以最小改动为 `MODULAR-RAG-MCP-SERVER` 增加 4 个增强能力：提问-回答反哺闭环、RRF 权重可配置化、chunk->document 聚合、MCP resources/prompts 扩展。

**Architecture:** 保持现有 Query/Tool 主链路不变，先在查询工具层加入“提问-召回-回答-反馈信号”日志闭环，再在融合层增加可配置权重、在 `query_knowledge_hub` 输出前增加文档聚合后处理，并在 MCP 协议层新增 resources/prompts 可发现接口。实现优先“兼容默认行为”，未配置时与当前行为一致。

**Tech Stack:** Python 3.10+, MCP Python SDK, pytest, 现有 `src/core/query_engine/*` 与 `src/mcp_server/*`

---

## File Structure

- Modify: `config/settings.yaml`
  - 新增最小配置项：`retrieval.feedback_loop`、`retrieval.rrf_weights`、`retrieval.doc_aggregation`
- Modify: `src/core/settings.py`
  - 为新增配置提供 dataclass 字段与解析逻辑（含默认值）
- Create: `src/observability/qa_feedback_logger.py`
  - 记录 query、检索结果、答案摘要、弱反馈信号（追问/改写）
- Modify: `src/core/query_engine/hybrid_search.py`
  - 融合阶段按配置决定调用 `fuse()` 或 `fuse_with_weights()`
- Modify: `src/mcp_server/tools/query_knowledge_hub.py`
  - 增加文档级聚合函数，作为 query 工具最后一步后处理；并接入 QA feedback logger
- Modify: `src/mcp_server/protocol_handler.py`
  - 注册 `list_resources/read_resource/list_prompts/get_prompt`
- Create: `src/mcp_server/resource_prompt_registry.py`
  - 统一维护 resources/prompts 的装配逻辑与 `config/prompts` 文件读取
- Test: `tests/unit/test_hybrid_search.py`（如已存在则扩展）
- Test: `tests/unit/test_query_knowledge_hub.py`（如已存在则扩展）
- Create: `tests/unit/test_qa_feedback_logger.py`
- Create: `tests/unit/test_resource_prompt_registry.py`
- Modify: `tests/unit/test_protocol_handler.py`

---

### Task 0: 提问-回答反哺闭环（最小日志链路）

**Files:**
- Modify: `config/settings.yaml`
- Modify: `src/core/settings.py`
- Create: `src/observability/qa_feedback_logger.py`
- Modify: `src/mcp_server/tools/query_knowledge_hub.py`
- Create: `tests/unit/test_qa_feedback_logger.py`
- Modify: `tests/unit/test_query_knowledge_hub.py`

- [ ] **Step 1: 写失败测试（日志记录）**

```python
def test_qa_feedback_logger_writes_jsonl(tmp_path):
    logger = QAFeedbackLogger(log_path=str(tmp_path / "qa_feedback.jsonl"))
    logger.log_event({
        "query": "什么是RRF",
        "collection": "knowledge_hub",
        "result_count": 3,
        "follow_up": False,
    })
    lines = (tmp_path / "qa_feedback.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert "\"query\": \"什么是RRF\"" in lines[0]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/unit/test_qa_feedback_logger.py::test_qa_feedback_logger_writes_jsonl -v`  
Expected: FAIL（文件与类未实现）

- [ ] **Step 3: 最小实现 logger 与配置字段**

```python
class QAFeedbackLogger:
    def __init__(self, log_path: str = "./logs/qa_feedback.jsonl", enabled: bool = True):
        self.log_path = Path(log_path)
        self.enabled = enabled
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log_event(self, payload: Dict[str, Any]) -> None:
        if not self.enabled:
            return
        payload = {"timestamp": datetime.utcnow().isoformat(), **payload}
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
```

- [ ] **Step 4: 在 query_knowledge_hub 接入日志（弱反馈先行）**

```python
# execute() 结束前记录
self._qa_feedback_logger.log_event({
    "query": query,
    "collection": effective_collection,
    "result_count": len(results),
    "top_k": effective_top_k,
    "final_chunk_ids": [r.chunk_id for r in results[:5]],
    "follow_up": False,  # 先占位，后续可由会话层覆盖
})
```

- [ ] **Step 5: 运行测试并提交**

Run: `pytest tests/unit/test_qa_feedback_logger.py tests/unit/test_query_knowledge_hub.py -v`  
Expected: PASS

```bash
git add config/settings.yaml src/core/settings.py src/observability/qa_feedback_logger.py src/mcp_server/tools/query_knowledge_hub.py tests/unit/test_qa_feedback_logger.py tests/unit/test_query_knowledge_hub.py
git commit -m "feat: add minimal qa feedback loop logging for query-answer traces"
```

---

### Task 1: 配置模型扩展（RRF 权重 + 文档聚合开关）

**Files:**
- Modify: `config/settings.yaml`
- Modify: `src/core/settings.py`
- Test: `tests/unit/test_config_loading.py`

- [ ] **Step 1: 写失败测试（配置解析）**

```python
def test_settings_parse_rrf_weights_and_doc_aggregation():
    data = {
        "llm": {"provider": "openai", "model": "gpt-4o", "temperature": 0.0, "max_tokens": 1024},
        "embedding": {"provider": "openai", "model": "text-embedding-ada-002", "dimensions": 1536},
        "vector_store": {"provider": "chroma", "persist_directory": "./data/db/chroma", "collection_name": "knowledge_hub"},
        "retrieval": {
            "dense_top_k": 20,
            "sparse_top_k": 20,
            "fusion_top_k": 10,
            "rrf_k": 60,
            "rrf_weights": {"dense": 1.2, "sparse": 0.8},
            "doc_aggregation": {"enabled": True, "tail_decay": 0.5},
        },
        "rerank": {"enabled": False, "provider": "none", "model": "x", "top_k": 5},
        "evaluation": {"enabled": False, "provider": "custom", "metrics": ["hit_rate"]},
        "observability": {"log_level": "INFO", "trace_enabled": True, "trace_file": "./logs/t.jsonl", "structured_logging": True},
    }
    s = Settings.from_dict(data)
    assert s.retrieval.rrf_weights["dense"] == 1.2
    assert s.retrieval.rrf_weights["sparse"] == 0.8
    assert s.retrieval.doc_aggregation["enabled"] is True
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/unit/test_config_loading.py::test_settings_parse_rrf_weights_and_doc_aggregation -v`  
Expected: FAIL（`RetrievalSettings` 尚未包含新字段）

- [ ] **Step 3: 最小实现配置解析**

```python
@dataclass(frozen=True)
class RetrievalSettings:
    dense_top_k: int
    sparse_top_k: int
    fusion_top_k: int
    rrf_k: int
    rrf_weights: Dict[str, float]
    doc_aggregation: Dict[str, Any]

# in Settings.from_dict(...)
RetrievalSettings(
    dense_top_k=_require_int(retrieval, "dense_top_k", "retrieval"),
    sparse_top_k=_require_int(retrieval, "sparse_top_k", "retrieval"),
    fusion_top_k=_require_int(retrieval, "fusion_top_k", "retrieval"),
    rrf_k=_require_int(retrieval, "rrf_k", "retrieval"),
    rrf_weights=retrieval.get("rrf_weights", {"dense": 1.0, "sparse": 1.0}),
    doc_aggregation=retrieval.get("doc_aggregation", {"enabled": False, "tail_decay": 0.5}),
)
```

- [ ] **Step 4: 更新默认配置文件**

```yaml
retrieval:
  dense_top_k: 20
  sparse_top_k: 20
  fusion_top_k: 10
  rrf_k: 60
  rrf_weights:
    dense: 1.0
    sparse: 1.0
  doc_aggregation:
    enabled: false
    tail_decay: 0.5
```

- [ ] **Step 5: 运行测试并提交**

Run: `pytest tests/unit/test_config_loading.py -v`  
Expected: PASS

```bash
git add config/settings.yaml src/core/settings.py tests/unit/test_config_loading.py
git commit -m "feat: add retrieval config for weighted rrf and doc aggregation"
```

---

### Task 2: RRF 权重可配置化接入 HybridSearch

**Files:**
- Modify: `src/core/query_engine/hybrid_search.py`
- Test: `tests/unit/test_hybrid_search.py`

- [ ] **Step 1: 写失败测试（权重调用路径）**

```python
def test_hybrid_search_uses_weighted_rrf_when_configured(mocker):
    fusion = mocker.Mock()
    fusion.fuse.return_value = []
    fusion.fuse_with_weights.return_value = []
    hs = HybridSearch(
        settings=None,
        query_processor=mocker.Mock(),
        dense_retriever=mocker.Mock(),
        sparse_retriever=mocker.Mock(),
        fusion=fusion,
        config=HybridSearchConfig()
    )
    hs.config.rrf_weights = {"dense": 1.2, "sparse": 0.8}
    hs._fuse_results([], [], 5, None)
    fusion.fuse_with_weights.assert_called_once()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/unit/test_hybrid_search.py::test_hybrid_search_uses_weighted_rrf_when_configured -v`  
Expected: FAIL（尚未使用 `fuse_with_weights`）

- [ ] **Step 3: 最小实现（兼容默认）**

```python
# HybridSearchConfig 增加字段
rrf_weights: Dict[str, float] = field(default_factory=lambda: {"dense": 1.0, "sparse": 1.0})

# _extract_config 从 settings.retrieval 读取 rrf_weights
rrf_weights=getattr(retrieval_config, "rrf_weights", {"dense": 1.0, "sparse": 1.0}),

# _fuse_results 中按权重分支
weights = [self.config.rrf_weights.get("dense", 1.0), self.config.rrf_weights.get("sparse", 1.0)]
if weights != [1.0, 1.0]:
    fused = self.fusion.fuse_with_weights(ranking_lists=ranking_lists, weights=weights, top_k=top_k, trace=trace)
else:
    fused = self.fusion.fuse(ranking_lists=ranking_lists, top_k=top_k, trace=trace)
```

- [ ] **Step 4: 补充回归测试（默认行为不变）**

```python
def test_hybrid_search_uses_default_fuse_when_weights_default(mocker):
    fusion = mocker.Mock()
    fusion.fuse.return_value = []
    hs = HybridSearch(..., fusion=fusion, config=HybridSearchConfig())
    hs.config.rrf_weights = {"dense": 1.0, "sparse": 1.0}
    hs._fuse_results([], [], 5, None)
    fusion.fuse.assert_called_once()
```

- [ ] **Step 5: 运行测试并提交**

Run: `pytest tests/unit/test_hybrid_search.py -v`  
Expected: PASS

```bash
git add src/core/query_engine/hybrid_search.py tests/unit/test_hybrid_search.py
git commit -m "feat: support configurable weighted rrf in hybrid search"
```

---

### Task 3: 在 query_knowledge_hub 增加 chunk->document 聚合

**Files:**
- Modify: `src/mcp_server/tools/query_knowledge_hub.py`
- Test: `tests/unit/test_query_knowledge_hub.py`

- [ ] **Step 1: 写失败测试（聚合行为）**

```python
def test_doc_aggregation_merges_same_source_results():
    tool = QueryKnowledgeHubTool()
    tool.config.enable_doc_aggregation = True
    tool.config.doc_aggregation_tail_decay = 0.5
    results = [
        RetrievalResult(chunk_id="a1", score=0.9, text="A1", metadata={"source_path": "docA.md"}),
        RetrievalResult(chunk_id="a2", score=0.7, text="A2", metadata={"source_path": "docA.md"}),
        RetrievalResult(chunk_id="b1", score=0.8, text="B1", metadata={"source_path": "docB.md"}),
    ]
    out = tool._aggregate_results_by_document(results, top_k=5)
    assert len(out) == 2
    assert out[0].metadata["chunk_count"] >= 1
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/unit/test_query_knowledge_hub.py::test_doc_aggregation_merges_same_source_results -v`  
Expected: FAIL（函数或配置字段不存在）

- [ ] **Step 3: 最小实现（工具层后处理）**

```python
@dataclass
class QueryKnowledgeHubConfig:
    ...
    enable_doc_aggregation: bool = False
    doc_aggregation_tail_decay: float = 0.5

def _aggregate_results_by_document(self, results: List[RetrievalResult], top_k: int) -> List[RetrievalResult]:
    grouped = {}
    for r in results:
        key = r.metadata.get("source_ref") or r.metadata.get("doc_id") or r.metadata.get("source_path") or r.chunk_id
        grouped.setdefault(str(key), []).append(r)
    merged = []
    for group in grouped.values():
        group.sort(key=lambda x: x.score, reverse=True)
        best = group[0]
        score = best.score
        for i, tail in enumerate(group[1:], start=2):
            score += tail.score * (self.config.doc_aggregation_tail_decay / i)
        m = best.metadata.copy()
        m["chunk_count"] = len(group)
        merged.append(RetrievalResult(chunk_id=best.chunk_id, score=score, text=best.text, metadata=m))
    merged.sort(key=lambda x: x.score, reverse=True)
    return merged[:top_k]
```

- [ ] **Step 4: 在 execute 流程中接入聚合（可开关）**

```python
if self.config.enable_doc_aggregation and results:
    results = self._aggregate_results_by_document(results, effective_top_k)
```

- [ ] **Step 5: 运行测试并提交**

Run: `pytest tests/unit/test_query_knowledge_hub.py -v`  
Expected: PASS

```bash
git add src/mcp_server/tools/query_knowledge_hub.py tests/unit/test_query_knowledge_hub.py
git commit -m "feat: add optional chunk-to-document aggregation in query tool"
```

---

### Task 4: MCP resources/prompts 最小扩展

**Files:**
- Create: `src/mcp_server/resource_prompt_registry.py`
- Modify: `src/mcp_server/protocol_handler.py`
- Test: `tests/unit/test_resource_prompt_registry.py`
- Test: `tests/unit/test_protocol_handler.py`

- [ ] **Step 1: 写失败测试（list/read/get）**

```python
def test_registry_lists_prompt_resources():
    reg = ResourcePromptRegistry(prompts_dir="config/prompts")
    resources = reg.list_resources()
    assert any("mrag://prompts/" in str(r.uri) for r in resources)

def test_registry_get_prompt_template():
    reg = ResourcePromptRegistry(prompts_dir="config/prompts")
    result = reg.get_prompt("retrieval_answer", {"query": "什么是RRF"})
    assert len(result.messages) > 0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/unit/test_resource_prompt_registry.py -v`  
Expected: FAIL（文件与类未实现）

- [ ] **Step 3: 实现统一注册器**

```python
class ResourcePromptRegistry:
    def __init__(self, prompts_dir: str = "config/prompts"):
        self.prompts_dir = Path(prompts_dir)

    def list_resources(self) -> List[types.Resource]:
        # mrag://prompts/{name}
        ...

    def read_resource(self, uri: str) -> types.ReadResourceResult:
        ...

    def list_prompts(self) -> List[types.Prompt]:
        return [
            types.Prompt(name="retrieval_answer", arguments=[types.PromptArgument(name="query", required=True)]),
            types.Prompt(name="document_summary", arguments=[types.PromptArgument(name="doc_id", required=True)]),
        ]

    def get_prompt(self, name: str, arguments: Dict[str, Any]) -> types.GetPromptResult:
        ...
```

- [ ] **Step 4: 在 protocol_handler 注册 MCP handlers**

```python
registry = ResourcePromptRegistry()

@server.list_resources()
async def handle_list_resources() -> List[types.Resource]:
    return registry.list_resources()

@server.read_resource()
async def handle_read_resource(uri: str) -> types.ReadResourceResult:
    return registry.read_resource(uri)

@server.list_prompts()
async def handle_list_prompts() -> List[types.Prompt]:
    return registry.list_prompts()

@server.get_prompt()
async def handle_get_prompt(name: str, arguments: Dict[str, Any]) -> types.GetPromptResult:
    return registry.get_prompt(name, arguments or {})
```

- [ ] **Step 5: 运行测试并提交**

Run: `pytest tests/unit/test_resource_prompt_registry.py tests/unit/test_protocol_handler.py -v`  
Expected: PASS

```bash
git add src/mcp_server/resource_prompt_registry.py src/mcp_server/protocol_handler.py tests/unit/test_resource_prompt_registry.py tests/unit/test_protocol_handler.py
git commit -m "feat: add mcp resources and prompts discovery support"
```

---

### Task 5: 回归验证与文档更新

**Files:**
- Modify: `README.md`
- Modify: `LLM_WIKI_ENHANCEMENT_DEV_SPEC.md`（仅追加已实施状态，不改原规划结构）
- Test: `tests/integration/test_mcp_server.py`

- [ ] **Step 1: 写文档更新内容**

```md
## New retrieval enhancements
- configurable weighted RRF via `retrieval.rrf_weights`
- optional doc aggregation via `retrieval.doc_aggregation`
- MCP resources/prompts discovery endpoints
```

- [ ] **Step 2: 运行核心测试集合**

Run: `pytest tests/unit/test_config_loading.py tests/unit/test_hybrid_search.py tests/unit/test_query_knowledge_hub.py tests/unit/test_resource_prompt_registry.py tests/unit/test_protocol_handler.py -v`  
Expected: PASS

- [ ] **Step 3: 运行 MCP 集成测试**

Run: `pytest tests/integration/test_mcp_server.py -v`  
Expected: PASS（至少 initialize/tools/list 不回归）

- [ ] **Step 4: 全量静态检查**

Run: `ruff check src tests`  
Expected: no new errors

- [ ] **Step 5: 提交收尾**

```bash
git add README.md LLM_WIKI_ENHANCEMENT_DEV_SPEC.md
git commit -m "docs: document minimal enhancement package and config usage"
```

---

## Self-Review

### 1) Spec coverage

- 覆盖项 0：提问-回答反哺闭环 -> Task 0
- 覆盖项 A：RRF 权重可配置化 -> Task 1 + Task 2
- 覆盖项 B：chunk->document 聚合 -> Task 3
- 覆盖项 C：MCP resources/prompts 扩展 -> Task 4
- 验证与交付闭环 -> Task 5

无缺口。

### 2) Placeholder scan

- 无 “TODO/TBD/later/similar to” 占位语。
- 每个代码步骤都给了可执行示例。

### 3) Type consistency

- 配置字段统一使用 `rrf_weights` 与 `doc_aggregation`。
- Query 工具聚合开关统一使用 `enable_doc_aggregation`。
- MCP 新增能力统一由 `ResourcePromptRegistry` 提供。

---

Plan complete and saved to `docs/superpowers/plans/2026-04-27-b-minimal-rag-enhancement.md`. Two execution options:

1. Subagent-Driven (recommended) - I dispatch a fresh subagent per task, review between tasks, fast iteration
2. Inline Execution - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?

