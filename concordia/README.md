# CONCORDIA

**Live AI mediation agent that builds a conflict knowledge graph in real time.**

Built for the NYC Build W/ AI Hackathon (Google Cloud Labs x Columbia Business School, March 2026).

**Repository:** https://github.com/sargonxg/H_Pjt_NYC_GeminiLive_Med

## What It Does

Parties to a dispute talk naturally — alone or together — while a conflict knowledge graph builds live on screen. CONCORDIA listens, extracts structural primitives (actors, claims, interests, leverage, narratives...), and visualizes them as a D3 force graph. When the picture is complete, the agent shifts from listener to bridge-builder, proposing concrete resolution paths grounded in the graph data.

## Architecture

```
Browser (WebSocket + Audio)
        │
        ▼
┌──────────────────────────┐
│  FastAPI Server (main.py)│
│  - WebSocket bidi-stream │
│  - LiveRequestQueue      │
│  - run_live() + RunConfig│
│  - REST: /api/graph,     │
│    /api/health, /api/status
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────────────────────┐
│  Google ADK Agent Hierarchy              │
│                                          │
│  concordia (root)                        │
│    └── listener_agent   [11 tools]       │
│          └── verifier_agent [3 tools]    │
│                └── resolver_agent [3]    │
│                                          │
│  Tools mutate ──► ConflictGraph (8 types)│
└──────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────┐
│  Gemini Live API         │
│  - gemini-2.0-flash      │
│  - Voice + Text          │
└──────────────────────────┘
```

## Quick Start

```bash
# 1. Clone
git clone https://github.com/sargonxg/H_Pjt_NYC_GeminiLive_Med.git
cd H_Pjt_NYC_GeminiLive_Med/concordia

# 2. Virtual environment
python -m venv .venv && source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp app/.env.example app/.env
# Edit app/.env with your GOOGLE_API_KEY

# 5. Run
cd app
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

Then open http://localhost:8080 — you'll see the full UI with chat, live D3 graph, and stats panel.

## Project Structure

```
concordia/
├── app/
│   ├── main.py                    # FastAPI bidi-streaming server
│   ├── .env.example               # Environment template
│   ├── concordia_agent/
│   │   ├── __init__.py            # Exports root_agent and graph
│   │   ├── ontology.py            # 8 conflict primitives + ConflictGraph
│   │   ├── tools.py               # 14 tools the agent calls
│   │   └── agent.py               # 3 ADK agents
│   └── static/
│       └── index.html             # Frontend (D3 graph + chat + audio)
├── requirements.txt
├── Dockerfile
├── .gitignore
└── README.md
```

## How It Works

**Gemini Live API** enables real-time, bidirectional voice/text conversations. The server uses:

- **`LiveRequestQueue`** — queues audio/text frames from the WebSocket into the ADK pipeline
- **`run_live()`** — streams agent responses back through the WebSocket
- **`RunConfig`** — configures the model, tools, and streaming behavior

The key innovation: after **every tool call**, the server pushes the updated graph to the frontend via WebSocket `graph_update` messages. This means the D3 visualization updates live — nodes appear with smooth animations as the agent silently extracts conflict primitives during conversation.

## The 3 Agents

| Agent | Role | Tools |
|-------|------|-------|
| **Listener** | Natural conversation + silent graph building | 11 graph-building tools |
| **Verifier** | Completeness assessment + gap identification | 3 analysis tools |
| **Resolver** | Common ground analysis + resolution proposals | 3 analysis tools |

## The 8 Conflict Primitives

Derived from UN Security Council mediation practice:

| Primitive | What It Captures |
|-----------|-----------------|
| **Actor** | People, groups, organizations involved |
| **Claim** | Demands, accusations, grievances, proposals |
| **Interest** | Underlying needs (security, identity, autonomy...) |
| **Constraint** | Legal, financial, temporal, structural limits |
| **Leverage** | Power dynamics and influence sources |
| **Commitment** | Promises made — active, broken, or fulfilled |
| **Event** | Timeline of triggers, escalations, agreements |
| **Narrative** | How each party frames the story |

## Cloud Run Deployment

```bash
gcloud run deploy concordia \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GOOGLE_API_KEY=your_key,CONCORDIA_MODEL=gemini-2.0-flash
```

WebSocket connections have a 60-minute timeout on Cloud Run. The `session_resumption` in RunConfig handles reconnection automatically.

## Tech Stack

- **Google ADK** (Agent Development Kit) — agent orchestration
- **Gemini Live API** — real-time voice/text AI
- **FastAPI** — async WebSocket server
- **D3.js** — force-directed graph visualization
- **Pydantic** — conflict ontology data models
- **Docker / Cloud Run** — deployment

## Team

**Giulio Catanzariti** — [TACITUS](https://tacitus.me) | Columbia SIPA | 8 years UN Security Council

---

*CONCORDIA: When the picture is complete, the mediator becomes a bridge-builder.*
