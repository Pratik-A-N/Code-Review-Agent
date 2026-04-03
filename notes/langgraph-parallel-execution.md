# LangGraph Parallel Execution — Personal Notes

---

## Context

Refactored the code-review-agent pipeline to run the three review agents
(Security, Logic, Style) in true parallel using LangGraph's Send API,
instead of the original sequential chain.

---

## Control Flow

### Before (Sequential)

```
code_parser
    │
    ▼
security_node   (~200ms)
    │
    ▼
logic_node      (~180ms)
    │
    ▼
style_node      (~150ms)
    │
    ▼
aggregator

Total ≈ 530ms
```

Implemented via chained `add_edge` calls:
```python
graph.add_edge("security_node", "logic_node")
graph.add_edge("logic_node", "style_node")
graph.add_edge("style_node", "aggregator")
```

Each node waited for the previous to finish before starting.

---

### After (Parallel via Send API)

```
code_parser
    │
    ▼
fan_out()   ← conditional edge function
    │
    ├──── Send("security_node", state) ──→ security_node ─┐
    ├──── Send("logic_node", state)    ──→ logic_node    ──┤→ aggregator
    └──── Send("style_node", state)    ──→ style_node   ──┘

Total ≈ 200ms (only as slow as the slowest node)
```

---

## The Three Core Concepts

---

### 1. The Send API — Message Passing, not Edge Wiring

Normally LangGraph nodes are connected at compile time:
```python
graph.add_edge("A", "B")   # static wiring
```

The Send API is **runtime message dispatch**:
```python
from langgraph.types import Send

def fan_out(state: AgentState):
    return [
        Send("security_node", state),
        Send("logic_node", state),
        Send("style_node", state),
    ]
```

- `Send(node_name, payload)` = "invoke this node with this state right now"
- Returning a **list** of `Send` objects tells LangGraph to dispatch all simultaneously
- LangGraph uses a `ThreadPoolExecutor` internally to run them in parallel threads
- `fan_out` is registered as a **conditional edge function** after `code_parser`
- Normally conditional edges return a string (`"aggregator"`). Returning `Send` objects is the escape hatch for fan-out

**Key insight:** Send API is dynamic — you can decide at runtime how many branches to create
and what payload each gets. Static edges can't do this.

---

### 2. State Reducers — How Parallel Writes Don't Clobber Each Other

**The problem:** if `security_node` and `logic_node` both write to the same state
field simultaneously, who wins? Without reducers, it's last-writer-wins — a race condition.

**The fix — `Annotated[T, reducer_fn]`:**

```python
from typing import Annotated
import operator

class AgentState(TypedDict):
    # Without reducer — race condition in parallel
    security_findings: list[dict]

    # With reducer — parallel writes are merged safely
    security_findings: Annotated[list[dict], operator.add]
```

`Annotated[T, fn]` tells LangGraph: *"when merging updates to this field,
don't overwrite — call `fn(current_value, new_value)` instead."*

`operator.add` on lists = concatenation:
```python
operator.add([], [finding1, finding2])   # → [finding1, finding2]
operator.add([], [finding3])             # → [finding3]
```

Each node writes to a **different** field (`security_findings`, `logic_findings`,
`style_findings`), so they never conflict. LangGraph collects all three partial
updates and merges them before passing state to `aggregator`.

**Custom reducer for nested dicts (`metrics`):**

```python
def _merge_metrics(left: dict, right: dict) -> dict:
    merged = {**left}
    if "latency_per_node" in right:
        merged["latency_per_node"] = {
            **merged.get("latency_per_node", {}),
            **right["latency_per_node"],
        }
    ...
    return merged

metrics: Annotated[dict, _merge_metrics]
```

Three nodes each return:
- `{"latency_per_node": {"security_agent": 200}}`
- `{"latency_per_node": {"logic_agent": 180}}`
- `{"latency_per_node": {"style_agent": 150}}`

The reducer unions all subkeys — none gets lost.

---

### 3. Fan-in / Barrier Synchronization

After 3 parallel nodes fire, how does `aggregator` know to wait for all three?

LangGraph tracks **in-flight branches** from each Send. Each `Send` creates a branch
with a unique task ID. The graph counts how many branches are still running for a
given join point. `aggregator` has three incoming edges, so LangGraph holds it until
all three have delivered their updates — then schedules `aggregator`.

```
security_node ──┐
logic_node    ──┤  barrier: LangGraph waits for all 3
style_node   ──┘
                 │
                 ▼
             aggregator  (runs only after all 3 complete)
```

This is the classic **barrier synchronization** pattern from concurrent programming.

---

### 4. Partial State Updates

Parallel nodes return a `dict`, not a full `AgentState`:

```python
def security_node(state: AgentState) -> dict:   # not AgentState
    findings, ms = run_security_agent(state.get("file_chunks", []))
    return {
        "security_findings": findings,           # only owns this field
        "metrics": {"latency_per_node": {"security_agent": round(ms, 2)}},
    }
```

Each node **only owns its own fields**. LangGraph merges all partial updates
into the global state using the reducers before handing off to the next node.

---

## Files Changed

| File | What changed |
|---|---|
| `backend/graph/state.py` | Added `Annotated` reducers on findings fields and `metrics` |
| `backend/graph/pipeline.py` | Replaced sequential `add_edge` chain with `fan_out` + `Send` |

---

## Interview Cheat Sheet

| Concept | One-liner |
|---|---|
| **Send API** | Runtime message dispatch for dynamic fan-out; returns `Send` objects from a conditional edge instead of a string |
| **Reducers** | Functions declared on state fields via `Annotated[T, fn]` that control how parallel writes are merged instead of overwritten |
| **Fan-in / barrier** | LangGraph counts in-flight branches per join point and holds the next node until all branches resolve |
| **`operator.add`** | Just list concatenation — each parallel node appends its results to the shared list |
| **ThreadPoolExecutor** | LangGraph's sync `invoke()` runs parallel branches in threads; for true async, use `ainvoke()` with `async def` nodes |
| **Partial state updates** | Parallel nodes return `dict` not full state — only the fields they own. Reducers merge these into global state |

---

## Key Trade-off to Remember

> **Send API gives you parallelism but forces you to think about state merging.**
> Sequential nodes can freely read/write shared state.
> Parallel nodes must own disjoint state fields with reducers — otherwise you get non-deterministic results.

---

## Known Caveat (from this project)

Parallelism only helps when the LLM provider can handle concurrent requests.
With **Groq free tier**, all 3 requests land simultaneously and hit rate limits —
making parallel execution *slower* than sequential. Parallelism pays off with
providers that support burst concurrency (Gemini, OpenAI, self-hosted Ollama).
