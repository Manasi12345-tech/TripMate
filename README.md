# TripMate

TripMate is an AI-powered travel planning assistant that combines flight search, hotel discovery, and itinerary generation into a single conversational web app. It uses a multi-agent pipeline built with LangGraph to coordinate specialized agents that each handle a distinct part of the planning workflow.

## Features

- **Flight search** — looks up live flight status via the AviationStack API, resolving natural language like "flights from Mumbai to Tokyo" to IATA codes automatically
- **Hotel discovery** — finds hotel recommendations using Tavily AI-powered web search
- **Itinerary generation** — produces a structured day-by-day travel plan from the combined flight and hotel data
- **Conversation memory** — persists conversation state per user in PostgreSQL so follow-up messages are context-aware across server restarts
- **Chat UI** — a browser-based interface served at `http://localhost:8000`

## Architecture

```
User query
    │
    ▼
flight_agent   → AviationStack API (live flight status)
    │
    ▼
hotel_agent    → Tavily web search
    │
    ▼
itinerary_agent → LLM (day-by-day plan)
    │
    ▼
final_agent    → LLM (formatted response)
    │
    ▼
JSON response → browser
```

The pipeline is defined as a LangGraph `StateGraph`. A shared `TravelState` dict flows through all four nodes, accumulating results. A `PostgresSaver` checkpointer saves state after every node so conversations are durable and multi-user safe via `thread_id` isolation.

## Technology Stack

| Layer | Technology |
|---|---|
| Web framework | FastAPI + Uvicorn |
| AI pipeline | LangGraph |
| LLM | Groq (`openai/gpt-oss-120b` via LangChain-Groq) |
| Flight data | AviationStack API |
| Hotel/web search | Tavily |
| Conversation persistence | PostgreSQL (via psycopg3 + LangGraph checkpoint) |
| HTML templating | Jinja2 |
| Language | Python 3.13 |
| Package manager | uv |

## Prerequisites

- Python 3.13
- [uv](https://docs.astral.sh/uv/) package manager
- A PostgreSQL database (e.g. Render free tier)
- API keys for Groq, AviationStack, and Tavily

## Setup

**1. Clone and install dependencies**

```bash
git clone <repo-url>
cd TripMate
uv sync
```

**2. Create a `.env` file**

```env
GROQ_API_KEY=your_groq_api_key
AVIATIONSTACK_API_KEY=your_aviationstack_api_key
TAVILY_API_KEY=your_tavily_api_key
DATABASE_URL=postgresql://user:password@host:port/dbname
DEFAULT_ORIGIN_IATA=BOM   # your home airport IATA code
```

`DATABASE_URL` should be the external connection string from your Postgres provider. TripMate automatically appends `sslmode=require` if it is not already present.

**3. Run the app**

```bash
uv run python app.py
```

The server starts at `http://127.0.0.1:8000`. The LangGraph checkpointer creates its tables in Postgres automatically on first run.

## Project Structure

```
TripMate/
├── app.py           # FastAPI server — routes and request handling
├── backend.py       # LangGraph pipeline — four agents wired into a graph
├── tools/
│   ├── flight_tool.py   # AviationStack API client + IATA location resolver
│   └── tavily_tool.py   # Tavily web search wrapper
├── templates/
│   └── index.html   # Chat UI
├── static/
│   ├── script.js    # Frontend logic
│   └── style.css    # Styles
├── pyproject.toml   # Project metadata and dependencies
└── requirements.txt # Pinned dependency list
```

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Serves the chat UI |
| `POST` | `/api/travel` | Accepts `{ "message": "...", "thread_id": null }` and returns the travel plan |
| `GET` | `/health` | Health check — returns `{ "status": "ok" }` |

The `thread_id` returned by `/api/travel` can be passed in subsequent requests to continue the same conversation.

## Notes on Flight Data

AviationStack provides **live flight status** (departure/arrival times, gate, delay), not ticket prices. If pricing information is needed, a fare-pricing API such as Amadeus would need to be integrated.
