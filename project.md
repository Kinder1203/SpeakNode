# 📁 Project Blueprint: SpeakNode (v2.0 Kotlin Edition)
### AI 기반 로컬 회의록 시각화 및 지능형 관리 시스템

## 1. 🏗️ High-Level System Architecture (전체 구조도)
**"Python Brain + Kotlin Body"** 구조의 **완전 독립형(Standalone) 어플리케이션**.

* **Core Layer (The Brain):** STT, LLM, DB, Agent 등 모든 AI 핵심 로직 (Python).
* **Interface Layer A (Prototype):** Streamlit — 빠른 검증 및 시각화.
* **Interface Layer B (Production):** FastAPI + Kotlin Native App.
    * **Server:** Python(FastAPI)이 로컬에서 AI 엔진 역할 수행.
    * **Client:** Kotlin(Compose) PC 앱이 서버와 통신하며 UI 제공.

## 2. 🛠️ Tech Stack (기술 스택)

| 구분 | 기술 | 역할 |
| :--- | :--- | :--- |
| **STT (귀)** | Faster-Whisper | GPU 가속 고속 변환 (C++ 최적화) |
| **Orchestration** | LangChain / LangGraph | LLM 흐름 제어, Agent 워크플로 |
| **LLM (지능)** | Ollama (Local) | Llama 3, DeepSeek 등 로컬 모델 (API 비용 0원) |
| **Database (뇌)** | KuzuDB (Embedded) | 파일 기반 그래프 DB (Graph + Vector) |
| **Backend API** | FastAPI | Python ↔ Kotlin 연결 고속 API |
| **Frontend (Test)** | Streamlit | 빠른 프로토타이핑 대시보드 |
| **Frontend (Prod)** | Kotlin (Compose) | 네이티브 PC 앱 |
| **Type Safety** | Pydantic | 도메인 모델 타입 강제 |
| **Packaging** | PyInstaller / MSI | 원클릭 설치 파일 |

## 3. 🔄 Data Processing Pipeline

| 단계 | 프로세스 | 기술 | 세부 동작 |
| :--- | :--- | :--- | :--- |
| **Step 1** | Transcribe | Faster-Whisper | GPU 가속 + 화자 분리(Optional) + 타임스탬프 |
| **Step 2** | Understanding | Sentence-Transformers | 384차원 벡터 생성 (Lazy + Batch 인코딩) |
| **Step 3** | Extraction | LangChain + Ollama | Entity/Relation JSON 추출 → Pydantic 모델 |
| **Step 4** | Schema Mapping | Python Logic | AnalysisResult → KuzuDB 스키마 변환 |
| **Step 5** | Ingest | Kuzu Python API | .kuzu 파일 적재 (Node/Edge 생성) |

## 4. 🗄️ Database Schema (KuzuDB)

### A. Node Tables
```sql
CREATE NODE TABLE Person(name STRING, role STRING, PRIMARY KEY(name))
CREATE NODE TABLE Topic(title STRING, summary STRING, PRIMARY KEY(title))
CREATE NODE TABLE Task(description STRING, deadline STRING, status STRING, PRIMARY KEY(description))
CREATE NODE TABLE Decision(description STRING, PRIMARY KEY(description))
CREATE NODE TABLE Utterance(id STRING, text STRING, startTime FLOAT, endTime FLOAT, embedding FLOAT[384], PRIMARY KEY(id))
CREATE NODE TABLE Meeting(id STRING, title STRING, date STRING, source_file STRING, PRIMARY KEY(id))
```

### B. Relationship Tables
```sql
CREATE REL TABLE PROPOSED(FROM Person TO Topic)
CREATE REL TABLE ASSIGNED_TO(FROM Person TO Task)
CREATE REL TABLE RESULTED_IN(FROM Topic TO Decision)
CREATE REL TABLE SPOKE(FROM Person TO Utterance)
CREATE REL TABLE NEXT(FROM Utterance TO Utterance)
CREATE REL TABLE DISCUSSED(FROM Meeting TO Topic)
CREATE REL TABLE CONTAINS(FROM Meeting TO Utterance)
```

## 5. 📂 Directory Structure

```
SpeakNode/
├── assets/                          # 공용 아이콘, 로고 이미지
├── core/                            # [The Brain — 핵심 로직 (Python)]
│   ├── __init__.py
│   ├── config.py                    # 중앙 설정 (모델명, 차원, 경로 등)
│   ├── domain.py                    # ★ Pydantic 도메인 모델 정의
│   ├── pipeline.py                  # 실행 파이프라인 (Lazy Loading)
│   ├── agent.py                     # LangGraph 지능형 에이전트
│   ├── hybrid_rag.py                # Vector + Graph RAG 결합 검색
│   ├── transcriber.py               # Faster-Whisper STT + 화자 분리
│   ├── extractor.py                 # LLM 정보 추출 → AnalysisResult
│   ├── kuzu_manager.py              # KuzuDB CRUD
│   ├── share_manager.py             # PNG 스테가노그래피 데이터 공유
│   ├── check_db.py                  # DB 디버그 유틸리티
│   └── tools/                       # ★ ToolRegistry 기반 도구 패키지
│       ├── __init__.py              # ToolRegistry + @register 데코레이터
│       ├── search_tools.py          # Vector/Graph/Hybrid 검색
│       ├── meeting_tools.py         # 회의 요약
│       ├── email_tools.py           # 이메일 초안 생성
│       └── general_tools.py         # 직접 답변
├── database/                        # [The Memory — 데이터 저장소]
│   └── speach.kuzu/
├── interfaces/                      # [The Face — 인터페이스]
│   ├── streamlit_app/               # Track A: 테스트용
│   │   ├── app.py                   # Streamlit 메인 (Agent 탭 포함)
│   │   └── view_components.py       # UI 컴포넌트
│   └── api_server/                  # Track B: 배포용 서버
│       └── server.py                # FastAPI (Agent API 포함)
├── kotlin_client/                   # Track B: Kotlin 앱
│   ├── src/
│   └── build.gradle.kts
├── run_test.bat                     # Streamlit 실행
├── run_server.bat                   # FastAPI 서버 실행
├── requirements.txt                 # Python 의존성
├── .gitignore
├── README.md                        # 프로젝트 소개
└── project.md                       # 설계 문서 (이 파일)
```

## 6. 🚀 Roadmap

### Phase 1: Foundation — ✅ Complete
- [x] 폴더 구조 생성, KuzuDB 스키마, 더미 데이터 테스트

### Phase 2: The Core Logic — ✅ Complete
- [x] STT (Faster-Whisper), LLM 추출 (Ollama), Pipeline 통합

### Phase 3: Track A — Prototype — ✅ Complete
- [x] Streamlit 파일 업로드, PyVis 그래프 시각화

### Phase 3.5: Memory/Vector — ✅ Complete
- [x] Utterance Embedding, NEXT Edge, 벡터 검색 추가

### Phase 4: Intelligent Agent — ✅ Complete
- [x] Step 4-1: LangGraph Agent (`agent.py`) + ToolRegistry 패턴
- [x] Step 4-2: Pipeline ↔ Agent 연결, Lazy Loading
- [x] Step 4-3: Hybrid RAG (Vector + Graph), Pydantic Domain Models
- [x] Step 4-4: Streamlit Agent 탭 + FastAPI Agent API

### Phase 5: Track B — Production — 📌 Next
- [ ] Step 5-1: FastAPI 서버 고도화
- [ ] Step 5-2: Kotlin Native Client 개발