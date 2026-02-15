"""
generate_demo_pngs.py
=====================
index.html 데모 카드에 쓸 PNG 3장을 docs/demos/ 에 생성한다.
각 PNG는 ShareManager 형식(speaknode_data_zlib_b64 tEXt 청크)으로
analysis_result + graph_dump JSON을 임베딩하므로,
index.html Upload PNG 드롭존이나 SpeakNode 앱에서도 바로 읽을 수 있다.

Usage:
    python scripts/generate_demo_pngs.py
"""

import os
import sys

# ── project root를 sys.path에 추가 ──
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from core.shared.share_manager import ShareManager  # noqa: E402

OUTPUT_DIR = os.path.join(PROJECT_ROOT, "docs", "demos")

# ══════════════════════════════════════════════════════════════
# Demo Bundles (index.html DEMO_BUNDLES 와 동일)
# ══════════════════════════════════════════════════════════════

DEMO_BUNDLES = [
    # ── 0: 주간 기획 회의 ──
    {
        "meta": {"title": "주간 기획 회의", "icon": "📅", "desc": "API 마이그레이션, RAG 최적화, UI 개선 논의 · 4명 참석"},
        "analysis_result": {
            "topics": [
                {"title": "API 서버 마이그레이션", "summary": "FastAPI v5.2.0 업그레이드를 이번 주 내로 완료하기로 논의. Ktor 클라이언트도 동시 업데이트 필요.", "proposer": "김태호"},
                {"title": "RAG 파이프라인 최적화", "summary": "Hybrid RAG의 정확도 개선을 위해 Cypher 쿼리를 추가하고, 벡터 인덱스 벤치마크를 진행하기로 함.", "proposer": "이서연"},
                {"title": "모바일 UI 개선", "summary": "Material 3 다크 테마를 전면 채택하고, 프로토타입을 2/15까지 완성하기로 함.", "proposer": "박준혁"},
                {"title": "그래프 스키마 확장", "summary": "감정 분석 노드 추가 가능성 논의. Entity 타입 확장 검토.", "proposer": "최유진"},
            ],
            "decisions": [
                {"description": "API v5.2.0 즉시 마이그레이션 진행", "related_topic": "API 서버 마이그레이션"},
                {"description": "Material 3 다크 테마 채택", "related_topic": "모바일 UI 개선"},
            ],
            "tasks": [
                {"description": "Ktor 클라이언트 업데이트", "assignee": "이서연", "deadline": "2025-02-20", "status": "in_progress"},
                {"description": "벡터 인덱스 벤치마크", "assignee": "최유진", "deadline": "2025-02-18", "status": "pending"},
                {"description": "UI 프로토타입 제작", "assignee": "박준혁", "deadline": "2025-02-15", "status": "done"},
                {"description": "Cypher 쿼리 최적화", "assignee": "이서연", "deadline": "2025-02-22", "status": "pending"},
            ],
            "people": [
                {"name": "김태호", "role": "PM"},
                {"name": "이서연", "role": "Developer"},
                {"name": "박준혁", "role": "Designer"},
                {"name": "최유진", "role": "Data Engineer"},
            ],
            "entities": [
                {"name": "FastAPI", "entity_type": "technology", "description": "Python 비동기 웹 프레임워크"},
                {"name": "KuzuDB", "entity_type": "technology", "description": "임베디드 그래프 데이터베이스"},
                {"name": "LangChain", "entity_type": "technology", "description": "LLM 오케스트레이션 프레임워크"},
                {"name": "Hybrid RAG", "entity_type": "concept", "description": "벡터 + 그래프 + Cypher 결합 검색"},
                {"name": "Material 3", "entity_type": "technology", "description": "Google 디자인 시스템"},
            ],
            "relations": [
                {"source": "FastAPI", "target": "KuzuDB", "relation_type": "통합"},
                {"source": "LangChain", "target": "Hybrid RAG", "relation_type": "구현 프레임워크"},
            ],
        },
        "graph_dump": {
            "schema_version": 3,
            "nodes": {
                "meetings": [
                    {"id": "m_w01", "title": "주간 기획 회의", "date": "2025-02-10", "source_file": "weekly.wav"},
                    {"id": "m_w02", "title": "디자인 리뷰", "date": "2025-02-12", "source_file": "design.mp3"},
                ],
                "people": [
                    {"name": "김태호", "role": "PM"},
                    {"name": "이서연", "role": "Developer"},
                    {"name": "박준혁", "role": "Designer"},
                    {"name": "최유진", "role": "Data Engineer"},
                ],
                "topics": [
                    {"title": "m_w01::API 서버 마이그레이션", "summary": "FastAPI v5.2.0 업그레이드 논의"},
                    {"title": "m_w01::RAG 파이프라인 최적화", "summary": "Hybrid RAG 정확도 개선"},
                    {"title": "m_w02::모바일 UI 개선", "summary": "Material 3 다크 테마 적용"},
                    {"title": "m_w01::그래프 스키마 확장", "summary": "감정 분석 노드 추가 논의"},
                ],
                "tasks": [
                    {"description": "m_w01::Ktor 클라이언트 업데이트", "deadline": "2025-02-20", "status": "in_progress"},
                    {"description": "m_w01::벡터 인덱스 벤치마크", "deadline": "2025-02-18", "status": "pending"},
                    {"description": "m_w02::UI 프로토타입 제작", "deadline": "2025-02-15", "status": "done"},
                    {"description": "m_w01::Cypher 쿼리 최적화", "deadline": "2025-02-22", "status": "pending"},
                ],
                "decisions": [
                    {"description": "m_w01::API v5.2.0 즉시 마이그레이션"},
                    {"description": "m_w02::Material 3 다크 테마 채택"},
                ],
                "utterances": [
                    {"id": "u_w01_000000_0000012500", "text": "서버 마이그레이션은 이번 주에 시작합시다", "start": 12.5, "end": 16.2},
                    {"id": "u_w01_000001_0000045100", "text": "벡터 검색 성능이 30% 향상되었습니다", "start": 45.1, "end": 50.3},
                    {"id": "u_w02_000002_0000068000", "text": "UI는 Material 3으로 통일하죠", "start": 68.0, "end": 72.5},
                    {"id": "u_w01_000003_0000091200", "text": "RAG에 Cypher 쿼리를 추가했습니다", "start": 91.2, "end": 97.8},
                ],
                "entities": [
                    {"name": "m_w01::FastAPI", "entity_type": "technology", "description": "Python 비동기 웹 프레임워크"},
                    {"name": "m_w01::KuzuDB", "entity_type": "technology", "description": "임베디드 그래프 데이터베이스"},
                    {"name": "m_w01::LangChain", "entity_type": "technology", "description": "LLM 오케스트레이션 프레임워크"},
                    {"name": "m_w01::Hybrid RAG", "entity_type": "concept", "description": "벡터 + 그래프 + Cypher 결합 검색"},
                    {"name": "m_w02::Material 3", "entity_type": "technology", "description": "Google 디자인 시스템"},
                ],
            },
            "edges": {
                "discussed": [
                    {"meeting_id": "m_w01", "topic": "m_w01::API 서버 마이그레이션"},
                    {"meeting_id": "m_w01", "topic": "m_w01::RAG 파이프라인 최적화"},
                    {"meeting_id": "m_w02", "topic": "m_w02::모바일 UI 개선"},
                    {"meeting_id": "m_w01", "topic": "m_w01::그래프 스키마 확장"},
                ],
                "proposed": [
                    {"person": "김태호", "topic": "m_w01::API 서버 마이그레이션"},
                    {"person": "이서연", "topic": "m_w01::RAG 파이프라인 최적화"},
                    {"person": "박준혁", "topic": "m_w02::모바일 UI 개선"},
                    {"person": "최유진", "topic": "m_w01::그래프 스키마 확장"},
                ],
                "assigned_to": [
                    {"person": "이서연", "task": "m_w01::Ktor 클라이언트 업데이트"},
                    {"person": "최유진", "task": "m_w01::벡터 인덱스 벤치마크"},
                    {"person": "박준혁", "task": "m_w02::UI 프로토타입 제작"},
                    {"person": "이서연", "task": "m_w01::Cypher 쿼리 최적화"},
                ],
                "resulted_in": [
                    {"topic": "m_w01::API 서버 마이그레이션", "decision": "m_w01::API v5.2.0 즉시 마이그레이션"},
                    {"topic": "m_w02::모바일 UI 개선", "decision": "m_w02::Material 3 다크 테마 채택"},
                ],
                "spoke": [
                    {"person": "김태호", "utterance_id": "u_w01_000000_0000012500"},
                    {"person": "최유진", "utterance_id": "u_w01_000001_0000045100"},
                    {"person": "박준혁", "utterance_id": "u_w02_000002_0000068000"},
                    {"person": "이서연", "utterance_id": "u_w01_000003_0000091200"},
                ],
                "next": [
                    {"from_utterance_id": "u_w01_000000_0000012500", "to_utterance_id": "u_w01_000001_0000045100"},
                    {"from_utterance_id": "u_w01_000001_0000045100", "to_utterance_id": "u_w01_000003_0000091200"},
                ],
                "contains": [
                    {"meeting_id": "m_w01", "utterance_id": "u_w01_000000_0000012500"},
                    {"meeting_id": "m_w01", "utterance_id": "u_w01_000001_0000045100"},
                    {"meeting_id": "m_w02", "utterance_id": "u_w02_000002_0000068000"},
                    {"meeting_id": "m_w01", "utterance_id": "u_w01_000003_0000091200"},
                ],
                "has_task": [
                    {"meeting_id": "m_w01", "task": "m_w01::Ktor 클라이언트 업데이트"},
                    {"meeting_id": "m_w01", "task": "m_w01::벡터 인덱스 벤치마크"},
                    {"meeting_id": "m_w02", "task": "m_w02::UI 프로토타입 제작"},
                    {"meeting_id": "m_w01", "task": "m_w01::Cypher 쿼리 최적화"},
                ],
                "has_decision": [
                    {"meeting_id": "m_w01", "decision": "m_w01::API v5.2.0 즉시 마이그레이션"},
                    {"meeting_id": "m_w02", "decision": "m_w02::Material 3 다크 테마 채택"},
                ],
                "related_to": [
                    {"source": "m_w01::FastAPI", "relation_type": "통합", "target": "m_w01::KuzuDB"},
                    {"source": "m_w01::LangChain", "relation_type": "구현 프레임워크", "target": "m_w01::Hybrid RAG"},
                ],
                "mentions": [
                    {"topic": "m_w01::API 서버 마이그레이션", "entity": "m_w01::FastAPI"},
                    {"topic": "m_w01::RAG 파이프라인 최적화", "entity": "m_w01::Hybrid RAG"},
                    {"topic": "m_w01::RAG 파이프라인 최적화", "entity": "m_w01::LangChain"},
                    {"topic": "m_w02::모바일 UI 개선", "entity": "m_w02::Material 3"},
                    {"topic": "m_w01::그래프 스키마 확장", "entity": "m_w01::KuzuDB"},
                ],
                "has_entity": [
                    {"meeting_id": "m_w01", "entity": "m_w01::FastAPI"},
                    {"meeting_id": "m_w01", "entity": "m_w01::KuzuDB"},
                    {"meeting_id": "m_w01", "entity": "m_w01::LangChain"},
                    {"meeting_id": "m_w01", "entity": "m_w01::Hybrid RAG"},
                    {"meeting_id": "m_w02", "entity": "m_w02::Material 3"},
                ],
            },
        },
    },
    # ── 1: AI 기술 세미나 ──
    {
        "meta": {"title": "AI 기술 세미나", "icon": "🎓", "desc": "트랜스포머, LLM 학습, 멀티모달 AI 강의 · Entity 풍부"},
        "analysis_result": {
            "topics": [
                {"title": "트랜스포머 아키텍처의 진화", "summary": "2017년 Attention Is All You Need 논문 이후 트랜스포머가 NLP를 넘어 비전, 음성, 멀티모달 분야로 확장된 과정을 설명. Self-Attention 메커니즘이 핵심.", "proposer": "정민수"},
                {"title": "대규모 LLM 학습 전략", "summary": "GPT-4, LLaMA, Qwen 등 최신 모델들의 학습 기법: RLHF, DPO, MoE 아키텍처 비교. 학습 데이터 규모와 품질의 트레이드오프 분석.", "proposer": "정민수"},
                {"title": "멀티모달 AI의 현재와 미래", "summary": "GPT-4V, Gemini 등 텍스트+이미지+음성 통합 모델의 발전. 의료, 교육, 로보틱스 적용 사례 소개.", "proposer": "정민수"},
            ],
            "decisions": [],
            "tasks": [{"description": "트랜스포머 논문 리뷰 정리", "assignee": "최한결", "deadline": "2025-03-01", "status": "pending"}],
            "people": [{"name": "정민수", "role": "강연자"}, {"name": "최한결", "role": "참석자"}],
            "entities": [
                {"name": "Transformer", "entity_type": "concept", "description": "Self-Attention 기반 신경망 아키텍처 (2017)"},
                {"name": "Self-Attention", "entity_type": "concept", "description": "시퀀스 내 모든 위치 간 관계를 계산하는 메커니즘"},
                {"name": "GPT-4", "entity_type": "technology", "description": "OpenAI의 대규모 멀티모달 언어 모델"},
                {"name": "LLaMA", "entity_type": "technology", "description": "Meta의 오픈소스 LLM 시리즈"},
                {"name": "Gemini", "entity_type": "technology", "description": "Google DeepMind의 멀티모달 AI 모델"},
                {"name": "RLHF", "entity_type": "concept", "description": "인간 피드백 기반 강화학습"},
                {"name": "OpenAI", "entity_type": "organization", "description": "GPT 시리즈 개발 AI 연구소"},
                {"name": "Google DeepMind", "entity_type": "organization", "description": "Gemini, AlphaFold 개발 연구소"},
                {"name": "MoE", "entity_type": "concept", "description": "Mixture of Experts — 조건부 연산 아키텍처"},
            ],
            "relations": [
                {"source": "Transformer", "target": "Self-Attention", "relation_type": "핵심 구성요소"},
                {"source": "GPT-4", "target": "Transformer", "relation_type": "기반 아키텍처"},
                {"source": "GPT-4", "target": "RLHF", "relation_type": "학습 기법"},
                {"source": "OpenAI", "target": "GPT-4", "relation_type": "개발"},
                {"source": "Google DeepMind", "target": "Gemini", "relation_type": "개발"},
                {"source": "LLaMA", "target": "Transformer", "relation_type": "기반 아키텍처"},
                {"source": "Gemini", "target": "MoE", "relation_type": "사용 아키텍처"},
            ],
        },
        "graph_dump": {
            "schema_version": 3,
            "nodes": {
                "meetings": [{"id": "m_sem01", "title": "AI 기술 세미나", "date": "2025-03-05", "source_file": "seminar.wav"}],
                "people": [{"name": "정민수", "role": "강연자"}, {"name": "최한결", "role": "참석자"}],
                "topics": [
                    {"title": "m_sem01::트랜스포머 아키텍처의 진화", "summary": "2017년 Attention Is All You Need 이후 트랜스포머 확장 과정"},
                    {"title": "m_sem01::대규모 LLM 학습 전략", "summary": "GPT-4, LLaMA, Qwen 학습 기법 비교"},
                    {"title": "m_sem01::멀티모달 AI의 현재와 미래", "summary": "GPT-4V, Gemini 등 통합 모델 발전"},
                ],
                "tasks": [{"description": "m_sem01::트랜스포머 논문 리뷰 정리", "deadline": "2025-03-01", "status": "pending"}],
                "decisions": [],
                "utterances": [
                    {"id": "u_sem01_000000_0000005000", "text": "오늘은 트랜스포머의 진화부터 시작하겠습니다", "start": 5.0, "end": 9.2},
                    {"id": "u_sem01_000001_0000032000", "text": "Self-Attention이 트랜스포머의 핵심입니다", "start": 32.0, "end": 37.5},
                    {"id": "u_sem01_000002_0000085000", "text": "GPT-4는 RLHF를 통해 사람의 선호도를 학습합니다", "start": 85.0, "end": 92.3},
                    {"id": "u_sem01_000003_0000150000", "text": "Gemini는 MoE 아키텍처로 효율성을 높였습니다", "start": 150.0, "end": 157.0},
                    {"id": "u_sem01_000004_0000210000", "text": "멀티모달 AI가 의료 분야에서 큰 잠재력을 보입니다", "start": 210.0, "end": 217.5},
                ],
                "entities": [
                    {"name": "m_sem01::Transformer", "entity_type": "concept", "description": "Self-Attention 기반 신경망 아키텍처"},
                    {"name": "m_sem01::Self-Attention", "entity_type": "concept", "description": "시퀀스 내 모든 위치 간 관계 계산"},
                    {"name": "m_sem01::GPT-4", "entity_type": "technology", "description": "OpenAI 대규모 멀티모달 LLM"},
                    {"name": "m_sem01::LLaMA", "entity_type": "technology", "description": "Meta 오픈소스 LLM"},
                    {"name": "m_sem01::Gemini", "entity_type": "technology", "description": "Google DeepMind 멀티모달 AI"},
                    {"name": "m_sem01::RLHF", "entity_type": "concept", "description": "인간 피드백 기반 강화학습"},
                    {"name": "m_sem01::OpenAI", "entity_type": "organization", "description": "GPT 시리즈 개발 AI 연구소"},
                    {"name": "m_sem01::Google DeepMind", "entity_type": "organization", "description": "Gemini, AlphaFold 개발"},
                    {"name": "m_sem01::MoE", "entity_type": "concept", "description": "Mixture of Experts 아키텍처"},
                ],
            },
            "edges": {
                "discussed": [
                    {"meeting_id": "m_sem01", "topic": "m_sem01::트랜스포머 아키텍처의 진화"},
                    {"meeting_id": "m_sem01", "topic": "m_sem01::대규모 LLM 학습 전략"},
                    {"meeting_id": "m_sem01", "topic": "m_sem01::멀티모달 AI의 현재와 미래"},
                ],
                "proposed": [
                    {"person": "정민수", "topic": "m_sem01::트랜스포머 아키텍처의 진화"},
                    {"person": "정민수", "topic": "m_sem01::대규모 LLM 학습 전략"},
                    {"person": "정민수", "topic": "m_sem01::멀티모달 AI의 현재와 미래"},
                ],
                "assigned_to": [{"person": "최한결", "task": "m_sem01::트랜스포머 논문 리뷰 정리"}],
                "resulted_in": [],
                "spoke": [
                    {"person": "정민수", "utterance_id": "u_sem01_000000_0000005000"},
                    {"person": "정민수", "utterance_id": "u_sem01_000001_0000032000"},
                    {"person": "정민수", "utterance_id": "u_sem01_000002_0000085000"},
                    {"person": "정민수", "utterance_id": "u_sem01_000003_0000150000"},
                    {"person": "정민수", "utterance_id": "u_sem01_000004_0000210000"},
                ],
                "next": [
                    {"from_utterance_id": "u_sem01_000000_0000005000", "to_utterance_id": "u_sem01_000001_0000032000"},
                    {"from_utterance_id": "u_sem01_000001_0000032000", "to_utterance_id": "u_sem01_000002_0000085000"},
                    {"from_utterance_id": "u_sem01_000002_0000085000", "to_utterance_id": "u_sem01_000003_0000150000"},
                    {"from_utterance_id": "u_sem01_000003_0000150000", "to_utterance_id": "u_sem01_000004_0000210000"},
                ],
                "contains": [
                    {"meeting_id": "m_sem01", "utterance_id": "u_sem01_000000_0000005000"},
                    {"meeting_id": "m_sem01", "utterance_id": "u_sem01_000001_0000032000"},
                    {"meeting_id": "m_sem01", "utterance_id": "u_sem01_000002_0000085000"},
                    {"meeting_id": "m_sem01", "utterance_id": "u_sem01_000003_0000150000"},
                    {"meeting_id": "m_sem01", "utterance_id": "u_sem01_000004_0000210000"},
                ],
                "has_task": [{"meeting_id": "m_sem01", "task": "m_sem01::트랜스포머 논문 리뷰 정리"}],
                "has_decision": [],
                "related_to": [
                    {"source": "m_sem01::Transformer", "relation_type": "핵심 구성요소", "target": "m_sem01::Self-Attention"},
                    {"source": "m_sem01::GPT-4", "relation_type": "기반 아키텍처", "target": "m_sem01::Transformer"},
                    {"source": "m_sem01::GPT-4", "relation_type": "학습 기법", "target": "m_sem01::RLHF"},
                    {"source": "m_sem01::OpenAI", "relation_type": "개발", "target": "m_sem01::GPT-4"},
                    {"source": "m_sem01::Google DeepMind", "relation_type": "개발", "target": "m_sem01::Gemini"},
                    {"source": "m_sem01::LLaMA", "relation_type": "기반 아키텍처", "target": "m_sem01::Transformer"},
                    {"source": "m_sem01::Gemini", "relation_type": "사용 아키텍처", "target": "m_sem01::MoE"},
                ],
                "mentions": [
                    {"topic": "m_sem01::트랜스포머 아키텍처의 진화", "entity": "m_sem01::Transformer"},
                    {"topic": "m_sem01::트랜스포머 아키텍처의 진화", "entity": "m_sem01::Self-Attention"},
                    {"topic": "m_sem01::대규모 LLM 학습 전략", "entity": "m_sem01::GPT-4"},
                    {"topic": "m_sem01::대규모 LLM 학습 전략", "entity": "m_sem01::LLaMA"},
                    {"topic": "m_sem01::대규모 LLM 학습 전략", "entity": "m_sem01::RLHF"},
                    {"topic": "m_sem01::멀티모달 AI의 현재와 미래", "entity": "m_sem01::Gemini"},
                    {"topic": "m_sem01::멀티모달 AI의 현재와 미래", "entity": "m_sem01::MoE"},
                ],
                "has_entity": [
                    {"meeting_id": "m_sem01", "entity": "m_sem01::Transformer"},
                    {"meeting_id": "m_sem01", "entity": "m_sem01::Self-Attention"},
                    {"meeting_id": "m_sem01", "entity": "m_sem01::GPT-4"},
                    {"meeting_id": "m_sem01", "entity": "m_sem01::LLaMA"},
                    {"meeting_id": "m_sem01", "entity": "m_sem01::Gemini"},
                    {"meeting_id": "m_sem01", "entity": "m_sem01::RLHF"},
                    {"meeting_id": "m_sem01", "entity": "m_sem01::OpenAI"},
                    {"meeting_id": "m_sem01", "entity": "m_sem01::Google DeepMind"},
                    {"meeting_id": "m_sem01", "entity": "m_sem01::MoE"},
                ],
            },
        },
    },
    # ── 2: 프로젝트 온보딩 ──
    {
        "meta": {"title": "프로젝트 온보딩", "icon": "🚀", "desc": "팀 구조, 기술 스택, 일정 계획 배정 · Task 풍부"},
        "analysis_result": {
            "topics": [
                {"title": "팀 구조 소개", "summary": "프론트엔드, 백엔드, QA, 디자인 4개 파트 구성. 각 파트별 역할과 협업 방식 안내.", "proposer": "한지원"},
                {"title": "기술 스택 가이드", "summary": "프론트엔드는 React + TypeScript, 백엔드는 Spring Boot + PostgreSQL, 디자인은 Figma, 프로젝트 관리는 Jira 사용.", "proposer": "한지원"},
                {"title": "Q1 일정 계획", "summary": "3월 말까지 MVP 완성 목표. 2주 단위 스프린트 운영. 코드 리뷰 필수.", "proposer": "한지원"},
            ],
            "decisions": [
                {"description": "2주 스프린트 사이클 채택", "related_topic": "Q1 일정 계획"},
                {"description": "코드 리뷰 필수 정책 시행", "related_topic": "Q1 일정 계획"},
            ],
            "tasks": [
                {"description": "개발 환경 세팅", "assignee": "김도현", "deadline": "2025-03-10", "status": "in_progress"},
                {"description": "API 문서 숙지", "assignee": "박소율", "deadline": "2025-03-12", "status": "pending"},
                {"description": "QA 테스트 케이스 작성", "assignee": "오승현", "deadline": "2025-03-15", "status": "pending"},
                {"description": "디자인 시스템 컴포넌트 정리", "assignee": "윤서아", "deadline": "2025-03-14", "status": "pending"},
                {"description": "Jira 보드 초기 세팅", "assignee": "한지원", "deadline": "2025-03-08", "status": "done"},
            ],
            "people": [
                {"name": "한지원", "role": "팀장"},
                {"name": "김도현", "role": "백엔드 개발자"},
                {"name": "박소율", "role": "프론트엔드 개발자"},
                {"name": "오승현", "role": "QA 엔지니어"},
                {"name": "윤서아", "role": "디자이너"},
            ],
            "entities": [
                {"name": "React", "entity_type": "technology", "description": "Meta의 UI 라이브러리"},
                {"name": "Spring Boot", "entity_type": "technology", "description": "Java 기반 웹 프레임워크"},
                {"name": "Figma", "entity_type": "technology", "description": "협업 디자인 도구"},
                {"name": "Jira", "entity_type": "technology", "description": "Atlassian 프로젝트 관리 도구"},
                {"name": "PostgreSQL", "entity_type": "technology", "description": "오픈소스 관계형 데이터베이스"},
                {"name": "TypeScript", "entity_type": "technology", "description": "타입 안전 JavaScript 슈퍼셋"},
            ],
            "relations": [
                {"source": "React", "target": "TypeScript", "relation_type": "함께 사용"},
                {"source": "Spring Boot", "target": "PostgreSQL", "relation_type": "데이터베이스 연동"},
                {"source": "Jira", "target": "Figma", "relation_type": "작업 연계"},
            ],
        },
        "graph_dump": {
            "schema_version": 3,
            "nodes": {
                "meetings": [{"id": "m_onb01", "title": "프로젝트 온보딩", "date": "2025-03-07", "source_file": "onboarding.wav"}],
                "people": [
                    {"name": "한지원", "role": "팀장"},
                    {"name": "김도현", "role": "백엔드 개발자"},
                    {"name": "박소율", "role": "프론트엔드 개발자"},
                    {"name": "오승현", "role": "QA 엔지니어"},
                    {"name": "윤서아", "role": "디자이너"},
                ],
                "topics": [
                    {"title": "m_onb01::팀 구조 소개", "summary": "4개 파트 구성 및 협업 방식"},
                    {"title": "m_onb01::기술 스택 가이드", "summary": "React, Spring Boot, Figma, Jira 활용"},
                    {"title": "m_onb01::Q1 일정 계획", "summary": "3월 말 MVP, 2주 스프린트"},
                ],
                "tasks": [
                    {"description": "m_onb01::개발 환경 세팅", "deadline": "2025-03-10", "status": "in_progress"},
                    {"description": "m_onb01::API 문서 숙지", "deadline": "2025-03-12", "status": "pending"},
                    {"description": "m_onb01::QA 테스트 케이스 작성", "deadline": "2025-03-15", "status": "pending"},
                    {"description": "m_onb01::디자인 시스템 컴포넌트 정리", "deadline": "2025-03-14", "status": "pending"},
                    {"description": "m_onb01::Jira 보드 초기 세팅", "deadline": "2025-03-08", "status": "done"},
                ],
                "decisions": [
                    {"description": "m_onb01::2주 스프린트 사이클 채택"},
                    {"description": "m_onb01::코드 리뷰 필수 정책 시행"},
                ],
                "utterances": [
                    {"id": "u_onb01_000000_0000008000", "text": "오늘 온보딩에서 팀 구조부터 설명하겠습니다", "start": 8.0, "end": 12.5},
                    {"id": "u_onb01_000001_0000045000", "text": "프론트는 React와 TypeScript를 씁니다", "start": 45.0, "end": 50.2},
                    {"id": "u_onb01_000002_0000095000", "text": "백엔드는 Spring Boot와 PostgreSQL 사용합니다", "start": 95.0, "end": 101.3},
                    {"id": "u_onb01_000003_0000140000", "text": "3월 말까지 MVP를 완성하는 게 목표입니다", "start": 140.0, "end": 146.0},
                ],
                "entities": [
                    {"name": "m_onb01::React", "entity_type": "technology", "description": "Meta UI 라이브러리"},
                    {"name": "m_onb01::Spring Boot", "entity_type": "technology", "description": "Java 웹 프레임워크"},
                    {"name": "m_onb01::Figma", "entity_type": "technology", "description": "협업 디자인 도구"},
                    {"name": "m_onb01::Jira", "entity_type": "technology", "description": "프로젝트 관리 도구"},
                    {"name": "m_onb01::PostgreSQL", "entity_type": "technology", "description": "관계형 DB"},
                    {"name": "m_onb01::TypeScript", "entity_type": "technology", "description": "타입 안전 JS 슈퍼셋"},
                ],
            },
            "edges": {
                "discussed": [
                    {"meeting_id": "m_onb01", "topic": "m_onb01::팀 구조 소개"},
                    {"meeting_id": "m_onb01", "topic": "m_onb01::기술 스택 가이드"},
                    {"meeting_id": "m_onb01", "topic": "m_onb01::Q1 일정 계획"},
                ],
                "proposed": [
                    {"person": "한지원", "topic": "m_onb01::팀 구조 소개"},
                    {"person": "한지원", "topic": "m_onb01::기술 스택 가이드"},
                    {"person": "한지원", "topic": "m_onb01::Q1 일정 계획"},
                ],
                "assigned_to": [
                    {"person": "김도현", "task": "m_onb01::개발 환경 세팅"},
                    {"person": "박소율", "task": "m_onb01::API 문서 숙지"},
                    {"person": "오승현", "task": "m_onb01::QA 테스트 케이스 작성"},
                    {"person": "윤서아", "task": "m_onb01::디자인 시스템 컴포넌트 정리"},
                    {"person": "한지원", "task": "m_onb01::Jira 보드 초기 세팅"},
                ],
                "resulted_in": [
                    {"topic": "m_onb01::Q1 일정 계획", "decision": "m_onb01::2주 스프린트 사이클 채택"},
                    {"topic": "m_onb01::Q1 일정 계획", "decision": "m_onb01::코드 리뷰 필수 정책 시행"},
                ],
                "spoke": [
                    {"person": "한지원", "utterance_id": "u_onb01_000000_0000008000"},
                    {"person": "한지원", "utterance_id": "u_onb01_000001_0000045000"},
                    {"person": "한지원", "utterance_id": "u_onb01_000002_0000095000"},
                    {"person": "한지원", "utterance_id": "u_onb01_000003_0000140000"},
                ],
                "next": [
                    {"from_utterance_id": "u_onb01_000000_0000008000", "to_utterance_id": "u_onb01_000001_0000045000"},
                    {"from_utterance_id": "u_onb01_000001_0000045000", "to_utterance_id": "u_onb01_000002_0000095000"},
                    {"from_utterance_id": "u_onb01_000002_0000095000", "to_utterance_id": "u_onb01_000003_0000140000"},
                ],
                "contains": [
                    {"meeting_id": "m_onb01", "utterance_id": "u_onb01_000000_0000008000"},
                    {"meeting_id": "m_onb01", "utterance_id": "u_onb01_000001_0000045000"},
                    {"meeting_id": "m_onb01", "utterance_id": "u_onb01_000002_0000095000"},
                    {"meeting_id": "m_onb01", "utterance_id": "u_onb01_000003_0000140000"},
                ],
                "has_task": [
                    {"meeting_id": "m_onb01", "task": "m_onb01::개발 환경 세팅"},
                    {"meeting_id": "m_onb01", "task": "m_onb01::API 문서 숙지"},
                    {"meeting_id": "m_onb01", "task": "m_onb01::QA 테스트 케이스 작성"},
                    {"meeting_id": "m_onb01", "task": "m_onb01::디자인 시스템 컴포넌트 정리"},
                    {"meeting_id": "m_onb01", "task": "m_onb01::Jira 보드 초기 세팅"},
                ],
                "has_decision": [
                    {"meeting_id": "m_onb01", "decision": "m_onb01::2주 스프린트 사이클 채택"},
                    {"meeting_id": "m_onb01", "decision": "m_onb01::코드 리뷰 필수 정책 시행"},
                ],
                "related_to": [
                    {"source": "m_onb01::React", "relation_type": "함께 사용", "target": "m_onb01::TypeScript"},
                    {"source": "m_onb01::Spring Boot", "relation_type": "DB 연동", "target": "m_onb01::PostgreSQL"},
                    {"source": "m_onb01::Jira", "relation_type": "작업 연계", "target": "m_onb01::Figma"},
                ],
                "mentions": [
                    {"topic": "m_onb01::기술 스택 가이드", "entity": "m_onb01::React"},
                    {"topic": "m_onb01::기술 스택 가이드", "entity": "m_onb01::Spring Boot"},
                    {"topic": "m_onb01::기술 스택 가이드", "entity": "m_onb01::Figma"},
                    {"topic": "m_onb01::기술 스택 가이드", "entity": "m_onb01::Jira"},
                    {"topic": "m_onb01::기술 스택 가이드", "entity": "m_onb01::PostgreSQL"},
                    {"topic": "m_onb01::기술 스택 가이드", "entity": "m_onb01::TypeScript"},
                ],
                "has_entity": [
                    {"meeting_id": "m_onb01", "entity": "m_onb01::React"},
                    {"meeting_id": "m_onb01", "entity": "m_onb01::Spring Boot"},
                    {"meeting_id": "m_onb01", "entity": "m_onb01::Figma"},
                    {"meeting_id": "m_onb01", "entity": "m_onb01::Jira"},
                    {"meeting_id": "m_onb01", "entity": "m_onb01::PostgreSQL"},
                    {"meeting_id": "m_onb01", "entity": "m_onb01::TypeScript"},
                ],
            },
        },
    },
]


