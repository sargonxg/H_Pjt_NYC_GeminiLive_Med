# CONCORDIA

**Live AI mediation agent that builds a conflict knowledge graph in real time.**

Built for the NYC Build W/ AI Hackathon (Google Cloud Labs × Columbia Business School, March 2026).

> *"When the picture is complete, the mediator becomes a bridge-builder."*

---

## What It Does

Parties to a dispute talk naturally — alone or together — while a conflict knowledge graph builds live on screen. CONCORDIA listens, extracts structural primitives (actors, claims, interests, leverage, narratives…), and visualizes them as a D3 force graph. When the picture is complete, the agent shifts from listener to bridge-builder, proposing concrete resolution paths grounded in the graph data.

**The core thesis:** conflict has a grammar. Eight structural primitives — derived from UN Security Council mediation practice — can capture any human dispute. CONCORDIA makes that grammar visible and actionable.

---

## Architecture

```
Browser (React 18 + D3.js)
  │ WebSocket (text / audio / graph updates)
  │ REST API (case management)
  ▼
┌─────────────────────────────────────────────┐
│  FastAPI Server (main.py)                   │
│                                             │
│  ┌── Case Manager ──────────────────────┐   │
│  │  Multi-party session orchestration    │   │
│  │  Phase tracking (intake → joint →     │   │
│  │    resolution)                        │   │
│  │  Per-party graph isolation            │   │
│  └──────────────────────────────────────┘   │
│                                             │
│  ┌── REST API ──────────────────────────┐   │
│  │  POST /api/cases         (create)    │   │
│  │  GET  /api/cases         (list)      │   │
│  │  GET  /api/cases/:id     (detail)    │   │
│  │  POST /api/cases/:id/upload (docs)   │   │
│  │  POST /api/cases/:id/advance         │   │
│  │  GET  /api/health                    │   │
│  │  GET  /api/graph, /api/status        │   │
│  │  POST /api/set-key                   │   │
│  └──────────────────────────────────────┘   │
│                                             │
│  ┌── WebSocket ─────────────────────────┐   │
│  │  /ws/{case}/{party}/{session} (new)  │   │
│  │  /ws/{user}/{session}         (compat)│  │
│  │  LiveRequestQueue → run_live() bidi  │   │
│  │  Graph broadcast to all parties      │   │
│  └──────────────────────────────────────┘   │
│                                             │
│  ┌── Ingestion Pipeline ────────────────┐   │
│  │  Auto-detect: plain text, email      │   │
│  │    chain, structured JSON            │   │
│  │  Party-attributed extraction         │   │
│  └──────────────────────────────────────┘   │
└────────────────────┬────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────┐
│  Google ADK Agent Hierarchy (4 agents)      │
│                                             │
│  concordia (root — router)                  │
│    └── listener_agent   [11 graph tools]    │
│          └── verifier_agent [3 analysis]    │
│                ├── bridge_agent [3 analysis] │
│                │     └── resolver_agent [3] │
│                └── resolver_agent [3]       │
│                                             │
│  14 tools mutate ──► ConflictGraph          │
│  (8 primitive types + edges + documents)    │
└────────────────────┬────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────┐
│  Gemini Live API                            │
│  • gemini-3-flash-preview (text, default)    │
│  • gemini-3-flash-preview-native-audio      │
│  • Bidi-streaming via LiveRequestQueue      │
└─────────────────────────────────────────────┘
```

---

## Quick Start

### Prerequisites

