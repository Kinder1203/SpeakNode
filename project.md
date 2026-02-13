# SpeakNode Project Blueprint (v2.1)
로컬 회의 데이터 지식화 및 에이전트 기반 활용 시스템

## 1. Architecture
### Core Principle
- Python Brain + Kotlin Body
- 오프라인 우선(local-first), 파일 기반 그래프 메모리

### Layers
1. Core Layer (Python)
   STT, Embedding, Extraction, Graph DB, Agent
2. Interface Layer A
   Streamlit 기반 검증/운영 대시보드
3. Interface Layer B
   FastAPI 서버 + Kotlin 클라이언트

## 2. Technical Stack
| Domain | Stack | Role |
|---|---|---|
| STT | Faster-Whisper | 음성 → 텍스트 |
| Embedding | Sentence-Transformers | 발화 벡터화 |
| LLM | Ollama + LangChain | 정보 추출/응답 생성 |
| Agent | LangGraph | Router-Tool-Synthesizer 흐름 |
| DB | KuzuDB | Graph + Vector 저장 |
| API | FastAPI | Python 서비스 계층 |
| UI | Streamlit / Kotlin Compose | 운영 UI |

## 3. Data Flow
1. Transcribe: 오디오를 발화 세그먼트로 변환
2. Embed: 발화 임베딩 생성
3. Extract: 주제/결정/할 일/인물 구조화
4. Ingest: Meeting 단위 그래프 적재
5. Query: Hybrid RAG + Agent 응답
6. Cypher Query: 자연어를 읽기 전용 Cypher로 변환해 구조 질의
7. Share: PNG 메타데이터(압축)를 통한 그래프 덤프 공유/복원

## 4. Graph Schema (KuzuDB)
### Node
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

### Relationship
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
| POST | `/analyze` | 파일 분석 및 그래프 적재 |
| POST | `/agent/query` | Agent 질의 |
| GET | `/chats` | 채팅 목록 |
| POST | `/chats` | 채팅 생성 |
| DELETE | `/chats/{chat_id}` | 채팅 DB 초기화 |
| GET | `/meetings` | 회의 목록 조회 |
| GET | `/meetings/{meeting_id}` | 회의 상세 |
| GET | `/graph/export` | 그래프 덤프 추출 (`include_embeddings` 옵션) |
| POST | `/graph/import` | 그래프 덤프 복원 |
| PATCH | `/nodes/update` | 노드 속성 업데이트 |

## 6. Directory Structure
```text
SpeakNode/
├── core/
│   ├── config.py
│   ├── domain.py
│   ├── pipeline.py
│   ├── stt/transcriber.py
│   ├── llm/extractor.py
│   ├── db/
│   │   ├── kuzu_manager.py
│   │   └── check_db.py
│   ├── shared/share_manager.py
│   └── agent/
│       ├── agent.py
│       ├── hybrid_rag.py
│       └── tools/
├── interfaces/
│   ├── streamlit_app/
│   │   ├── app.py
│   │   └── view_components.py
│   └── api_server/server.py
├── scripts/api_smoke_test.py
├── docs/api_examples.http
└── requirements.txt
```

## 7. Phase 5.1 Completion Criteria
- 파일 업로드 검증(확장자/크기) 적용
- 채팅 단위 동기화 락 적용
- 회의/그래프 조회 및 복원 API 제공
- 노드 속성 업데이트 API 제공
- 스모크 테스트 스크립트 제공
- HTTP 요청 컬렉션 제공
- 그래프 import 보호(크기/요소 제한) 적용
- 회의 스코프 키 기반 엔티티 충돌 방지 적용

## 8. Roadmap Status
- Phase 1 Foundation: Complete
- Phase 2 Core Logic: Complete
- Phase 3 Prototype UI: Complete
- Phase 3.5 Vector Memory: Complete
- Phase 4 Intelligent Agent: Complete
- Phase 5.1 FastAPI Hardening: Complete
- Phase 5.2 Kotlin Client: Planned
