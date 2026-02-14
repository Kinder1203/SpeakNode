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


class Entity(BaseModel):
    """General knowledge entity extracted from audio content."""
    name: str
    entity_type: str = "concept"   # person | technology | organization | concept | event
    description: str = ""


class Relation(BaseModel):
    """Relationship between two extracted entities."""
    source: str
    target: str
    relation_type: str = "related_to"


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
    entities: list[Entity] = Field(default_factory=list)
    relations: list[Relation] = Field(default_factory=list)

    def to_dict(self) -> dict:
        return self.model_dump()


class MeetingSummary(BaseModel):
    meeting_id: str
    title: str = ""
    date: str = ""
    source_file: str = ""
    topics: list[Topic] = Field(default_factory=list)