# ══════════════════════════════════════════════════════════════
# PNG 생성 — ShareManager.create_card() 활용
# ══════════════════════════════════════════════════════════════


def generate_demo_png(bundle: dict, filename: str):
    """ShareManager.create_card()를 사용하여 카드 이미지 + 메타데이터 임베딩 PNG를 생성."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    mgr = ShareManager(output_dir=OUTPUT_DIR)

    # 카드 비주얼에 사용할 분석 결과
    analysis_result = bundle["analysis_result"]

    # PNG 메타데이터에 임베딩할 전체 번들 페이로드
    payload = {
        "format": "speaknode_graph_bundle_v1",
        "analysis_result": analysis_result,
        "graph_dump": bundle["graph_dump"],
    }

    return mgr.create_card(analysis_result, filename, payload=payload)


# ══════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════
DEMO_FILES = [
    "demo_weekly_meeting.png",
    "demo_ai_seminar.png",
    "demo_project_onboarding.png",
]


def main():
    print(f"Output directory: {OUTPUT_DIR}")
    print("=" * 50)

    for bundle, filename in zip(DEMO_BUNDLES, DEMO_FILES):
        path = generate_demo_png(bundle, filename)
        size_kb = os.path.getsize(path) / 1024
        print(f"  ✓ {filename}  ({size_kb:.1f} KB)")

        # 검증: 저장된 PNG에서 데이터 추출 가능한지 확인
        mgr = ShareManager(output_dir=OUTPUT_DIR)
        loaded = mgr.load_data_from_image(path)
        if loaded and loaded.get("format") == "speaknode_graph_bundle_v1":
            topics_count = len(loaded.get("analysis_result", {}).get("topics", []))
            print(f"    └─ Verified: {topics_count} topics extracted from PNG metadata")
        else:
            print(f"    └─ ⚠ Verification failed!")

    print("=" * 50)
    print(f"Done. {len(DEMO_FILES)} demo PNGs generated in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
