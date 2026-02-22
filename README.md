# SpeakNode

> Local-first AI system that analyzes meeting audio, extracts structured knowledge into a graph database, and enables intelligent retrieval — all running on your machine.

## Overview

SpeakNode processes meeting audio through a fully local pipeline and exposes the results through a single Streamlit desktop app.

<img src="https://github.com/user-attachments/assets/78766c52-be0b-4068-a446-e045aa883ec4" width="500">

-> web demo - only knowledge graph rendering % Summary of DB contents

1. **Transcribe** — Convert speech to text with timestamps via Faster-Whisper (optional pyannote speaker diarization)
2. **Embed** — Generate utterance embeddings (all-MiniLM-L6-v2, 384 dimensions)
3. **Extract** — Structure topics, decisions, tasks, people, entities, and relations using Ollama + LangChain
4. **Store** — Persist each meeting as an independent KuzuDB graph directory (`database/meetings/{meeting_id}/`)
5. **Query** — Answer questions via Hybrid RAG (vector + graph + Cypher) and a LangGraph agent
6. **Share** — Export/import graph snapshots embedded in PNG metadata (zlib + base64)

All data stays on your machine.

## Key Features

| Area | Description |
|---|---|
| STT | Faster-Whisper 1.2.1 (Whisper large-v3, Korean default) |
| Speaker Diarization | Optional pyannote.audio 3.3.0 speaker separation |
| Embedding | Sentence-Transformers 5.2.2 (all-MiniLM-L6-v2, 384d) |
| Extraction | Ollama + LangChain structured extraction (topics, tasks, decisions, people, entities, relations) |
| Graph DB | KuzuDB 0.11.3 — 1 meeting = 1 independent DB directory, 7 node types, 12 relationship types |
| Search | Hybrid RAG: vector similarity + graph traversal + Cypher + Entity search |
| Agent | LangGraph 1.0.8 agent with 7 tools (search, summary, email draft, Cypher, direct answer) |
| Sharing | Compressed graph dump embedded in PNG metadata (`speaknode_graph_bundle_v1`) |
| Editing | In-app editing of Topic, Task, Person, Meeting, and Entity nodes |

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
streamlit run streamlit_app/app.py
```

## Agent Tools

| Tool | Description |
|---|---|
| `search_by_meaning` | Vector-based semantic search (Utterance cosine similarity) |
| `search_by_structure` | Structural graph traversal (topic/task/decision/person/meeting/entity) |
| `hybrid_search` | Combined semantic + structural search |
| `search_by_cypher` | NL → read-only Cypher translation + execution |
| `get_meeting_summary` | Meeting summary retrieval |
| `draft_email` | Draft email based on meeting results |
| `direct_answer` | Direct answer for DB-independent questions |

## DB Strategy

Each audio analysis creates a new independent KuzuDB directory:

```
database/
└── meetings/
    ├── m_20260221_143000_123456/   ← one directory per meeting
    │   ├── metadata.json           ← title, date, source_file (for fast UI listing)
    │   └── <kuzu internal files>
    └── m_20260220_091500_654321/
```

- No cross-meeting key scoping needed — PKs are plain text within each isolated DB.
- `metadata.json` enables the Streamlit sidebar to display friendly meeting labels without opening KuzuDB.

Standard task statuses: `pending`, `in_progress`, `done`, `blocked`

## Project Structure

```text
SpeakNode/
├── core/
│   ├── config.py              # Central config + meeting DB path helpers
│   ├── domain.py              # Pydantic domain models (incl. MeetingSummary)
│   ├── utils.py               # Task status normalization, token estimation
│   ├── embedding.py           # SentenceTransformer singleton
│   ├── pipeline.py            # SpeakNodeEngine: STT → Embed → LLM → DB
│   ├── stt/transcriber.py     # Faster-Whisper + optional pyannote diarization
│   ├── llm/extractor.py       # Ollama structured extraction
│   ├── db/
│   │   ├── kuzu_manager.py    # KuzuDB manager (schema v3, CRUD, vector search, export/import)
│   │   └── check_db.py        # DB diagnostic utility (node counts, topic samples)
│   ├── shared/share_manager.py # PNG metadata graph sharing
│   └── agent/
│       ├── agent.py           # LangGraph agent (Router → Tool → Synthesizer)
│       ├── hybrid_rag.py      # Hybrid RAG engine
│       └── tools/             # ToolRegistry + 7 tools
├── streamlit_app/
│   ├── app.py             # Streamlit app (meeting selection, analysis, agent UI)
│   └── view_components.py # Graph viewer, node editor, PNG export/import
├── database/
│   └── meetings/              # Per-meeting KuzuDB directories (auto-created)
├── docs/
│   ├── index.html             # Interactive knowledge graph demo
│   └── demos/                 # Demo assets
├── requirements.txt
└── README.md
```

## License

Apache 2.0

[Project Detail Architecture and Planning Document](project.md)
