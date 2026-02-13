# 🎙️ SpeakNode

> **AI 기반 로컬 회의록 분석 · 지식 그래프 시각화 · 지능형 에이전트 시스템**

회의 녹음 파일을 업로드하면 **로컬 AI**가 자동으로 분석하여 주제, 결정 사항, 할 일을 추출하고, **지식 그래프**로 시각화합니다. AI Agent에게 자연어로 질문하면 회의 데이터를 검색·요약·이메일 초안 작성까지 해줍니다.

> ⚡ **완전 오프라인** — 인터넷·API 키·클라우드 불필요. 모든 데이터가 내 컴퓨터에만 저장됩니다.

---

## 주요 기능

| 기능 | 설명 |
|------|------|
| 🎧 **STT** | Faster-Whisper 기반 고속 음성→텍스트 (GPU 가속) |
| 🧠 **LLM 추출** | Ollama 로컬 모델로 주제/결정/할일 자동 추출 |
| 🕸️ **지식 그래프** | KuzuDB 그래프 DB + PyVis 시각화 |
| 🤖 **AI Agent** | Router→Tool→Synthesizer 파이프라인, 6개 도구 |
| 🔍 **Hybrid RAG** | Vector(의미 검색) + Graph(구조 검색) 결합 |
| 📧 **이메일 초안** | 회의 데이터 기반 비즈니스 이메일 자동 작성 |

---

## 빠른 시작

### 1. 설치
```bash
# Python 3.10+ 필요
git clone <repo-url> && cd SpeakNode
pip install -r requirements.txt

# Ollama (LLM 엔진) 설치 후 모델 다운로드
ollama pull gemma3:4b
ollama pull qwen2.5:14b   # Agent용
```

### 2. 실행
```bash
# Streamlit 테스트 모드
streamlit run interfaces/streamlit_app/app.py

# 또는 FastAPI 서버 모드
uvicorn interfaces.api_server.server:app --host 0.0.0.0 --port 8000
```

### 3. 사용
1. Streamlit UI에서 오디오 파일 업로드
2. 자동 분석 후 Knowledge Graph 탭에서 결과 확인
3. **AI Agent 탭**에서 자연어 질문:
   - _"이번 회의에서 결정된 사항은?"_
   - _"누가 어떤 일을 맡았어?"_
   - _"회의 결과를 이메일로 보내줘"_

---

## 기술 스택

| 역할 | 기술 |
|------|------|
| STT | Faster-Whisper (CTranslate2) |
| LLM | Ollama + LangChain |
| Agent | LangGraph + ToolRegistry |
| DB | KuzuDB (Graph + Vector) |
| 타입 | Pydantic Domain Models |
| API | FastAPI |
| UI (Test) | Streamlit |
| UI (Prod) | Kotlin Compose (예정) |

---

## 프로젝트 구조

```
SpeakNode/
├── core/                   # AI 핵심 로직
│   ├── config.py           # 중앙 설정
│   ├── domain.py           # Pydantic 도메인 모델
│   ├── pipeline.py         # 실행 파이프라인 (Lazy Loading)
│   ├── agent.py            # LangGraph Agent
│   ├── hybrid_rag.py       # Vector + Graph RAG
│   ├── transcriber.py      # STT + 화자 분리
│   ├── extractor.py        # LLM 분석 → AnalysisResult
│   ├── kuzu_manager.py     # KuzuDB CRUD
│   └── tools/              # ToolRegistry 기반 도구
│       ├── search_tools.py
│       ├── meeting_tools.py
│       ├── email_tools.py
│       └── general_tools.py
├── interfaces/
│   ├── streamlit_app/      # Streamlit UI
│   └── api_server/         # FastAPI 서버
├── requirements.txt
└── project.md              # 상세 설계 문서
```

> 📚 상세 설계는 [project.md](project.md)를 참고하세요.

---

## 라이선스

Private Project
