# 📁 Project Blueprint: SpeachNode (v1.0 Kotlin Edition)
### AI 기반 로컬 회의록 시각화 및 지능형 관리 시스템

## 1. 🏗️ High-Level System Architecture (전체 구조도)
이 시스템은 **"Python Brain + Kotlin Body"** 구조를 가진 **완전 독립형(Standalone) 어플리케이션** 입니다.
핵심 AI 연산은 Python이 담당하고, 사용자 인터페이스는 고성능 Native App(Kotlin)으로 구현하여 최고의 속도와 사용성을 제공합니다.

* **Core Layer (The Brain):** STT, LLM, DB 등 모든 AI 핵심 로직이 모여 있는 계층 (Python).
* **Interface Layer A (Prototype):** Streamlit. 개발자가 기능을 빠르게 검증하고 시각화 결과를 확인하는 용도.
* **Interface Layer B (Production):** FastAPI + Kotlin Native App.
    * **Server:** Python(FastAPI)이 로컬 호스트에서 AI 엔진 역할을 수행.
    * **Client:** Kotlin(Compose)으로 제작된 PC 앱이 서버와 통신하며 결과를 보여줌.

## 2. 🛠️ Tech Stack (기술 스택 총정리)
테스트 환경은 개발 속도를, 배포 환경은 **성능(Performance)**을 최우선으로 합니다.

| 구분 (Layer) | 기술 (Technology) | 역할 및 특징 |
| :--- | :--- | :--- |
| **STT (귀)** | Faster-Whisper | OpenAI Whisper보다 4~8배 빠른 C++ 최적화 버전 (GPU 활용) |
| **Orchestration** | LangChain / LangGraph | LLM 호출, 데이터 흐름 제어, 에러 핸들링 |
| **LLM (지능)** | Ollama (Local) | Llama 3, DeepSeek 등 로컬 모델 연동 (API 비용 0원) |
| **Database (뇌)** | KuzuDB (Embedded) | 설치가 필요 없는 파일 기반 그래프 DB (Graph + Vector 지원) |
| **Backend API** | FastAPI | Kotlin 앱과 Python 로직을 연결하는 고속 API 서버 |
| **Frontend (Test)** | Streamlit | (개발자용) Python만으로 빠르게 기능 검증 및 대시보드 구현 |
| **Frontend (Prod)** | Kotlin (Compose) | (배포용) 네이티브 PC 앱. 가볍고 빠르며 안드로이드와 UI 공유 가능 |
| **Visualization** | Compose Canvas | (배포용) Kotlin 자체 그래픽 라이브러리로 그래프 시각화 구현 |
| **Packaging** | PyInstaller / MSI | Python 서버와 Kotlin 앱을 하나의 설치 파일로 배포 |

## 3. 🔄 Data Processing Pipeline (데이터 파이프라인)
오디오가 그래프 데이터로 변환되어 내 컴퓨터 폴더(./database)에 저장되는 과정입니다.

| 단계 | 프로세스 | 기술 스택 | 세부 동작 |
| :--- | :--- | :--- | :--- |
| **Step 1** | Transcribe (받아쓰기) | Faster-Whisper | - GPU 가속을 통한 고속 변환<br>- Diarization(화자 분리) 및 타임스탬프(00:05:30) 추출 |
| **Step 2** | **Understanding (이해)** | Sentence-Transformers | - 문장의 의미를 분석하여 384차원 Vector 생성<br>- 의미 기반 검색(RAG)을 위한 임베딩 데이터 확보 |
| **Step 3** | Extraction (구조화) | LangChain + Ollama | - 텍스트에서 Entity(인물, 주제, 할일)와 Relation(제안, 할당) 추출<br>- JSON 포맷으로 구조화 |
| **Step 4** | Schema Mapping | Python Logic | - 추출된 데이터를 KuzuDB 테이블 스키마에 맞게 변환 및 검증 |
| **Step 5** | Ingest (적재) | Kuzu Python API | - 로컬 폴더 내 .kuzu 파일로 데이터 적재 (Node/Edge 생성) |

## 4. 🗄️ Database Schema (KuzuDB 모델링)
KuzuDB는 사전 스키마 정의가 필요하므로, 회의 분석에 최적화된 구조를 설계합니다.

### A. Node Tables (노드)
```sql
Create NODE TABLE Person(name STRING, role STRING, PRIMARY KEY(name))
Create NODE TABLE Topic(title STRING, summary STRING, PRIMARY KEY(title))
Create NODE TABLE Task(description STRING, deadline STRING, status STRING, PRIMARY KEY(description))
Create NODE TABLE Decision(description STRING, PRIMARY KEY(description))
Create NODE TABLE Utterance(id STRING, text STRING, startTime FLOAT, endTime FLOAT, embedding FLOAT[384], PRIMARY KEY(id))
Create NODE TABLE Meeting(id STRING, title STRING, date STRING, source_file STRING, PRIMARY KEY(id))
```

