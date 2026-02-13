"""
SpeakNode Domain Models
========================
모든 모듈 간 데이터 교환에 사용되는 Pydantic 모델 정의.
dict 대신 타입이 강제되어 키 오타, 누락 등 런타임 에러를 방지합니다.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ================================================================
# 기본 엔티티 (Node)
# ================================================================

class Utterance(BaseModel):
    """STT 세그먼트 단위 발화"""
    id: str = ""
    text: str
    start: float
    end: float
    speaker: str = "Unknown"
    embedding: list[float] = Field(default_factory=list)


class Person(BaseModel):
    """회의 참여자"""
    name: str
    role: str = "Member"


class Topic(BaseModel):
    """회의 주제"""
    title: str
    summary: str = ""
    proposer: str = "Unknown"


class Task(BaseModel):
    """할 일"""
    description: str
    assignee: str = "Unassigned"
    deadline: str = "TBD"
    status: str = "pending"


class Decision(BaseModel):
    """결정 사항"""
    description: str
    related_topic: str = ""


class Meeting(BaseModel):
    """회의 단위"""
    id: str
    title: str
    date: str = ""
    source_file: str = ""


# ================================================================
# 복합 결과 (Pipeline 출력)
# ================================================================

class AnalysisResult(BaseModel):
    """Extractor가 반환하는 LLM 분석 결과"""
    topics: list[Topic] = Field(default_factory=list)
    decisions: list[Decision] = Field(default_factory=list)
    tasks: list[Task] = Field(default_factory=list)
    people: list[Person] = Field(default_factory=list)

    def to_dict(self) -> dict:
        """기존 dict 기반 코드와의 역호환용"""
        return self.model_dump()


class MeetingSummary(BaseModel):
    """회의 요약 결과"""
    meeting_id: str
    title: str = ""
    date: str = ""
    source_file: str = ""
    topics: list[Topic] = Field(default_factory=list)
