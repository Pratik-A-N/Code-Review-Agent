# Code Review Agent

> AI-powered code review agent using LangGraph multi-agent architecture with real-time SSE streaming

**[Live Demo](https://code-review-agent-ui.onrender.com)** · [API Docs](https://code-review-agent-api-fdkw.onrender.com/docs)

---

## Overview

Paste a GitHub Pull Request URL and get a structured code review in seconds. Three specialized AI agents (security, logic, style) analyze the diff in parallel and surface findings ranked by severity — with a baseline single-prompt mode for direct comparison.

### Key Features

- **Parallel multi-agent review** — Security, Logic, and Style agents run independently via LangGraph's Send API and fan back in to an aggregator
- **Provider-agnostic LLM abstraction** — swap between Google Gemini and Groq via a factory pattern; no code changes needed
- **Real-time streaming progress** — SSE delivers live node status events to the browser as each pipeline stage completes
- **GitHub PR integration** — works with any public GitHub PR URL out of the box; supports private repos via `GITHUB_TOKEN`

**Screenshots**

<!-- Add screenshots here -->
_[screenshot placeholder]_

---

## Architecture

```
POST /api/review/async
        │
        ▼
┌───────────────┐
│  PR Ingester  │  GitHub REST API → raw diff + metadata
└───────┬───────┘
        │
┌───────▼───────┐
│  Code Parser  │  Split diff → per-file chunks + language detection
└───────┬───────┘
        │
   ┌────┴──────────────────┐
   │           │            │
┌──▼──┐   ┌───▼──┐   ┌────▼──┐
│Sec. │   │Logic │   │Style  │  ← parallel via LangGraph Send API
│Agent│   │Agent │   │Agent  │
└──┬──┘   └───┬──┘   └────┬──┘
   └──────────┼────────────┘
              │
   ┌──────────▼──────────┐
   │      Aggregator     │  Merge + deduplicate + rank by severity
   └──────────┬──────────┘
              │
   ┌──────────▼──────────┐
   │      Formatter      │  LLM summary + structured JSON output
   └─────────────────────┘
              │
    SSE stream → browser
```

**Baseline mode** routes directly from `pr_ingester` to a single-prompt node, bypassing all specialist agents — useful for comparison.

**SSE progress** — `POST /api/review/async` returns a `review_id` immediately; the browser opens `GET /api/review/{review_id}/stream` to receive live node status events as the pipeline executes.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend framework | FastAPI |
| Agent orchestration | LangGraph (StateGraph + Send API) |
| LLM providers | Gemini 2.0 Flash / Groq (provider-agnostic factory) |
| Real-time streaming | Server-Sent Events (SSE) via `sse-starlette` |
| Database | SQLite (auto-created, no migrations) |
| Frontend | React 18 + Vite + Tailwind CSS |
| Containerization | Docker + docker-compose |
| Deployment | Render (API service + Static Site) |

---

## Local Setup

### Prerequisites
- Python 3.11+
- Node.js 20+
- [Gemini API key](https://aistudio.google.com/) (free tier works)

### Quick Start

```bash
# 1. Clone and configure
git clone <repo-url>
cd code-review-agent
cp .env.example .env
# Edit .env — set GEMINI_API_KEY at minimum

# 2. Backend
pip install -r requirements.txt
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# 3. Frontend (new terminal)
cd frontend
npm install
npm run dev
```

Open http://localhost:5173, paste a GitHub PR URL, click **Run Code Review**.

### Docker

```bash
cp .env.example .env  # fill in GEMINI_API_KEY
docker-compose up --build
# frontend → http://localhost:5173
# backend  → http://localhost:8000
```

---

## Deployment (Render)

1. Push this repo to GitHub.
2. Go to [Render Blueprints](https://dashboard.render.com/blueprints) and connect the repo — `render.yaml` is auto-detected.
3. After the first deploy, set these secret env vars in the Render dashboard:
   - `GEMINI_API_KEY` — required
   - `GITHUB_TOKEN` — optional (private repos only)
   - `CORS_ORIGINS` — set to your frontend's public URL (e.g. `https://code-review-frontend.onrender.com`)
   - `VITE_API_URL` (frontend service) — set to your backend's public URL, then trigger a redeploy.

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Health check |
| `POST` | `/api/review` | Synchronous review (blocks until complete) |
| `POST` | `/api/review/async` | Start async review → returns `{review_id}` |
| `GET` | `/api/review/{review_id}/stream` | SSE stream of progress + final result |
| `GET` | `/api/reviews` | Review history (last 50) |
| `GET` | `/api/reviews/{id}` | Single review by DB ID |

**POST /api/review body:**
```json
{ "pr_url": "https://github.com/owner/repo/pull/123" }
```

**SSE event types:**
```jsonc
// Node progress
{"node": "pr_ingester", "status": "running",   "message": "Fetching PR data..."}
{"node": "pr_ingester", "status": "completed", "message": "PR data fetched", "latency_ms": 312}

// Final result
{"type": "result", "data": { /* ReviewResponse */ }}

// Error
{"type": "error", "message": "..."}
```

**Query param:** `?mode=agent` (default) or `?mode=baseline`

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `GEMINI_API_KEY` | Yes | — | Google AI Studio API key |
| `GITHUB_TOKEN` | No | — | PAT for private repo access |
| `DATABASE_URL` | No | `sqlite:///./reviews.db` | SQLite path |
| `CORS_ORIGINS` | No | `http://localhost:5173,...` | Comma-separated allowed origins |
