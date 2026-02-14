# SpeakNode Project Blueprint (v2.1)

Local meeting knowledge extraction and agent-based retrieval system.

## 1. Architecture

### Core Principle

- Python Brain + Kotlin Body
- Offline-first (local-first), file-based graph memory

### Layers

1. **Core Layer** (Python) - STT, Embedding, Extraction, Graph DB, Agent
2. **Interface Layer A** - Streamlit dashboard for verification and operation
3. **Interface Layer B** - FastAPI server + Kotlin desktop client

## 2. Technical Stack

| Domain | Stack | Role |
|---|---|---|
| STT | Faster-Whisper | Speech to text |
| Embedding | Sentence-Transformers | Utterance vectorization |
| LLM | Ollama + LangChain | Information extraction and response generation |
| Agent | LangGraph | Router-Tool-Synthesizer flow |
| DB | KuzuDB | Graph + vector storage |
| API | FastAPI | Python service layer |
| UI | Streamlit / Kotlin Compose | Operation UI |

## 3. Data Flow

1. **Transcribe** - Convert audio to utterance segments
2. **Embed** - Generate utterance embeddings
3. **Extract** - Structure topics, decisions, tasks, and people
4. **Ingest** - Store as a meeting-scoped graph
5. **Query** - Hybrid RAG + Agent response
6. **Cypher Query** - Natural language to read-only Cypher translation
7. **Share** - Graph dump sharing/restoration via compressed PNG metadata

## 4. Graph Schema (KuzuDB)

### Nodes

```sql
CREATE NODE TABLE Person(name STRING, role STRING, PRIMARY KEY(name));
CREATE NODE TABLE Topic(title STRING, summary STRING, PRIMARY KEY(title));
CREATE NODE TABLE Task(description STRING, deadline STRING, status STRING, PRIMARY KEY(description));
CREATE NODE TABLE Decision(description STRING, PRIMARY KEY(description));
CREATE NODE TABLE Utterance(
  id STRING,
  text STRING,
  startTime FLOAT,
  endTime FLOAT,
  embedding FLOAT[384],
  PRIMARY KEY(id)
);
CREATE NODE TABLE Meeting(id STRING, title STRING, date STRING, source_file STRING, PRIMARY KEY(id));
```

### Relationships

```sql
CREATE REL TABLE PROPOSED(FROM Person TO Topic);
CREATE REL TABLE ASSIGNED_TO(FROM Person TO Task);
CREATE REL TABLE RESULTED_IN(FROM Topic TO Decision);
CREATE REL TABLE SPOKE(FROM Person TO Utterance);
CREATE REL TABLE NEXT(FROM Utterance TO Utterance);
CREATE REL TABLE DISCUSSED(FROM Meeting TO Topic);
CREATE REL TABLE CONTAINS(FROM Meeting TO Utterance);
CREATE REL TABLE HAS_TASK(FROM Meeting TO Task);
CREATE REL TABLE HAS_DECISION(FROM Meeting TO Decision);
```

## 5. API Scope (Phase 5.1)

| Method | Endpoint | Description |
|---|---|---|
| POST | `/analyze` | File analysis and graph ingestion |
| POST | `/agent/query` | Agent query |
| GET | `/chats` | List chat sessions |
| POST | `/chats` | Create chat session |
| DELETE | `/chats/{chat_id}` | Reset chat DB |
| GET | `/meetings` | List meetings |
| GET | `/meetings/{meeting_id}` | Meeting details |
| GET | `/graph/export` | Export graph dump (optional `include_embeddings`) |
| POST | `/graph/import` | Import graph dump |
| PATCH | `/nodes/update` | Update node properties |

## 6. Directory Structure

```text
SpeakNode/
├── core/
│   ├── config.py              # Central configuration + chat utilities
│   ├── domain.py              # Pydantic domain models
│   ├── utils.py               # Shared business logic (task status normalization)
│   ├── embedding.py           # Embedding model singleton cache
│   ├── pipeline.py            # STT -> Embed -> LLM -> DB pipeline
│   ├── stt/transcriber.py
│   ├── llm/extractor.py
│   ├── db/
│   │   ├── kuzu_manager.py    # KuzuDB unified manager (sole DB access point)
│   │   └── check_db.py        # DB diagnostic script
│   ├── shared/share_manager.py
│   └── agent/
│       ├── agent.py           # LangGraph agent (query-scoped DB lifecycle)
│       ├── hybrid_rag.py      # Hybrid RAG (vector + graph)
│       └── tools/             # Decorator-based tool registry
├── interfaces/
│   ├── streamlit_app/
│   │   ├── app.py
│   │   └── view_components.py
│   └── api_server/server.py   # FastAPI + CORS
├── kotlin-client/             # Compose Desktop client (Phase 5.2)
│   ├── build.gradle.kts
│   ├── settings.gradle.kts
│   └── src/main/kotlin/com/speaknode/client/
│       ├── Main.kt
│       ├── api/               # Ktor HTTP client + models
│       ├── ui/                # Compose Material 3 UI
│       └── viewmodel/         # StateFlow-based state management
├── scripts/api_smoke_test.py
├── docs/api_examples.http
└── requirements.txt
```

## 7. Phase 5.1 Completion Criteria

- File upload validation (extension/size) applied
- Per-chat synchronization lock applied
- Meeting/graph query and restoration API provided
- Node property update API provided
- Smoke test script provided
- HTTP request collection provided
- Graph import protection (size/element limits) applied
- Meeting-scoped key-based entity collision prevention applied

## 8. Phase 5.2 Completion Criteria

- CORS middleware applied (environment-variable-based origin configuration)
- Compose Multiplatform Desktop project set up
- Ktor-based API client covering all endpoints
- Kotlinx Serialization request/response models defined
- Material 3 dark theme UI
- 2-pane layout (sidebar + content)
- Meeting analysis/list screen
- Agent conversation screen
- StateFlow-based reactive state management

## 9. Roadmap Status

- Phase 1 Foundation: Complete
- Phase 2 Core Logic: Complete
- Phase 3 Prototype UI: Complete
- Phase 3.5 Vector Memory: Complete
- Phase 4 Intelligent Agent: Complete
- Phase 5.1 FastAPI Hardening: Complete
- Phase 5.2 Kotlin Client: Complete
