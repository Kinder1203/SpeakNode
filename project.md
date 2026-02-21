# SpeakNode Project Blueprint (v3.0)

Local-first AI meeting knowledge extraction system with a single-user Streamlit desktop interface.

## 1. Architecture

### Core Principle

- **Local-First, Single-User**: All models and data run on-device. No cloud services, no network layer.
- **Direct Import**: Streamlit UI imports `core/` Python modules directly — no HTTP intermediary.
- **1 Meeting = 1 KuzuDB**: Each audio analysis creates an independent graph database directory, eliminating cross-meeting key collision complexity.

### Layers

1. **Core Layer** (Python) — STT, Embedding, Extraction, Graph DB, Agent
2. **Interface Layer** — Streamlit desktop app (`streamlit_app/`)

```
[streamlit_app/]  ──direct Python import──▶  [core/]  ──stores to──▶  [database/meetings/{id}/]
```

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
| UI | Streamlit + PyVis | 1.54.0 / 0.3.2 | Desktop app + graph visualization |
| GPU | PyTorch | 2.8.0 | CUDA acceleration for STT |

## 3. Data Flow

1. **Transcribe** — Convert audio to utterance segments (optional speaker diarization)
2. **Embed** — Generate utterance embeddings (all-MiniLM-L6-v2, 384d)
3. **Extract** — Structure topics, decisions, tasks, people, entities, and relations (conservative Korean signal-based extraction + comprehensive entity extraction)
4. **Ingest** — Store as a per-meeting graph (`database/meetings/{meeting_id}/`). Plain-text PKs within each isolated DB.
5. **Query** — Hybrid RAG + Agent response (vector + graph + Cypher)
6. **Cypher Query** — Natural language to read-only Cypher translation (forbidden token validation)
7. **Share** — Graph dump sharing/restoration via compressed PNG metadata (`speaknode_graph_bundle_v1`)

## 4. Graph Schema (KuzuDB)

### Nodes (7 tables)

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
CREATE NODE TABLE Entity(name STRING, entity_type STRING, description STRING, PRIMARY KEY(name));
```

> `Entity.entity_type` values: `person`, `technology`, `organization`, `concept`, `event`

### Relationships (12 tables)

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
CREATE REL TABLE RELATED_TO(FROM Entity TO Entity, relation_type STRING);
CREATE REL TABLE MENTIONS(FROM Topic TO Entity);
CREATE REL TABLE HAS_ENTITY(FROM Meeting TO Entity);
```

### DB Strategy (Document-based)

Each meeting gets its own isolated KuzuDB directory. PKs are **plain text** — no `meeting_id::value` scoping required.

```
database/meetings/
├── m_20260221_143000_123456/     ← 1 directory per meeting
│   ├── metadata.json             ← {meeting_id, title, date, source_file}
│   └── <kuzu internal files>
└── m_20260220_091500_654321/
```

`metadata.json` is written by the pipeline after successful ingest, allowing the UI to list meetings with friendly labels without opening each DB.

## 5. Agent Architecture

### Tools (7)

| Tool | Description | Source |
|---|---|---|
| `search_by_meaning` | Vector-based semantic search (Utterance similarity) | search_tools.py |
| `search_by_structure` | Structural graph traversal (topic/task/decision/person/meeting/entity) | search_tools.py |
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

## 6. Directory Structure

```text
SpeakNode/
├── core/
│   ├── config.py              # Central config + meeting DB path helpers (sanitize_meeting_id, get_meeting_db_path, list_meeting_ids)
│   ├── domain.py              # Pydantic domain models (Utterance, Person, Topic, Task, Decision, Entity, Relation, Meeting, AnalysisResult)
│   ├── utils.py               # Task status normalization, LLM token estimation
│   ├── embedding.py           # SentenceTransformer singleton cache (thread-safe double-check)
│   ├── pipeline.py            # SpeakNodeEngine: STT → Embed → LLM → DB pipeline (lazy loading, thread-safe locks, metadata.json output)
│   ├── stt/transcriber.py     # Faster-Whisper STT + optional pyannote diarization
│   ├── llm/extractor.py       # Ollama structured extraction (conservative Korean signal + entity extraction)
│   ├── db/kuzu_manager.py     # KuzuDB manager (schema v3, plain-text PKs, vector search, export/import)
│   ├── shared/share_manager.py # PNG metadata sharing (zlib + base64, speaknode_graph_bundle_v1)
│   └── agent/
│       ├── agent.py           # LangGraph agent (Router → Tool → Synthesizer)
│       ├── hybrid_rag.py      # Hybrid RAG (vector + graph + Cypher + Entity)
│       └── tools/             # ToolRegistry + 7 registered tools
├── streamlit_app/
│   ├── app.py             # Streamlit app (meeting selection, analysis, agent, save)
│   └── view_components.py # Graph viewer, node editor, PNG export/import
├── database/
│   └── meetings/              # Per-meeting KuzuDB directories (auto-created on first analysis)
├── docs/
├── requirements.txt
└── README.md
```

## 7. Design Characteristics

### Pipeline (`SpeakNodeEngine`)

- **Lazy loading**: Whisper/Extractor loaded on first invocation only
- **Thread safety**: Independent `threading.Lock` per component (transcriber, embedder, extractor) — retained for Streamlit's internal threading
- **Embedding-first**: Embeddings completed before DB open → prevents orphan Meeting nodes on failure
- **meeting_id handoff**: Accepts an optional pre-generated `meeting_id` from the caller; auto-generates if absent
- **metadata.json**: Written after successful DB ingest to enable fast UI listing without reopening KuzuDB

### DB Manager (`KuzuManager`)

- **Context Manager**: Automatic resource release via `with` statement
- **Manual transactions**: `BEGIN/COMMIT/ROLLBACK` wrapping
- **Plain-text PKs**: No scoped key encoding/decoding — Topic/Task/Decision/Entity use plain text as PK within each per-meeting DB
- **Vector search**: `array_cosine_similarity()` built-in
- **Export/Restore**: `export_graph_dump()` / `restore_graph_dump()` (schema version 3)
- **Legacy fallback**: Graceful handling of old DBs without HAS_TASK/HAS_DECISION/Entity edges

### Hybrid RAG

- **Vector search**: Cosine similarity-based Utterance retrieval
- **Graph search**: Entity type-specific structural traversal
- **Cypher search**: LLM NL→Cypher → read-only validation → execution
- **Hybrid fusion**: Keyword intent detection → combine relevant results

### Share System (`ShareManager`)

- PNG metadata embedding: analysis + graph dump via zlib + base64
- Format: `speaknode_graph_bundle_v1` (analysis_result + graph_dump + include_embeddings)
- Legacy `speaknode_data` field compatibility maintained