### B. Relationship Tables (엣지)
```sql
Create REL TABLE PROPOSED(FROM Person TO Topic)
Create REL TABLE ASSIGNED_TO(FROM Person TO Task)
Create REL TABLE RESULTED_IN(FROM Topic TO Decision)
Create REL TABLE SPOKE(FROM Person TO Utterance)
Create REL TABLE NEXT(FROM Utterance TO Utterance)
Create REL TABLE DISCUSSED(FROM Meeting TO Topic)
Create REL TABLE CONTAINS(FROM Meeting TO Utterance)
```

5. 📂 Directory Structure (폴더 구조 - 이원화)
Python(서버)과 Kotlin(클라이언트) 프로젝트가 공존하는 구조입니다.

SpeakNode/
├── assets/                      # 공용 아이콘, 로고 이미지
├── core/                        # [The Brain - 핵심 로직 (Python)]
│   ├── __init__.py
│   ├── pipeline.py              # 전체 실행 파이프라인 (개별 단계 노출)
│   ├── config.py                # 중앙 설정 (모델명, 차원, 경로 등)
│   ├── agent.py                 # [Phase 4] LangGraph 지능형 에이전트
│   ├── transcriber.py           # Faster-Whisper 설정 및 실행
│   ├── extractor.py             # LLM 정보 추출 프롬프트
│   ├── kuzu_manager.py          # KuzuDB CRUD 로직
│   ├── share_manager.py         # PNG 스테가노그래피 기반 데이터 공유
│   └── check_db.py              # DB 디버그/검증 유틸리티
├── database/                    # [The Memory - 데이터 저장소]
│   └── speach.kuzu/             # 실제 DB 파일 저장 경로
├── interfaces/                  # [The Face - 인터페이스 계층]
│   ├── streamlit_app/           # [Track A: 테스트용 (Python)]
│   │   ├── app.py               # Streamlit 실행 파일
│   │   └── view_components.py   # 화면 구성요소
│   └── api_server/              # [Track B: 배포용 서버 (FastAPI)]
│       └── server.py            # Kotlin 앱이 접속할 API 주소 제공
├── kotlin_client/               # [Track B: 배포용 앱 (Kotlin Project)]
│   ├── src/                     # (친구들이 작업할 공간) 안드로이드/PC 앱 소스
│   └── build.gradle.kts         # Kotlin 빌드 설정
├── run_test.bat                 # [실행] Streamlit 테스트 모드
├── run_server.bat               # [실행] 배포용 API 서버 구동
├── requirements.txt             # Python 라이브러리 목록
└── .env                         # 환경 설정

6. 🚀 Detailed Roadmap (개발 로드맵)
Phase 1: Foundation (기초 공사) - [Completed]
[x] Step 1-1: 이원화된 폴더 구조 생성 (core, interfaces 분리).

[x] Step 1-2: kuzu_manager.py 작성 (KuzuDB 스키마 정의 및 테이블 생성).

[x] Step 1-3: 더미 데이터로 DB 입출력 테스트.

Phase 2: The Core Logic (뇌 만들기) - [Completed]
[x] Step 2-1: transcriber.py (Faster-Whisper) 구현 및 GPU 연동 테스트.

[x] Step 2-2: extractor.py (Local LLM) 프롬프트 엔지니어링 및 JSON 추출 테스트.

[x] Step 2-3: pipeline.py로 위 기능들을 하나로 연결.

Phase 3: Track A - Prototyping (검증 및 시각화) - [Completed]
[x] Step 3-1: Streamlit 으로 파일 업로드 및 처리 상태바 구현.

[x] Step 3-2: KuzuDB 데이터를 읽어 PyVis로 네트워크 그래프 시각화.

Phase 3.5: Missing Link (기억/벡터 보강) - [Completed]
[x] DB 스키마 확장 (Utterance Embedding, NEXT Edge 추가).

[x] Pipeline 임베딩 모델(sentence-transformers) 추가 및 연동.

Phase 4: Intelligent Agent (지능화) - [Current Focus]
[ ] Step 4-1: LangGraph 도입 및 agent.py 작성.

[ ] Step 4-2: Pipeline과 Agent 연결 (Swarm Architecture).

[ ] Step 4-3: 복합 질문 처리를 위한 Hybrid RAG (Vector RAG + Graph RAG) 로직 구현.

Phase 5: Track B - Production (배포화) - [Next]
[ ] Step 5-1: FastAPI 서버 구축.

[ ] Step 5-2: Kotlin Native Client 개발.