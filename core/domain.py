"""Pydantic domain models shared across all modules."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Utterance(BaseModel):
    id: str = ""
    text: str
    start: float
    end: float
    speaker: str = "Unknown"
    embedding: list[float] = Field(default_factory=list)


class Person(BaseModel):
    name: str
    role: str = "Member"


class Topic(BaseModel):
    title: str
    summary: str = ""
    proposer: str = "Unknown"


class Task(BaseModel):
    description: str
    assignee: str = "Unassigned"
    deadline: str = "TBD"
    status: str = "pending"


class Decision(BaseModel):
    description: str
    related_topic: str = ""


class Meeting(BaseModel):
    id: str
    title: str
    date: str = ""
    source_file: str = ""


class AnalysisResult(BaseModel):
    topics: list[Topic] = Field(default_factory=list)
    decisions: list[Decision] = Field(default_factory=list)
    tasks: list[Task] = Field(default_factory=list)
    people: list[Person] = Field(default_factory=list)

    def to_dict(self) -> dict:
        return self.model_dump()


class MeetingSummary(BaseModel):
    meeting_id: str
    title: str = ""
    date: str = ""
    source_file: str = ""
    topics: list[Topic] = Field(default_factory=list)
