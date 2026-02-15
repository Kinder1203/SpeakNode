#!/usr/bin/env python3
"""
SpeakNode Demo PNG Generator
=============================
DEMO_BUNDLES (index.html과 동일한 데이터)를 PNG tEXt 청크에 내장하여
실제 SpeakNode PNG 공유 포맷과 동일한 파일을 생성합니다.

Usage:
    pip install Pillow
    python scripts/generate_demo_pngs.py

Output:
    docs/demo_meeting.png
    docs/demo_seminar.png
    docs/demo_onboarding.png
"""

import json, zlib, base64, os
from PIL import Image, PngImagePlugin

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "docs")

# ──────────────────────────────────────────────────────────────
# Demo Bundle Data (speaknode_graph_bundle_v1)
# ──────────────────────────────────────────────────────────────
DEMOS = [
    {
        "filename": "demo_meeting.png",
        "bg_color": (15, 23, 42),  # dark blue
        "bundle": {
            "format": "speaknode_graph_bundle_v1",
            "include_embeddings": False,
            "analysis_result": {
                "topics": [
                    {"title": "API 서버 마이그레이션", "summary": "FastAPI v5.2.0 업그레이드를 이번 주 내로 완료하기로 논의.", "proposer": "김태호"},
                    {"title": "RAG 파이프라인 최적화", "summary": "Hybrid RAG의 정확도 개선을 위해 Cypher 쿼리를 추가.", "proposer": "이서연"},
                    {"title": "모바일 UI 개선", "summary": "Material 3 다크 테마를 전면 채택.", "proposer": "박준혁"},
                    {"title": "그래프 스키마 확장", "summary": "감정 분석 노드 추가 가능성 논의.", "proposer": "최유진"},
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
                    "meetings": [{"id": "m_w01", "title": "주간 기획 회의", "date": "2025-02-10", "source_file": "weekly.wav"}, {"id": "m_w02", "title": "디자인 리뷰", "date": "2025-02-12", "source_file": "design.mp3"}],
                    "people": [{"name": "김태호", "role": "PM"}, {"name": "이서연", "role": "Developer"}, {"name": "박준혁", "role": "Designer"}, {"name": "최유진", "role": "Data Engineer"}],
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
                    "decisions": [{"description": "m_w01::API v5.2.0 즉시 마이그레이션"}, {"description": "m_w02::Material 3 다크 테마 채택"}],
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
                    "discussed": [{"meeting_id": "m_w01", "topic": "m_w01::API 서버 마이그레이션"}, {"meeting_id": "m_w01", "topic": "m_w01::RAG 파이프라인 최적화"}, {"meeting_id": "m_w02", "topic": "m_w02::모바일 UI 개선"}, {"meeting_id": "m_w01", "topic": "m_w01::그래프 스키마 확장"}],
                    "proposed": [{"person": "김태호", "topic": "m_w01::API 서버 마이그레이션"}, {"person": "이서연", "topic": "m_w01::RAG 파이프라인 최적화"}, {"person": "박준혁", "topic": "m_w02::모바일 UI 개선"}, {"person": "최유진", "topic": "m_w01::그래프 스키마 확장"}],
                    "assigned_to": [{"person": "이서연", "task": "m_w01::Ktor 클라이언트 업데이트"}, {"person": "최유진", "task": "m_w01::벡터 인덱스 벤치마크"}, {"person": "박준혁", "task": "m_w02::UI 프로토타입 제작"}, {"person": "이서연", "task": "m_w01::Cypher 쿼리 최적화"}],
                    "resulted_in": [{"topic": "m_w01::API 서버 마이그레이션", "decision": "m_w01::API v5.2.0 즉시 마이그레이션"}, {"topic": "m_w02::모바일 UI 개선", "decision": "m_w02::Material 3 다크 테마 채택"}],
                    "spoke": [{"person": "김태호", "utterance_id": "u_w01_000000_0000012500"}, {"person": "최유진", "utterance_id": "u_w01_000001_0000045100"}, {"person": "박준혁", "utterance_id": "u_w02_000002_0000068000"}, {"person": "이서연", "utterance_id": "u_w01_000003_0000091200"}],
                    "next": [{"from_utterance_id": "u_w01_000000_0000012500", "to_utterance_id": "u_w01_000001_0000045100"}, {"from_utterance_id": "u_w01_000001_0000045100", "to_utterance_id": "u_w01_000003_0000091200"}],
                    "contains": [{"meeting_id": "m_w01", "utterance_id": "u_w01_000000_0000012500"}, {"meeting_id": "m_w01", "utterance_id": "u_w01_000001_0000045100"}, {"meeting_id": "m_w02", "utterance_id": "u_w02_000002_0000068000"}, {"meeting_id": "m_w01", "utterance_id": "u_w01_000003_0000091200"}],
                    "has_task": [{"meeting_id": "m_w01", "task": "m_w01::Ktor 클라이언트 업데이트"}, {"meeting_id": "m_w01", "task": "m_w01::벡터 인덱스 벤치마크"}, {"meeting_id": "m_w02", "task": "m_w02::UI 프로토타입 제작"}, {"meeting_id": "m_w01", "task": "m_w01::Cypher 쿼리 최적화"}],
                    "has_decision": [{"meeting_id": "m_w01", "decision": "m_w01::API v5.2.0 즉시 마이그레이션"}, {"meeting_id": "m_w02", "decision": "m_w02::Material 3 다크 테마 채택"}],
                    "related_to": [{"source": "m_w01::FastAPI", "relation_type": "통합", "target": "m_w01::KuzuDB"}, {"source": "m_w01::LangChain", "relation_type": "구현 프레임워크", "target": "m_w01::Hybrid RAG"}],
                    "mentions": [{"topic": "m_w01::API 서버 마이그레이션", "entity": "m_w01::FastAPI"}, {"topic": "m_w01::RAG 파이프라인 최적화", "entity": "m_w01::Hybrid RAG"}, {"topic": "m_w01::RAG 파이프라인 최적화", "entity": "m_w01::LangChain"}, {"topic": "m_w02::모바일 UI 개선", "entity": "m_w02::Material 3"}, {"topic": "m_w01::그래프 스키마 확장", "entity": "m_w01::KuzuDB"}],
                    "has_entity": [{"meeting_id": "m_w01", "entity": "m_w01::FastAPI"}, {"meeting_id": "m_w01", "entity": "m_w01::KuzuDB"}, {"meeting_id": "m_w01", "entity": "m_w01::LangChain"}, {"meeting_id": "m_w01", "entity": "m_w01::Hybrid RAG"}, {"meeting_id": "m_w02", "entity": "m_w02::Material 3"}],
                },
            },
        },
    },
    {
        "filename": "demo_seminar.png",
        "bg_color": (20, 10, 30),  # dark purple
        "bundle": {
            "format": "speaknode_graph_bundle_v1",
            "include_embeddings": False,
            "analysis_result": {
                "topics": [
                    {"title": "트랜스포머 아키텍처의 진화", "summary": "2017년 Attention Is All You Need 이후 트랜스포머 확장", "proposer": "정민수"},
                    {"title": "대규모 LLM 학습 전략", "summary": "GPT-4, LLaMA, Qwen 학습 기법 비교", "proposer": "정민수"},
                    {"title": "멀티모달 AI의 현재와 미래", "summary": "GPT-4V, Gemini 등 통합 모델 발전", "proposer": "정민수"},
                ],
                "decisions": [],
                "tasks": [{"description": "트랜스포머 논문 리뷰 정리", "assignee": "최한결", "deadline": "2025-03-01", "status": "pending"}],
                "people": [{"name": "정민수", "role": "강연자"}, {"name": "최한결", "role": "참석자"}],
                "entities": [
                    {"name": "Transformer", "entity_type": "concept", "description": "Self-Attention 기반 신경망 아키텍처"},
                    {"name": "Self-Attention", "entity_type": "concept", "description": "시퀀스 내 관계 계산 메커니즘"},
                    {"name": "GPT-4", "entity_type": "technology", "description": "OpenAI 멀티모달 LLM"},
                    {"name": "LLaMA", "entity_type": "technology", "description": "Meta 오픈소스 LLM"},
                    {"name": "Gemini", "entity_type": "technology", "description": "Google DeepMind 멀티모달 AI"},
                    {"name": "RLHF", "entity_type": "concept", "description": "인간 피드백 기반 강화학습"},
                    {"name": "OpenAI", "entity_type": "organization", "description": "GPT 시리즈 개발"},
                    {"name": "Google DeepMind", "entity_type": "organization", "description": "Gemini, AlphaFold 개발"},
                    {"name": "MoE", "entity_type": "concept", "description": "Mixture of Experts"},
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
                        {"title": "m_sem01::트랜스포머 아키텍처의 진화", "summary": "Attention Is All You Need 이후 확장"},
                        {"title": "m_sem01::대규모 LLM 학습 전략", "summary": "GPT-4, LLaMA, Qwen 학습 기법 비교"},
                        {"title": "m_sem01::멀티모달 AI의 현재와 미래", "summary": "GPT-4V, Gemini 등 통합 모델"},
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
                        {"name": "m_sem01::Transformer", "entity_type": "concept", "description": "Self-Attention 기반 신경망"},
                        {"name": "m_sem01::Self-Attention", "entity_type": "concept", "description": "시퀀스 내 관계 계산"},
                        {"name": "m_sem01::GPT-4", "entity_type": "technology", "description": "OpenAI 멀티모달 LLM"},
                        {"name": "m_sem01::LLaMA", "entity_type": "technology", "description": "Meta 오픈소스 LLM"},
                        {"name": "m_sem01::Gemini", "entity_type": "technology", "description": "Google DeepMind 멀티모달 AI"},
                        {"name": "m_sem01::RLHF", "entity_type": "concept", "description": "인간 피드백 강화학습"},
                        {"name": "m_sem01::OpenAI", "entity_type": "organization", "description": "GPT 시리즈 개발"},
                        {"name": "m_sem01::Google DeepMind", "entity_type": "organization", "description": "Gemini, AlphaFold 개발"},
                        {"name": "m_sem01::MoE", "entity_type": "concept", "description": "Mixture of Experts"},
                    ],
                },
                "edges": {
                    "discussed": [{"meeting_id": "m_sem01", "topic": "m_sem01::트랜스포머 아키텍처의 진화"}, {"meeting_id": "m_sem01", "topic": "m_sem01::대규모 LLM 학습 전략"}, {"meeting_id": "m_sem01", "topic": "m_sem01::멀티모달 AI의 현재와 미래"}],
                    "proposed": [{"person": "정민수", "topic": "m_sem01::트랜스포머 아키텍처의 진화"}, {"person": "정민수", "topic": "m_sem01::대규모 LLM 학습 전략"}, {"person": "정민수", "topic": "m_sem01::멀티모달 AI의 현재와 미래"}],
                    "assigned_to": [{"person": "최한결", "task": "m_sem01::트랜스포머 논문 리뷰 정리"}],
                    "resulted_in": [],
                    "spoke": [{"person": "정민수", "utterance_id": "u_sem01_000000_0000005000"}, {"person": "정민수", "utterance_id": "u_sem01_000001_0000032000"}, {"person": "정민수", "utterance_id": "u_sem01_000002_0000085000"}, {"person": "정민수", "utterance_id": "u_sem01_000003_0000150000"}, {"person": "정민수", "utterance_id": "u_sem01_000004_0000210000"}],
                    "next": [{"from_utterance_id": "u_sem01_000000_0000005000", "to_utterance_id": "u_sem01_000001_0000032000"}, {"from_utterance_id": "u_sem01_000001_0000032000", "to_utterance_id": "u_sem01_000002_0000085000"}, {"from_utterance_id": "u_sem01_000002_0000085000", "to_utterance_id": "u_sem01_000003_0000150000"}, {"from_utterance_id": "u_sem01_000003_0000150000", "to_utterance_id": "u_sem01_000004_0000210000"}],
                    "contains": [{"meeting_id": "m_sem01", "utterance_id": "u_sem01_000000_0000005000"}, {"meeting_id": "m_sem01", "utterance_id": "u_sem01_000001_0000032000"}, {"meeting_id": "m_sem01", "utterance_id": "u_sem01_000002_0000085000"}, {"meeting_id": "m_sem01", "utterance_id": "u_sem01_000003_0000150000"}, {"meeting_id": "m_sem01", "utterance_id": "u_sem01_000004_0000210000"}],
                    "has_task": [{"meeting_id": "m_sem01", "task": "m_sem01::트랜스포머 논문 리뷰 정리"}],
                    "has_decision": [],
                    "related_to": [{"source": "m_sem01::Transformer", "relation_type": "핵심 구성요소", "target": "m_sem01::Self-Attention"}, {"source": "m_sem01::GPT-4", "relation_type": "기반 아키텍처", "target": "m_sem01::Transformer"}, {"source": "m_sem01::GPT-4", "relation_type": "학습 기법", "target": "m_sem01::RLHF"}, {"source": "m_sem01::OpenAI", "relation_type": "개발", "target": "m_sem01::GPT-4"}, {"source": "m_sem01::Google DeepMind", "relation_type": "개발", "target": "m_sem01::Gemini"}, {"source": "m_sem01::LLaMA", "relation_type": "기반 아키텍처", "target": "m_sem01::Transformer"}, {"source": "m_sem01::Gemini", "relation_type": "사용 아키텍처", "target": "m_sem01::MoE"}],
                    "mentions": [{"topic": "m_sem01::트랜스포머 아키텍처의 진화", "entity": "m_sem01::Transformer"}, {"topic": "m_sem01::트랜스포머 아키텍처의 진화", "entity": "m_sem01::Self-Attention"}, {"topic": "m_sem01::대규모 LLM 학습 전략", "entity": "m_sem01::GPT-4"}, {"topic": "m_sem01::대규모 LLM 학습 전략", "entity": "m_sem01::LLaMA"}, {"topic": "m_sem01::대규모 LLM 학습 전략", "entity": "m_sem01::RLHF"}, {"topic": "m_sem01::멀티모달 AI의 현재와 미래", "entity": "m_sem01::Gemini"}, {"topic": "m_sem01::멀티모달 AI의 현재와 미래", "entity": "m_sem01::MoE"}],
                    "has_entity": [{"meeting_id": "m_sem01", "entity": "m_sem01::Transformer"}, {"meeting_id": "m_sem01", "entity": "m_sem01::Self-Attention"}, {"meeting_id": "m_sem01", "entity": "m_sem01::GPT-4"}, {"meeting_id": "m_sem01", "entity": "m_sem01::LLaMA"}, {"meeting_id": "m_sem01", "entity": "m_sem01::Gemini"}, {"meeting_id": "m_sem01", "entity": "m_sem01::RLHF"}, {"meeting_id": "m_sem01", "entity": "m_sem01::OpenAI"}, {"meeting_id": "m_sem01", "entity": "m_sem01::Google DeepMind"}, {"meeting_id": "m_sem01", "entity": "m_sem01::MoE"}],
                },
            },
        },
    },
    {
        "filename": "demo_onboarding.png",
        "bg_color": (10, 25, 15),  # dark green
        "bundle": {
            "format": "speaknode_graph_bundle_v1",
            "include_embeddings": False,
            "analysis_result": {
                "topics": [
                    {"title": "팀 구조 소개", "summary": "프론트엔드, 백엔드, QA, 디자인 4개 파트 구성", "proposer": "한지원"},
                    {"title": "기술 스택 가이드", "summary": "React + TypeScript, Spring Boot + PostgreSQL, Figma, Jira", "proposer": "한지원"},
                    {"title": "Q1 일정 계획", "summary": "3월 말 MVP 완성 목표, 2주 스프린트", "proposer": "한지원"},
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
                    {"name": "React", "entity_type": "technology", "description": "Meta UI 라이브러리"},
                    {"name": "Spring Boot", "entity_type": "technology", "description": "Java 웹 프레임워크"},
                    {"name": "Figma", "entity_type": "technology", "description": "협업 디자인 도구"},
                    {"name": "Jira", "entity_type": "technology", "description": "프로젝트 관리 도구"},
                    {"name": "PostgreSQL", "entity_type": "technology", "description": "관계형 DB"},
                    {"name": "TypeScript", "entity_type": "technology", "description": "타입 안전 JS 슈퍼셋"},
                ],
                "relations": [
                    {"source": "React", "target": "TypeScript", "relation_type": "함께 사용"},
                    {"source": "Spring Boot", "target": "PostgreSQL", "relation_type": "DB 연동"},
                    {"source": "Jira", "target": "Figma", "relation_type": "작업 연계"},
                ],
            },
            "graph_dump": {
                "schema_version": 3,
                "nodes": {
                    "meetings": [{"id": "m_onb01", "title": "프로젝트 온보딩", "date": "2025-03-07", "source_file": "onboarding.wav"}],
                    "people": [{"name": "한지원", "role": "팀장"}, {"name": "김도현", "role": "백엔드 개발자"}, {"name": "박소율", "role": "프론트엔드 개발자"}, {"name": "오승현", "role": "QA 엔지니어"}, {"name": "윤서아", "role": "디자이너"}],
                    "topics": [
                        {"title": "m_onb01::팀 구조 소개", "summary": "4개 파트 구성 및 협업 방식"},
                        {"title": "m_onb01::기술 스택 가이드", "summary": "React, Spring Boot, Figma, Jira"},
                        {"title": "m_onb01::Q1 일정 계획", "summary": "3월 말 MVP, 2주 스프린트"},
                    ],
                    "tasks": [
                        {"description": "m_onb01::개발 환경 세팅", "deadline": "2025-03-10", "status": "in_progress"},
                        {"description": "m_onb01::API 문서 숙지", "deadline": "2025-03-12", "status": "pending"},
                        {"description": "m_onb01::QA 테스트 케이스 작성", "deadline": "2025-03-15", "status": "pending"},
                        {"description": "m_onb01::디자인 시스템 컴포넌트 정리", "deadline": "2025-03-14", "status": "pending"},
                        {"description": "m_onb01::Jira 보드 초기 세팅", "deadline": "2025-03-08", "status": "done"},
                    ],
                    "decisions": [{"description": "m_onb01::2주 스프린트 사이클 채택"}, {"description": "m_onb01::코드 리뷰 필수 정책 시행"}],
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
                    "discussed": [{"meeting_id": "m_onb01", "topic": "m_onb01::팀 구조 소개"}, {"meeting_id": "m_onb01", "topic": "m_onb01::기술 스택 가이드"}, {"meeting_id": "m_onb01", "topic": "m_onb01::Q1 일정 계획"}],
                    "proposed": [{"person": "한지원", "topic": "m_onb01::팀 구조 소개"}, {"person": "한지원", "topic": "m_onb01::기술 스택 가이드"}, {"person": "한지원", "topic": "m_onb01::Q1 일정 계획"}],
                    "assigned_to": [{"person": "김도현", "task": "m_onb01::개발 환경 세팅"}, {"person": "박소율", "task": "m_onb01::API 문서 숙지"}, {"person": "오승현", "task": "m_onb01::QA 테스트 케이스 작성"}, {"person": "윤서아", "task": "m_onb01::디자인 시스템 컴포넌트 정리"}, {"person": "한지원", "task": "m_onb01::Jira 보드 초기 세팅"}],
                    "resulted_in": [{"topic": "m_onb01::Q1 일정 계획", "decision": "m_onb01::2주 스프린트 사이클 채택"}, {"topic": "m_onb01::Q1 일정 계획", "decision": "m_onb01::코드 리뷰 필수 정책 시행"}],
                    "spoke": [{"person": "한지원", "utterance_id": "u_onb01_000000_0000008000"}, {"person": "한지원", "utterance_id": "u_onb01_000001_0000045000"}, {"person": "한지원", "utterance_id": "u_onb01_000002_0000095000"}, {"person": "한지원", "utterance_id": "u_onb01_000003_0000140000"}],
                    "next": [{"from_utterance_id": "u_onb01_000000_0000008000", "to_utterance_id": "u_onb01_000001_0000045000"}, {"from_utterance_id": "u_onb01_000001_0000045000", "to_utterance_id": "u_onb01_000002_0000095000"}, {"from_utterance_id": "u_onb01_000002_0000095000", "to_utterance_id": "u_onb01_000003_0000140000"}],
                    "contains": [{"meeting_id": "m_onb01", "utterance_id": "u_onb01_000000_0000008000"}, {"meeting_id": "m_onb01", "utterance_id": "u_onb01_000001_0000045000"}, {"meeting_id": "m_onb01", "utterance_id": "u_onb01_000002_0000095000"}, {"meeting_id": "m_onb01", "utterance_id": "u_onb01_000003_0000140000"}],
                    "has_task": [{"meeting_id": "m_onb01", "task": "m_onb01::개발 환경 세팅"}, {"meeting_id": "m_onb01", "task": "m_onb01::API 문서 숙지"}, {"meeting_id": "m_onb01", "task": "m_onb01::QA 테스트 케이스 작성"}, {"meeting_id": "m_onb01", "task": "m_onb01::디자인 시스템 컴포넌트 정리"}, {"meeting_id": "m_onb01", "task": "m_onb01::Jira 보드 초기 세팅"}],
                    "has_decision": [{"meeting_id": "m_onb01", "decision": "m_onb01::2주 스프린트 사이클 채택"}, {"meeting_id": "m_onb01", "decision": "m_onb01::코드 리뷰 필수 정책 시행"}],
                    "related_to": [{"source": "m_onb01::React", "relation_type": "함께 사용", "target": "m_onb01::TypeScript"}, {"source": "m_onb01::Spring Boot", "relation_type": "DB 연동", "target": "m_onb01::PostgreSQL"}, {"source": "m_onb01::Jira", "relation_type": "작업 연계", "target": "m_onb01::Figma"}],
                    "mentions": [{"topic": "m_onb01::기술 스택 가이드", "entity": "m_onb01::React"}, {"topic": "m_onb01::기술 스택 가이드", "entity": "m_onb01::Spring Boot"}, {"topic": "m_onb01::기술 스택 가이드", "entity": "m_onb01::Figma"}, {"topic": "m_onb01::기술 스택 가이드", "entity": "m_onb01::Jira"}, {"topic": "m_onb01::기술 스택 가이드", "entity": "m_onb01::PostgreSQL"}, {"topic": "m_onb01::기술 스택 가이드", "entity": "m_onb01::TypeScript"}],
                    "has_entity": [{"meeting_id": "m_onb01", "entity": "m_onb01::React"}, {"meeting_id": "m_onb01", "entity": "m_onb01::Spring Boot"}, {"meeting_id": "m_onb01", "entity": "m_onb01::Figma"}, {"meeting_id": "m_onb01", "entity": "m_onb01::Jira"}, {"meeting_id": "m_onb01", "entity": "m_onb01::PostgreSQL"}, {"meeting_id": "m_onb01", "entity": "m_onb01::TypeScript"}],
                },
            },
        },
    },
]


