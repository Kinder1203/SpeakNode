# SpeakNode

> Local-first AI system that analyzes meeting audio, stores structured knowledge in a graph database, and enables intelligent retrieval and sharing.

## Overview

SpeakNode processes meeting audio files through a fully local pipeline:

1. **Transcribe** — Convert speech to text with timestamps via Faster-Whisper (optional pyannote speaker diarization)
2. **Embed** — Generate utterance embeddings (all-MiniLM-L6-v2, 384 dimensions)
3. **Extract** — Structure topics, decisions, tasks, and people using Ollama + LangChain (conservative Korean signal-based extraction)
4. **Store** — Persist meeting data as a knowledge graph in KuzuDB (meeting-scoped keys)
5. **Query** — Answer questions via Hybrid RAG (vector + graph + Cypher) and a LangGraph agent
6. **Share** — Export/import graph snapshots embedded in PNG metadata (zlib + base64)

All data stays on your machine.

## Key Features

| Area | Description |
|---|---|
| STT | Faster-Whisper 1.2.1 speech recognition with speaker timestamps (Whisper large-v3) |
| Speaker Diarization | Optional pyannote.audio 3.3.0 speaker separation |
| Embedding | Sentence-Transformers 5.2.2 (all-MiniLM-L6-v2, 384d) |
| Extraction | Ollama + LangChain 1.2.10 structured extraction (topics, tasks, decisions, people) |
| Graph DB | KuzuDB 0.11.3 with node/relationship storage and utterance vector embeddings |
| Search | Hybrid RAG combining vector similarity, graph traversal, and Cypher queries |
| Cypher Search | Natural language to read-only Cypher translation with forbidden token validation |
| Agent | LangGraph 1.0.8 agent with 7 tools (search, summary, email draft, Cypher, direct answer) |
| Sharing | Compressed graph dump embedded in PNG metadata (`speaknode_graph_bundle_v1` format) |
| Editing | In-app editing of Topic, Task, Person, and Meeting nodes |
| API | FastAPI 0.129.0 server with full CRUD endpoints, async locks, and file validation |
| Desktop Client | Kotlin Compose Multiplatform 1.7.3 with Material 3 dark theme |

## Quick Start

### 1) Prerequisites