- Python 3.11+
- A [Google AI API key](https://aistudio.google.com/apikey)

### Install and Run

```bash
# 1. Clone
git clone https://github.com/sargonxg/H_Pjt_NYC_GeminiLive_Med.git
cd H_Pjt_NYC_GeminiLive_Med/concordia

# 2. Virtual environment
python -m venv .venv && source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure
cp app/.env.example app/.env
# Edit app/.env — set GOOGLE_API_KEY=your_key_here

# 5. Run
make dev
# or: cd app && uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

Open **http://localhost:8080** — you'll see the landing page with diagnostics.

### Load Demo Scenarios

```bash
# Load the HR dispute (Alex vs Maya)
make load-demo

# Load all three demo scenarios
make load-all-demos
```

---

## How It Works

### The Mediation Flow

```
Party 1 Intake → Party 2 Intake → Joint Session → Resolution
     │                 │                │              │
  Private chat    Private chat    Bridge agent    Resolver agent
  with listener   with listener   neutral summary  ZOPA analysis
  builds graph    builds graph    guided dialogue  concrete paths
```

1. **Create a case** with 2+ party names
2. **Party 1 intake**: The listener agent has a natural conversation, silently extracting conflict primitives into the knowledge graph
3. **Party 2 intake**: Same process, different perspective — the graph captures structural truth neither party can see alone
4. **Joint session**: The bridge agent presents a neutral structural summary (never revealing raw quotes) and guides dialogue
5. **Resolution**: When the graph reaches 75%+ health, the resolver proposes concrete paths grounded in graph data

### The 4 Agents

| Agent | Role | Tools |
|-------|------|-------|
| **Listener** | Natural conversation + silent graph building. Uses Fisher/Ury interest-based probing, Galtung's conflict triangle, Glasl's escalation model. | 11 graph-building tools |
| **Verifier** | Assesses graph completeness. Identifies gaps and suggests questions. | 3 analysis tools |
| **Bridge** | Joint session facilitator. Presents neutral summaries. Never reveals direct quotes. | 3 analysis tools |
| **Resolver** | ZOPA analysis, leverage balance, narrative bridges. Proposes 2-3 concrete resolution paths. | 3 analysis tools |

### The 8 Conflict Primitives (TACITUS Grammar)

Derived from 8 years of UN Security Council mediation practice:

| Primitive | What It Captures | Example |
|-----------|-----------------|---------|
| **Actor** | People, groups, organizations | "Alex Chen, Senior Developer" |
| **Claim** | Demands, accusations, grievances | "Maya publicly humiliated me in the standup" |
| **Interest** | Underlying needs (security, identity, autonomy) | "I need to feel respected as a professional" |
| **Constraint** | Legal, financial, temporal, structural limits | "HR requires formal complaints within 30 days" |
| **Leverage** | Power dynamics and influence sources | "Maya controls task assignments" |
| **Commitment** | Promises — active, broken, or fulfilled | "They promised a project lead role" |
| **Event** | Timeline of triggers, escalations, agreements | "Tasks reassigned without notice, Q3 2025" |
| **Narrative** | How each party frames the conflict | "This is about workplace bullying" vs "This is about team accountability" |

### Neurosymbolic Design

CONCORDIA combines:
- **Deterministic structure**: The conflict graph is a typed, validated data structure (Pydantic models). Same inputs → same structure.
- **Probabilistic reasoning**: The LLM reasons *over* the graph to find resolution paths — it doesn't hallucinate from memory.
- **Per-party attribution**: Every node tracks who contributed it (`contributed_by` field), enabling per-party health checks and bias detection.

---

## Frontend

The frontend is a single-file React 18 application (`app/static/index.html`) — no build step, CDN-loaded with Babel. It provides:

### Landing Page
- **Active Cases** list with health indicators
- **Create Case** dialog (enter party names)
- **Diagnostics Bar** — real-time server and API key status with actionable error messages

### Mediation Dashboard
- **D3 Force Graph** — live conflict visualization with party-colored glow filters (blue for Party 1, orange for Party 2). Nodes appear with spring animations after each tool call.
- **Chat Panel** — natural conversation with the AI mediator. Supports text input with Enter to send.
- **Intel Panel** — structured view of all graph data organized by primitive type, with conflict health score and gap identification.
- **Tool Feed** — real-time display of agent tool calls (what the AI is extracting).
- **WebSocket Status** — green/red indicator showing connection state.
- **Help Modal** — press `?` or click Help for a full guide to the 8 primitives, mediation flow, and troubleshooting.

### Built-in Diagnostics
The frontend checks `/api/health` on load and displays:
- Server status (running / unreachable)
- Gemini API key status (configured / missing, with link to get one)
- Actionable error messages with copy-paste commands

---

## API Reference

### Case Management

```bash
# Create a case
curl -X POST http://localhost:8080/api/cases \
  -H "Content-Type: application/json" \
  -d '{"title": "Workplace Dispute", "parties": ["Alex", "Maya"]}'

# List all cases
curl http://localhost:8080/api/cases

# Get case details (includes graph, health, party states)
curl http://localhost:8080/api/cases/{case_id}

# Upload a document for a party
curl -X POST http://localhost:8080/api/cases/{case_id}/upload \
  -H "Content-Type: application/json" \
  -d '{"party_id": "party_0", "text": "Here is what happened...", "document_name": "Statement"}'

# Advance mediation phase
curl -X POST http://localhost:8080/api/cases/{case_id}/advance
```

### System

```bash
# Health check (server + Gemini API status)
curl http://localhost:8080/api/health

# Graph state (legacy global graph)
curl http://localhost:8080/api/graph

# Mediation status
curl http://localhost:8080/api/status

# Set API key at runtime (demo only)
curl -X POST http://localhost:8080/api/set-key \
  -H "Content-Type: application/json" \
  -d '{"key": "your_api_key"}'
```

### WebSocket

```
# Multi-party (recommended)
ws://localhost:8080/ws/{case_id}/{party_id}/{session_id}

# Legacy single-user
ws://localhost:8080/ws/{user_id}/{session_id}
```

**Messages sent by client:**
```json
{"type": "text", "content": "Tell me what happened..."}
```

**Messages received from server:**
```json
{"type": "text", "content": "...", "author": "listener_agent"}
{"type": "tool_call", "tool": "add_actor", "args": {...}}
{"type": "graph_update", "graph": {...}, "health": {...}}
{"type": "system", "content": "Your intake data looks comprehensive (score: 82%)"}
{"type": "error", "content": "...", "error_type": "quota_exhausted|internal"}
```

---

## Project Structure

```
concordia/
├── app/
│   ├── main.py                       # FastAPI server (REST + WebSocket + bidi-streaming)
│   ├── config.py                     # Pydantic Settings (env vars, defaults)
│   ├── mediation.py                  # CaseManager, MediationCase, phase tracking
│   ├── ingestion.py                  # Text upload pipeline (auto-detect format)
│   ├── .env.example                  # Environment template
│   ├── concordia_agent/
│   │   ├── __init__.py               # Exports root_agent and graph
│   │   ├── ontology.py               # 8 conflict primitives + ConflictGraph + health scoring
│   │   ├── tools.py                  # 14 tools (11 graph-building + 3 analysis)
│   │   └── agent.py                  # 4 ADK agents (listener, verifier, bridge, resolver)
│   └── static/
│       └── index.html                # React 18 frontend (D3 graph + chat + diagnostics)
├── tests/
│   ├── conftest.py                   # Fixtures (empty_graph, populated_graph, reset_state)
│   ├── test_ontology.py              # 18+ tests: primitives, health, escalation, common ground
│   ├── test_tools.py                 # 14+ tests: all tools, dedup, edges, invalid input
│   ├── test_api.py                   # Integration tests: REST endpoints, static serving
│   └── test_mediation.py             # Async tests: cases, phases, party states, isolation
├── demo/
│   ├── load_scenario.py              # Script to pre-load scenarios via REST API
│   └── scenarios/
│       ├── hr_dispute.json           # Alex vs Maya (workplace, Senior Dev vs Team Lead)
│       ├── lease_dispute.json        # Jordan vs Patricia (tenant vs landlord)
│       └── family_estate.json        # Sarah vs David (sibling estate dispute)
├── requirements.txt                  # Production dependencies
├── requirements-dev.txt              # Dev dependencies (pytest, ruff, httpx)
├── Dockerfile                        # Cloud Run-optimized container
├── .dockerignore                     # Exclude .git, .venv, .env, etc.
├── deploy.sh                         # One-command Cloud Run deployment
├── cloudbuild.yaml                   # Cloud Build CI/CD config
├── Makefile                          # Dev workflow shortcuts
├── DEMO_SCRIPT.md                    # 5-minute hackathon demo script
└── README.md
```

---

## Configuration

All configuration is via environment variables. Copy `app/.env.example` to `app/.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `GOOGLE_API_KEY` | *(required)* | Gemini API key from [AI Studio](https://aistudio.google.com/apikey) |
| `CONCORDIA_MODEL` | `gemini-3-flash-preview` | Model ID. Use `gemini-3-flash-preview-native-audio` for voice mode |
| `GOOGLE_GENAI_USE_VERTEXAI` | `FALSE` | Set `TRUE` to use Vertex AI instead of Gemini API |
| `GOOGLE_CLOUD_PROJECT` | — | GCP project ID (Vertex AI only) |
| `GOOGLE_CLOUD_LOCATION` | `us-central1` | GCP region (Vertex AI only) |
| `MAX_PARTIES_PER_CASE` | `6` | Maximum parties per mediation case |
| `HEALTH_THRESHOLD_PARTY` | `60` | Per-party health score to suggest advancing |
| `HEALTH_THRESHOLD_RESOLVE` | `75` | Overall health score to enable resolution |
| `LOG_LEVEL` | `INFO` | Python logging level |
| `CORS_ORIGINS` | `*` | Allowed CORS origins (comma-separated) |

---

## Testing

```bash
# Install dev dependencies
make install-dev

# Run all tests
make test

# Unit tests only (ontology + tools)
make test-unit

# Integration tests only (API + mediation)
make test-integration

# With coverage report
make test-cov

# Lint
make lint
```

### Test Coverage

- **test_ontology.py** — Primitive creation, UID generation, health check scoring (empty/partial/full/boundary), per-party health, escalation assessment, common ground detection, graph summaries
- **test_tools.py** — All 14 tools: actor dedup, claim edge creation, multi-actor constraints, leverage edges, commitment tracking, event timelines, narrative frames, edge validation, case info, document ingestion, analysis tools, invalid input handling
- **test_api.py** — REST endpoints (graph, health, status, set-key, cases CRUD, upload, advance), error cases (404, 422), static file serving
- **test_mediation.py** — Case creation, party state management, phase advancement, graph isolation between cases, per-party tracking, case summaries

---

## Cloud Run Deployment

### One-Command Deploy

```bash
# Set your GCP project
gcloud config set project YOUR_PROJECT_ID

# Deploy (builds container, deploys with WebSocket support)
make deploy
# or: bash deploy.sh
```

The deploy script configures:
- **Session affinity** — WebSocket connections stay on the same instance
- **1Gi memory, 2 vCPUs** — sufficient for real-time mediation
- **3600s timeout** — 1-hour WebSocket sessions
- **Min 1 instance** — no cold starts during demo
- **Unauthenticated access** — public demo endpoint

### Set API Key After Deploy

```bash
# Option 1: Via the UI (click "Set API Key" in diagnostics bar)
# Option 2: Via CLI
gcloud run services update concordia \
  --region us-central1 \
  --set-env-vars GOOGLE_API_KEY=your_key
```

### Docker (Local)

```bash
make docker-build
make docker-run   # requires GOOGLE_API_KEY env var
```

---

## Demo Scenarios

Three pre-built scenarios for testing and demos:

### HR Dispute (Alex vs Maya)
Senior developer vs team lead. Public criticism, task reassignment without notice, broken promises about project lead role. Tests: workplace power dynamics, procedural interests, commitment repair.

### Lease Dispute (Jordan vs Patricia)
Tenant vs landlord. Mold remediation, rent withholding, lease interpretation disagreement. Tests: contractual constraints, financial leverage, regulatory frameworks.

### Family Estate (Sarah vs David)
Siblings disputing family restaurant inheritance. Emotional attachments, financial needs, legacy preservation. Tests: identity interests, narrative divergence, multi-generational dynamics.

```bash
# Load a scenario
python demo/load_scenario.py demo/scenarios/hr_dispute.json

# Load all scenarios
make load-all-demos
```

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Agent orchestration | [Google ADK](https://google.github.io/adk-docs/) (Agent Development Kit) |
| Real-time AI | Gemini Live API (bidi-streaming, text + voice) |
| Backend | FastAPI (async WebSocket + REST) |
| Data models | Pydantic v2 (typed conflict ontology) |
| Visualization | D3.js v7 (force-directed graph) |
| Frontend | React 18 (single-file, CDN, no build step) |
| Deployment | Docker + Google Cloud Run |
| Testing | pytest + pytest-asyncio + httpx |

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Diagnostics bar shows "Server Unreachable" | Server not running | `make dev` |
| "No API Key" warning | Missing GOOGLE_API_KEY | Get one at [aistudio.google.com/apikey](https://aistudio.google.com/apikey), add to `app/.env` |
| WebSocket red dot | Connection failed | Check browser console; ensure server is on port 8080 |
| "Quota exhausted" error | Gemini API rate limit | Wait 60s and retry; or use a different API key |
| Graph not updating | Agent not calling tools | Try more descriptive input: "Alex accused Maya of..." |
| `ModuleNotFoundError: google` | Dependencies not installed | `pip install --ignore-installed PyYAML -r requirements.txt` |
| Docker build fails | PyYAML conflict | The Dockerfile uses `--no-cache-dir` to avoid this |

---

## Team

**Giulio Catanzariti** — [TACITUS](https://tacitus.me) | Columbia SIPA | 8 years UN Security Council

---

*CONCORDIA: When the picture is complete, the mediator becomes a bridge-builder.*
