# CONCORDIA — Hackathon Demo Script (5 minutes)

## Setup (before demo)

```bash
# Start server
cd concordia/app && uvicorn main:app --port 8080

# In another terminal, pre-load the HR scenario
python demo/load_scenario.py demo/scenarios/hr_dispute.json
```

Open http://localhost:8080 — verify the case appears in "Active Cases."

---

## [0:00–0:30] THE HOOK

> "Every conflict has a grammar. CONCORDIA is the first AI that speaks it."

- Show the landing page — dark, premium, clean
- Point to the tagline: *"When the picture is complete, the mediator becomes a bridge-builder."*
- Click the pre-loaded HR dispute case

---

## [0:30–2:00] THE BUILD

The graph should already have nodes from the pre-loaded scenario.

> "Two employees are in a workplace dispute. Alex says Maya publicly humiliated him. Maya says Alex is blocking the team."

- Point to the **D3 graph**: "Every name, claim, and underlying interest becomes a node in the conflict knowledge graph."
- Point to the **left panel** (tool feed): "Watch — the AI is silently extracting structural primitives."
- Point to the **health bar**: "The system knows what it knows — and what it's missing."
- Click a **gap** in the right panel: "It identifies exactly what questions to ask next."

If you want to add more data live, type in the chat:

> "Alex also mentioned that Maya reassigned two of his tasks without telling him last quarter."

Watch a new node (Event) appear with a spring animation.

---

## [2:00–3:00] THE SWITCH

- Click the **Bob/Maya tab** to show the other party's perspective
- Point to the **different glow colors** on nodes — blue for Party 1, orange for Party 2

> "Now Maya gets her turn. Same conflict, different perspective. The graph captures structural truth that neither party can see alone."

- Point to **shared interests** in the right panel: "Both care about clear process — that's the foundation."

---

## [3:00–4:00] THE RESOLUTION

- Health should be at 75%+ — the "Ready for Resolution" badge is visible
- Click "Move to Resolution" if needed

> "The picture is complete. Now watch what happens."

- Show the **common ground analysis**: "They share procedural interests — both want clear rules."
- Show the **leverage balance**: "Maya has structural authority; Alex has institutional knowledge."
- The agent proposes concrete paths:

> "Resolution paths grounded in the data — not opinions, not gut feelings."

---

## [4:00–5:00] THE WHY

> "8 conflict primitives derived from UN Security Council mediation practice."

Point to the legend:

> "Actor, Claim, Interest, Constraint, Leverage, Commitment, Event, Narrative — this grammar captures any human dispute."

Technical highlights:

- "Built on **Google ADK + Gemini Live API** for real-time voice or text"
- "**TACITUS** — the governed data layer that makes conflict legible to machines"
- "Deploys on **Cloud Run** in one command"
- "Graph builds **live** — every tool call pushes a WebSocket update"

> "CONCORDIA doesn't replace mediators. It gives them X-ray vision."

**Open for questions.**

---

## Backup talking points

- **"How is this different from ChatGPT?"**
  It doesn't just talk — it builds a structured knowledge graph with 8 typed primitives. Every claim, interest, and power dynamic is tracked as data, not just conversation.

- **"What about bias?"**
  The graph is deterministic — same inputs, same structure. The LLM reasons *over* the graph, not from memory. Each party gets a private intake session. The bridge agent never reveals raw quotes.

- **"Can it handle real disputes?"**
  The ontology comes from 8 years of UN Security Council mediation practice. We've tested it with workplace, family, landlord-tenant, and geopolitical scenarios.

- **"What's next?"**
  Multi-modal evidence (photos of damage, signed contracts), temporal graph evolution (how conflicts change over time), and integration with existing mediation platforms.