- Python 3.10+
- [Ollama](https://ollama.ai) with a model pulled (e.g. `qwen2.5:14b`)
- CUDA-capable GPU recommended for STT

### 2) Install

```bash
git clone <repo-url> && cd SpeakNode
pip install -r requirements.txt
ollama pull qwen2.5:14b
```

### 3) Run

```bash
# Streamlit UI
streamlit run interfaces/streamlit_app/app.py

# FastAPI server
uvicorn interfaces.api_server.server:app --host 0.0.0.0 --port 8000
```

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Server health check |
| POST | `/analyze` | Upload and analyze audio, store results in graph |
| POST | `/agent/query` | Query the agent |
| GET | `/meetings` | List meetings |
| GET | `/meetings/{meeting_id}` | Get meeting summary |
| GET | `/graph/export` | Export graph dump (optional `include_embeddings`) |
| POST | `/graph/import` | Import graph dump |
| PATCH | `/nodes/update` | Update node properties |
| GET/POST/DELETE | `/chats` | Chat session management |

Standard task statuses: `pending`, `in_progress`, `done`, `blocked`

Data integrity:
- Entities use meeting-scoped keys (`meeting_id::value`) to prevent cross-meeting collisions.
- `/nodes/update` accepts display values and falls back to scoped IDs on ambiguity.
- `/graph/import` enforces payload size (25MB) and element count (200K) limits.
- Per-chat `asyncio.Lock` for concurrency control.
- File upload validation: extensions (`.mp3`, `.wav`, `.m4a`), size limit (512MB).

CORS configuration via environment variable:
```bash
export SPEAKNODE_CORS_ORIGINS="http://localhost:3000,http://localhost:8080"
```

## Agent Tools

| Tool | Description |
|---|---|
| `search_by_meaning` | Vector-based semantic search (Utterance cosine similarity) |
| `search_by_structure` | Structural graph traversal (topic/task/decision/person/meeting) |
| `hybrid_search` | Combined semantic + structural search |
| `search_by_cypher` | NL → read-only Cypher translation + execution |
| `get_meeting_summary` | Meeting summary retrieval |
| `draft_email` | Draft email based on meeting results |
| `direct_answer` | Direct answer for DB-independent questions |

## Validation

```bash
# Start the API server
uvicorn interfaces.api_server.server:app --host 0.0.0.0 --port 8000

# Basic endpoint smoke test
python scripts/api_smoke_test.py --base-url http://127.0.0.1:8000

# Full test with audio analysis
python scripts/api_smoke_test.py \
  --base-url http://127.0.0.1:8000 \
  --audio ./sample.wav \
  --meeting-title "Smoke Test Meeting"
```

A manual HTTP request collection is available at `docs/api_examples.http` (VS Code REST Client or JetBrains HTTP Client).

## Project Structure

```text
SpeakNode/
├── core/
│   ├── __init__.py
│   ├── config.py              # Central configuration + chat session utilities
│   ├── domain.py              # Pydantic domain models
│   ├── utils.py               # Shared utilities (task status normalization, LLM token estimation)
│   ├── embedding.py           # SentenceTransformer singleton cache
│   ├── pipeline.py            # SpeakNodeEngine: STT → Embed → LLM → DB pipeline
│   ├── stt/
│   │   └── transcriber.py     # Faster-Whisper STT + optional pyannote diarization
│   ├── llm/
│   │   └── extractor.py       # LangChain/Ollama structured extraction
│   ├── db/
│   │   ├── kuzu_manager.py    # KuzuDB unified manager (schema, CRUD, vector search, export/import)
│   │   └── check_db.py        # DB diagnostic CLI script
│   ├── shared/
│   │   └── share_manager.py   # PNG metadata graph sharing (zlib + base64)
│   └── agent/
│       ├── agent.py           # LangGraph agent (Router → Tool → Synthesizer)
│       ├── hybrid_rag.py      # Hybrid RAG engine (vector + graph + Cypher)
│       └── tools/
│           ├── __init__.py    # Decorator-based ToolRegistry
│           ├── search_tools.py
│           ├── cypher_tools.py
│           ├── meeting_tools.py
│           ├── email_tools.py
│           └── general_tools.py
├── interfaces/
│   ├── streamlit_app/
│   │   ├── app.py             # Streamlit dashboard (multi-chat sessions)
│   │   └── view_components.py # UI components (graph viewer, node editor, card export/import)
│   └── api_server/
│       └── server.py          # FastAPI v5.2.0 (CORS, async locks, ThreadPoolExecutor)
├── kotlin-client/
│   ├── build.gradle.kts       # Compose Desktop build config
│   ├── settings.gradle.kts
│   └── src/main/kotlin/com/speaknode/client/
│       ├── Main.kt            # Entry point (1200×800 window)
│       ├── api/               # Ktor HTTP client + @Serializable models
│       ├── ui/                # Compose Material 3 UI (2-pane layout)
│       └── viewmodel/         # StateFlow-based state management
├── database/
│   └── chats/                 # Per-chat KuzuDB files
├── lib/
│   ├── bindings/utils.js      # PyVis network neighbor highlight utility
│   ├── tom-select/            # Tom Select dropdown library
│   └── vis-9.1.2/             # vis-network graph visualization
├── shared_cards/              # Shared card PNG output directory
├── scripts/
│   └── api_smoke_test.py      # API smoke test (stdlib only)
├── docs/
│   └── api_examples.http      # HTTP request collection (11 examples)
└── requirements.txt
```
## License

This project is licensed under the GNU Affero General Public License v3.0 (AGPL-3.0).
Commercial use requires a separate agreement.

[Project Detail Architecture and Planning Document](project.md)