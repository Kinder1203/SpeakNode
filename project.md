# SpeakNode Project Blueprint (v2.2)

Local meeting knowledge extraction and agent-based retrieval system.

## 1. Architecture

### Core Principle

- Python Brain + Kotlin Body
- Offline-first (local-first), file-based graph memory

### Layers

1. **Core Layer** (Python) — STT, Embedding, Extraction, Graph DB, Agent
2. **Interface Layer A** — Streamlit dashboard for verification and operation
3. **Interface Layer B** — FastAPI server (v5.2.0) + Kotlin Compose Desktop client

## 2. Technical Stack

| Domain | Stack | Version | Role |
|---|---|---|---|
| STT | Faster-Whisper | 1.2.1 | Speech to text (Whisper large-v3, Korean default) |
| Speaker Diarization | pyannote.audio | 3.3.0 (optional) | Speaker separation |
| Embedding | Sentence-Transformers | 5.2.2 | Utterance vectorization (all-MiniLM-L6-v2, 384d) |
| LLM | Ollama + LangChain | 1.2.10 | Information extraction and response generation |
| Agent | LangGraph | 1.0.8 | Router-Tool-Synthesizer flow |
| DB | KuzuDB | 0.11.3 | Graph + vector storage (cosine similarity) |
| Data Model | Pydantic | 2.12.5 | Domain model validation |
| API | FastAPI + Uvicorn | 0.129.0 / 0.40.0 | Python service layer |
| UI (Python) | Streamlit + PyVis | 1.54.0 / 0.3.2 | Operation UI + graph visualization |
| UI (Desktop) | Compose Multiplatform | 1.7.3 | Kotlin desktop client (Material 3) |
| HTTP Client | Ktor | 3.0.3 | Kotlin API client (CIO engine) |
| Serialization | Kotlinx Serialization | 1.7.3 | Request/Response models |
| GPU | PyTorch | 2.8.0 | CUDA acceleration for STT |

## 3. Data Flow

1. **Transcribe** — Convert audio to utterance segments (optional speaker diarization)
2. **Embed** — Generate utterance embeddings (all-MiniLM-L6-v2, 384d)
3. **Extract** — Structure topics, decisions, tasks, and people (conservative Korean signal-based extraction)
4. **Ingest** — Store as a meeting-scoped graph (scoped keys: `meeting_id::value`)
5. **Query** — Hybrid RAG + Agent response (vector + graph + Cypher)
6. **Cypher Query** — Natural language to read-only Cypher translation (forbidden token validation)
7. **Share** — Graph dump sharing/restoration via compressed PNG metadata (`speaknode_graph_bundle_v1`)

## 4. Graph Schema (KuzuDB)

### Nodes (6 tables)

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

### Relationships (9 tables)

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

### Scoping Strategy

Topic/Task/Decision primary keys use `{meeting_id}::{plain_text}` format to prevent cross-meeting entity collisions. Decoding via `decode_scoped_value()` / `extract_scope_from_value()` utilities.

## 5. API Scope (FastAPI v5.2.0)

| Method | Endpoint | Description | Key Parameters |
|---|---|---|---|
| GET | `/health` | Server health check | — |
| GET | `/chats` | List chat sessions | — |
| POST | `/chats` | Create chat session | `chat_id` (body) |
| DELETE | `/chats/{chat_id}` | Reset chat DB | `chat_id` (path) |
| POST | `/analyze` | Audio analysis + graph ingestion | `file` (multipart), `chat_id`, `meeting_title` (form) |
| POST | `/agent/query` | Agent query | `question`, `chat_id` (body) |
| GET | `/meetings` | List meetings | `chat_id`, `limit` (query) |
| GET | `/meetings/{meeting_id}` | Meeting details | `meeting_id` (path), `chat_id` (query) |
| GET | `/graph/export` | Export graph dump | `chat_id`, `include_embeddings` (query) |
| POST | `/graph/import` | Import graph dump | `chat_id`, `graph_dump` (body) |
| PATCH | `/nodes/update` | Update node properties | `chat_id`, `node_type`, `node_id`, `fields` (body) |

### Server Protection

- **CORS**: Environment variable `SPEAKNODE_CORS_ORIGINS` (default: `http://localhost:3000`)
- **File upload**: Extension validation (`.mp3`, `.wav`, `.m4a`), size limit (512MB)
- **Graph import**: Body size limit (25MB), element count limit (200K)
- **Per-chat async lock**: `asyncio.Lock` per chat session for concurrency control
- **Node update rules**: Whitelisted `node_type`/`fields` + task status validation
- **ThreadPoolExecutor**: Separate workers for analyze/agent CPU tasks

## 6. Agent Architecture

### Tools (7)

| Tool | Description | Source |
|---|---|---|
| `search_by_meaning` | Vector-based semantic search (Utterance similarity) | search_tools.py |
| `search_by_structure` | Structural graph traversal (topic/task/decision/person/meeting) | search_tools.py |
| `hybrid_search` | Combined semantic + structural search | search_tools.py |
| `search_by_cypher` | NL → read-only Cypher translation + execution | cypher_tools.py |
| `get_meeting_summary` | Meeting summary retrieval | meeting_tools.py |
| `draft_email` | Draft email based on meeting results | email_tools.py |
| `direct_answer` | Direct answer for DB-independent questions | general_tools.py |

### Flow

LangGraph 3-node graph:
1. **Router** (JSON format LLM) → Tool selection
2. **Tool Executor** → ToolRegistry decorator-based execution
3. **Synthesizer** (free-form LLM) → Natural language response generation

