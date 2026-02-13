# SpeakNode

> 로컬 환경에서 회의 음성을 분석하고, 지식 그래프로 저장/검색/공유하는 AI 시스템

## Overview
SpeakNode는 회의 음성 파일을 입력받아 다음 과정을 수행합니다.

1. STT로 발화를 텍스트와 타임스탬프로 변환
2. 임베딩 + LLM 추출로 주제/결정/할 일 구조화
3. Kuzu 그래프 DB에 회의 단위로 적재
4. Hybrid RAG + Agent로 질의응답/이메일 초안 생성
5. 그래프 PNG 공유 시 메타데이터를 통해 DB 복원

모든 데이터는 로컬에 저장됩니다.

## Key Features
| 영역 | 기능 |
|---|---|
| STT | Faster-Whisper 기반 음성 인식 |
| Extraction | Ollama + LangChain 기반 구조화 추출 |
| Graph DB | KuzuDB 노드/관계 + 발화 임베딩 저장 |
| Search | Vector + Graph 결합 Hybrid RAG |
| Cypher Search | 자연어 -> 읽기 전용 Cypher 변환 질의 |
| Agent | 회의 질의, 요약, 이메일 초안 생성 |
| Sharing | PNG 메타데이터(압축)에 그래프 덤프 포함/복원 |
| Editing | Streamlit에서 Topic/Task/Person/Meeting 수정 |
| API | FastAPI 운영형 엔드포인트(Phase 5.1) |

## Quick Start
### 1) Install
```bash
# Python 3.10+
git clone <repo-url> && cd SpeakNode
pip install -r requirements.txt

# Ollama 모델 준비
ollama pull qwen2.5:14b
```

### 2) Run
```bash
# Streamlit
streamlit run interfaces/streamlit_app/app.py

# FastAPI
uvicorn interfaces.api_server.server:app --host 0.0.0.0 --port 8000
```

## API Highlights (Phase 5.1)
| Method | Path | 설명 |
|---|---|---|
| POST | `/analyze` | 오디오 분석 및 DB 적재 |
| POST | `/agent/query` | Agent 질의 |
| GET | `/meetings` | 회의 목록 조회 |
| GET | `/meetings/{meeting_id}` | 회의 상세 요약 조회 |
| GET | `/graph/export` | 그래프 덤프 추출 (`include_embeddings` 옵션) |
| POST | `/graph/import` | 그래프 덤프 복원 |
| PATCH | `/nodes/update` | 노드 속성 업데이트 |
| GET/POST/DELETE | `/chats` | 채팅 DB 관리 |

Task 상태값 표준:
- `pending`
- `in_progress`
- `done`
- `blocked`

## Validation Workflow
### 1) Start API Server
```bash
uvicorn interfaces.api_server.server:app --host 0.0.0.0 --port 8000
```

### 2) Run Smoke Test
```bash
# 분석 없이 기본 엔드포인트 검증
python scripts/api_smoke_test.py --base-url http://127.0.0.1:8000

# 오디오 포함 검증
python scripts/api_smoke_test.py \
  --base-url http://127.0.0.1:8000 \
  --audio ./sample.wav \
  --meeting-title "Phase 5.1 Smoke Meeting"
```

### 3) Manual API Collection
- 파일: `docs/api_examples.http`
- VS Code REST Client 또는 JetBrains HTTP Client에서 실행 가능

## Project Structure
```text
SpeakNode/
├── core/
│   ├── config.py
│   ├── domain.py
│   ├── pipeline.py
│   ├── stt/transcriber.py
│   ├── llm/extractor.py
│   ├── db/kuzu_manager.py
│   ├── shared/share_manager.py
│   └── agent/
│       ├── agent.py
│       ├── hybrid_rag.py
│       └── tools/
├── interfaces/
│   ├── streamlit_app/
│   └── api_server/server.py
├── scripts/api_smoke_test.py
├── docs/api_examples.http
├── requirements.txt
└── project.md
```

## Current Status
- Phase 1~4: 완료
- Phase 5.1 (FastAPI 고도화): 완료
- Phase 5.2 (Kotlin Client): 진행 예정

## License
Private Project
