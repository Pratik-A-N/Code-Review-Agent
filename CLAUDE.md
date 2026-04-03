# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Debugging Protocol

When the user reports an error or says something "failed":
1. FIRST identify which file(s) are involved
2. THEN explain WHY it failed — root cause analysis
3. ONLY THEN propose a solution
4. Do NOT jump to fixing before the user understands the problem

Never skip the breakdown step.

---

## Development Commands

### Backend
```bash
# Activate venv (Windows/bash)
source venv/Scripts/activate

# Install dependencies
pip install -r requirements.txt

# Run backend (from project root)
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev       # dev server at http://localhost:5173
npm run build     # production build
npm run preview   # preview production build
```

### Docker
```bash
cp .env.example .env   # fill in GEMINI_API_KEY
docker-compose up --build
```

---

## Environment Variables

Required in `.env` (copy from `.env.example`):
- `GEMINI_API_KEY` — mandatory, backend crashes without it
- `GITHUB_TOKEN` — optional, only needed for private repos (public PRs work without it at 60 req/hr)
- `DATABASE_URL` — defaults to `sqlite:///./reviews.db`, no setup needed

---

## Architecture

### Request Flow
```
POST /api/review?mode={agent|baseline}
  → pipeline.invoke(initial_state)          # backend/graph/pipeline.py
  → LangGraph StateGraph node sequence
  → save_review()                           # backend/db/database.py
  → ReviewResponse
```

### LangGraph Pipeline (Agent Mode)
Nodes execute sequentially (true parallelism via Send API is a listed TODO):
```
pr_ingester → code_parser → security_agent → logic_agent → style_agent → aggregator → formatter
```

Baseline mode routes after `pr_ingester` directly to a `baseline` node, bypassing all specialist agents and the formatter.

### State Container
`AgentState` (TypedDict in `backend/graph/state.py`) is the single object passed between all nodes. Each node reads from and writes to this shared state. Key fields: `raw_diff`, `file_chunks`, `{security,logic,style}_findings`, `aggregated_findings`, `metrics`.

### LLM Usage
All Gemini calls go through the client initialized in `backend/config.py`. The three review agents (`backend/graph/nodes/review_agents.py`) each call `gemini-2.0-flash` with category-specific prompts and expect a JSON array back. Responses are stripped of markdown code fences before parsing.

### Frontend → Backend Communication
Vite proxies all `/api/*` requests to `http://localhost:8000` (configured in `frontend/vite.config.js`). Always use relative URLs (e.g. `/api/review`) in frontend code — never hardcode `http://localhost:8000` or it bypasses the proxy and causes CORS errors.

### Database
SQLite, auto-created on startup via `init_db()`. Schema is a single `reviews` table where `pr_metadata`, `findings`, and `metrics` are stored as JSON strings and deserialized on read. No migrations — schema is `CREATE TABLE IF NOT EXISTS`.

---

## Key Constraints & Known Issues

- **Sequential agents**: Security, Logic, and Style agents run one after another despite the architecture diagram showing parallel fan-out. Implementing true parallelism requires LangGraph's Send API (listed TODO).
- **Baseline bypasses formatter**: The baseline node does not call the formatter node, so it skips consistent summary generation.
- **Diff truncation**: File chunks are capped at 6000 chars; full diff capped at 8000 chars for baseline — necessary for Gemini free-tier token limits.
- **Simulated progress**: The pipeline progress UI in `App.jsx` uses `setInterval` with fixed delays, not real SSE from the backend.
- **CORS origins**: Hardcoded to `localhost:5173` and `localhost:3000` in `backend/main.py`.