DB lifecycle is managed per `query()` invocation scope.

## 7. Directory Structure

```text
SpeakNode/
├── core/
│   ├── __init__.py
│   ├── config.py              # Central configuration + chat session utilities
│   ├── domain.py              # Pydantic domain models (Utterance, Person, Topic, Task, Decision, Meeting, AnalysisResult, MeetingSummary)
│   ├── utils.py               # Shared business logic (task status normalization, LLM token estimation/truncation)
│   ├── embedding.py           # SentenceTransformer singleton cache
│   ├── pipeline.py            # SpeakNodeEngine: STT → Embed → LLM → DB pipeline (lazy loading, thread-safe)
│   ├── stt/
│   │   └── transcriber.py     # Faster-Whisper STT + optional pyannote speaker diarization
│   ├── llm/
│   │   └── extractor.py       # LangChain/Ollama structured extraction (conservative Korean signal patterns)
│   ├── db/
│   │   ├── kuzu_manager.py    # KuzuDB unified manager (schema, CRUD, vector search, export/import, transactions)
│   │   └── check_db.py        # DB diagnostic CLI script
│   ├── shared/
│   │   └── share_manager.py   # PNG metadata graph sharing (zlib + base64, speaknode_graph_bundle_v1)
│   └── agent/
│       ├── agent.py           # LangGraph agent (Router → Tool → Synthesizer, query-scoped DB lifecycle)
│       ├── hybrid_rag.py      # Hybrid RAG engine (vector + graph + Cypher search)
│       └── tools/
│           ├── __init__.py    # Decorator-based ToolRegistry
│           ├── search_tools.py
│           ├── cypher_tools.py
│           ├── meeting_tools.py
│           ├── email_tools.py
│           └── general_tools.py
├── interfaces/
│   ├── streamlit_app/
│   │   ├── app.py             # Streamlit dashboard (multi-chat session management)
│   │   └── view_components.py # UI components (graph viewer, node editor, card export/import)
│   └── api_server/
│       └── server.py          # FastAPI v5.2.0 (CORS, async locks, file validation, ThreadPoolExecutor)
├── kotlin-client/
│   ├── build.gradle.kts       # Compose Desktop build (v5.2.0)
│   ├── settings.gradle.kts
│   ├── gradle.properties
│   └── src/main/kotlin/com/speaknode/client/
│       ├── Main.kt            # Entry point (1200×800 window)
│       ├── api/
│       │   ├── SpeakNodeApi.kt       # Ktor HTTP client (all endpoints as suspend functions)
│       │   └── models/ApiModels.kt   # @Serializable request/response models
│       ├── ui/
│       │   ├── App.kt               # Root Composable (2-pane layout)
│       │   ├── theme/Theme.kt       # Material 3 dark theme
│       │   ├── components/Sidebar.kt # Sidebar (server status, chat list, navigation)
│       │   └── screens/
│       │       ├── MeetingScreen.kt  # Meeting analysis/list screen
│       │       └── AgentScreen.kt    # AI Agent conversation screen
│       └── viewmodel/
│           ├── AppViewModel.kt       # Global state management (StateFlow)
│           └── AgentViewModel.kt     # Agent conversation state (StateFlow)
├── database/
│   └── chats/                 # Per-chat KuzuDB files
├── lib/
│   ├── bindings/utils.js      # PyVis network neighbor highlight utility
│   ├── tom-select/            # Tom Select dropdown library (JS + CSS)
│   └── vis-9.1.2/             # vis-network 9.1.2 graph visualization (JS + CSS)
├── shared_cards/              # Shared card PNG output directory
├── scripts/
│   └── api_smoke_test.py      # API smoke test (stdlib only, no external dependencies)
├── docs/
│   └── api_examples.http      # HTTP request collection (11 examples)
└── requirements.txt
```

## 8. Design Characteristics

### Pipeline (`SpeakNodeEngine`)

- **Lazy loading**: Whisper/Extractor loaded on first invocation only
- **Thread safety**: Independent `threading.Lock` per component
- **Embedding-first**: Embeddings completed before DB open → prevents orphan Meeting nodes on failure

### DB Manager (`KuzuManager`)

- **Context Manager**: Automatic resource release via `with` statement
- **Manual transactions**: `BEGIN/COMMIT/ROLLBACK` wrapping (`_transaction()`)
- **Graph dump serialization**: `export_graph_dump()` / `restore_graph_dump()` (schema version 2)
- **Vector search**: Built-in `array_cosine_similarity()` function
- **Legacy compatibility**: Fallback queries for old DBs without HAS_TASK/HAS_DECISION edges

### Hybrid RAG

- **Vector search**: Cosine similarity-based Utterance retrieval
- **Graph search**: Entity type-specific structural traversal
- **Cypher search**: LLM NL→Cypher generation → read-only validation (`FORBIDDEN_CYPHER_TOKENS`) → execution
- **Hybrid fusion**: Keyword-based intent detection → combine relevant search results

### LLM Extractor

- **Conservative extraction**: Returns empty arrays for decisions/tasks when Korean signal patterns (`결정|합의|하기로 했...`, `할 일|담당|까지 완료...`) are absent
- **Context window management**: Transcript truncation at 27K token limit

### Share System (`ShareManager`)

- PNG image metadata embedding: analysis results + graph dump compressed via zlib + base64
- Format: `speaknode_graph_bundle_v1` (analysis_result + graph_dump + include_embeddings flag)
- Legacy `speaknode_data` field compatibility
