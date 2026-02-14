# SpeakNode

> Local-first AI system that analyzes meeting audio, stores structured knowledge in a graph database, and enables intelligent retrieval and sharing.

## Overview

SpeakNode processes meeting audio files through a fully local pipeline:

1. **Transcribe** - Convert speech to text with timestamps via Faster-Whisper
2. **Extract** - Structure topics, decisions, and tasks using Ollama + LangChain
3. **Store** - Persist meeting data as a knowledge graph in KuzuDB
4. **Query** - Answer questions via Hybrid RAG (vector + graph) and a LangGraph agent
5. **Share** - Export/import graph snapshots embedded in PNG metadata

All data stays on your machine.

## Key Features

| Area | Description |
|---|---|
| STT | Faster-Whisper speech recognition with speaker timestamps |
| Extraction | Ollama + LangChain structured extraction (topics, tasks, decisions, people) |
| Graph DB | KuzuDB with node/relationship storage and utterance embeddings |
| Search | Hybrid RAG combining vector similarity and graph traversal |
| Cypher Search | Natural language to read-only Cypher translation |
| Agent | LangGraph-based agent for meeting Q&A, summaries, and email drafts |
| Sharing | Compressed graph dump embedded in PNG metadata for portable sharing |
| Editing | In-app editing of Topic, Task, Person, and Meeting nodes |
| API | FastAPI server with full CRUD endpoints |

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
- `/graph/import` enforces payload size and element count limits.

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
│   ├── config.py              # Central configuration
│   ├── domain.py              # Pydantic domain models
│   ├── utils.py               # Shared utilities
│   ├── embedding.py           # Embedding model singleton
│   ├── pipeline.py            # STT -> Embed -> LLM -> DB pipeline
│   ├── stt/transcriber.py     # Faster-Whisper transcription
│   ├── llm/extractor.py       # LLM-based structured extraction
│   ├── db/kuzu_manager.py     # KuzuDB manager (single DB access point)
│   ├── db/check_db.py         # DB diagnostic script
│   ├── shared/share_manager.py
│   └── agent/
│       ├── agent.py           # LangGraph agent
│       ├── hybrid_rag.py      # Hybrid RAG (vector + graph)
│       └── tools/             # Decorator-based tool registry
├── interfaces/
│   ├── streamlit_app/         # Streamlit demo/test UI
│   └── api_server/server.py   # FastAPI production server
├── kotlin-client/             # Compose Desktop client
├── scripts/api_smoke_test.py
├── docs/api_examples.http
└── requirements.txt
```
## License

CC by NC ND 4.0 license