def encode_payload(data: dict) -> str:
    """SpeakNode 포맷: JSON → zlib → base64"""
    json_bytes = json.dumps(data, ensure_ascii=False).encode("utf-8")
    compressed = zlib.compress(json_bytes, level=9)
    return base64.b64encode(compressed).decode("ascii")


def create_demo_png(demo: dict) -> None:
    """데모 PNG 생성 (200x200 단색 이미지 + tEXt 메타데이터)"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    img = Image.new("RGB", (200, 200), demo["bg_color"])
    meta = PngImagePlugin.PngInfo()
    meta.add_text("speaknode_data_zlib_b64", encode_payload(demo["bundle"]))
    meta.add_text("speaknode_version", "1.0.0")

    path = os.path.join(OUTPUT_DIR, demo["filename"])
    img.save(path, pnginfo=meta)

    # 검증
    verify = Image.open(path)
    verify.load()
    raw_meta = verify.text
    assert "speaknode_data_zlib_b64" in raw_meta, "Metadata not found!"
    decoded = json.loads(
        zlib.decompress(base64.b64decode(raw_meta["speaknode_data_zlib_b64"])).decode("utf-8")
    )
    assert decoded["format"] == "speaknode_graph_bundle_v1"
    node_count = sum(len(v) for v in decoded["graph_dump"]["nodes"].values())
    edge_count = sum(len(v) for v in decoded["graph_dump"]["edges"].values())
    print(f"  ✅ {demo['filename']}  |  {node_count} nodes, {edge_count} edges  |  {os.path.getsize(path):,} bytes")


def main():
    print("SpeakNode Demo PNG Generator")
    print("=" * 40)
    for demo in DEMOS:
        create_demo_png(demo)
    print("=" * 40)
    print(f"Done! Files saved to: {os.path.abspath(OUTPUT_DIR)}")


if __name__ == "__main__":
    main()
