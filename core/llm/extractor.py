import logging
import re

from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from core.config import SpeakNodeConfig
from core.domain import AnalysisResult, Topic, Decision, Task, Person, Entity, Relation
from core.utils import truncate_text

logger = logging.getLogger(__name__)

class Extractor:
    def __init__(self, config: SpeakNodeConfig = None, model_name=None):
        cfg = config or SpeakNodeConfig()
        self.model_name = model_name or cfg.llm_model
        self.llm = ChatOllama(model=self.model_name, temperature=cfg.llm_temperature, format="json")
        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self._build_system_prompt()),
                ("user", "Transcript to analyze:\n{transcript}"),
            ]
        )
        self.chain = self.prompt | self.llm | JsonOutputParser()

    def _build_system_prompt(self):
        return """
You are an advanced transcript knowledge extractor. You extract structured information from any audio transcript — meetings, lectures, podcasts, interviews, or narration.

Output JSON only, with exactly these keys:
{{
  "topics": [{{"title": "...", "summary": "detailed summary of the topic with specific facts, names, dates, and numbers mentioned", "proposer": "Name or Unknown"}}],
  "decisions": [{{"description": "...", "related_topic": "Topic Title (Optional)"}}],
  "tasks": [{{"description": "...", "assignee": "Name", "status": "pending"}}],
  "entities": [{{"name": "...", "entity_type": "person|technology|organization|concept|event", "description": "brief description based on transcript context"}}],
  "relations": [{{"source": "Entity Name", "target": "Entity Name", "relation_type": "brief relationship label (e.g. developed, belongs_to, led_to, is_part_of, founded)"}}]
}}

Hard rules:
1. Use Korean for all extracted content (except proper nouns which may remain in original language).
2. Extract ALL important named entities mentioned in the transcript:
   - People (real or referenced): scientists, speakers, leaders, etc.
   - Technologies/Tools: programming languages, frameworks, models, algorithms
   - Organizations: companies, universities, research labs
   - Concepts: theories, methodologies, paradigms
   - Events: conferences, historical events, milestones with dates
3. For topics: write detailed summaries that capture specific facts, not vague descriptions. Include key numbers, dates, and names mentioned.
4. For entities: extract every distinct named entity. One entity per real-world thing.
5. For relations: capture how entities relate to each other as mentioned in the transcript.
6. For decisions: only include when there is an explicit commitment/agreement.
7. For tasks: only include when there is an explicit actionable assignment.
8. If the transcript is informational (lecture, podcast), decisions and tasks may be empty — but topics, entities, and relations should be rich.
9. Do NOT invent information not present in the transcript.
"""

    def _has_decision_signal(self, text: str) -> bool:
        pattern = r"(결정|합의|확정|승인|채택|결론|하기로\s*했|하기로\s*함|의결)"
        return re.search(pattern, text) is not None

    def _has_task_signal(self, text: str) -> bool:
        pattern = r"(할\s*일|액션\s*아이템|담당|요청|부탁|까지\s*(완료|제출|정리|작성|준비)|하겠습니다|진행하겠습니다|TODO|to do)"
        return re.search(pattern, text, flags=re.IGNORECASE) is not None

    # Maximum number of decisions/tasks to keep when no Korean signal pattern is found
    SAFETY_NET_MAX_WITHOUT_SIGNAL = 3

    def _normalize(self, raw: dict, transcript: str) -> AnalysisResult:
        data = raw if isinstance(raw, dict) else {}

        topics = []
        for item in data.get("topics", []):
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "")).strip()
            summary = str(item.get("summary", "")).strip()
            proposer = str(item.get("proposer", "Unknown")).strip()
            
            if not title:
                continue
            topics.append(Topic(title=title, summary=summary, proposer=proposer))

        decisions = []
        for item in data.get("decisions", []):
            if not isinstance(item, dict):
                continue
            description = str(item.get("description", "")).strip()
            related_topic = str(item.get("related_topic", "")).strip()

            if not description:
                continue
            decisions.append(Decision(description=description, related_topic=related_topic))

        tasks = []
        for item in data.get("tasks", []):
            if not isinstance(item, dict):
                continue
            description = str(item.get("description", "")).strip()
            assignee = str(item.get("assignee", "Unassigned")).strip() or "Unassigned"
            
            if not description:
                continue
            tasks.append(Task(description=description, assignee=assignee, status="pending"))

        # Entity extraction 
        entities = []
        entity_names_seen: set[str] = set()
        for item in data.get("entities", []):
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            if not name or name in entity_names_seen:
                continue
            entity_names_seen.add(name)
            entity_type = str(item.get("entity_type", "concept")).strip().lower()
            if entity_type not in ("person", "technology", "organization", "concept", "event"):
                entity_type = "concept"
            description = str(item.get("description", "")).strip()
            entities.append(Entity(name=name, entity_type=entity_type, description=description))

        # Relation extraction 
        relations = []
        for item in data.get("relations", []):
            if not isinstance(item, dict):
                continue
            source = str(item.get("source", "")).strip()
            target = str(item.get("target", "")).strip()
            relation_type = str(item.get("relation_type", "related_to")).strip()
            if not source or not target:
                continue
            # Only keep relations whose source and target exist in extracted entities
            if source in entity_names_seen and target in entity_names_seen:
                relations.append(Relation(source=source, target=target, relation_type=relation_type))

        # People extraction (from topics + tasks + entities) 
        people_set = set()
        for t in topics:
            if t.proposer and t.proposer not in ["Unknown", "None"]:
                people_set.add(t.proposer)
        for t in tasks:
            if t.assignee and t.assignee not in ["Unassigned", "None"]:
                people_set.add(t.assignee)
        for e in entities:
            if e.entity_type == "person" and e.name:
                people_set.add(e.name)
        
        people_list = [Person(name=p, role="Member") for p in people_set]

        # Relaxed safety net: keep LLM results but cap count when no signal found
        if not self._has_decision_signal(transcript) and decisions:
            logger.info(
                "No Korean decision signal found but LLM extracted %d decisions; capping at %d.",
                len(decisions), self.SAFETY_NET_MAX_WITHOUT_SIGNAL,
            )
            decisions = decisions[:self.SAFETY_NET_MAX_WITHOUT_SIGNAL]
        if not self._has_task_signal(transcript) and tasks:
            logger.info(
                "No Korean task signal found but LLM extracted %d tasks; capping at %d.",
                len(tasks), self.SAFETY_NET_MAX_WITHOUT_SIGNAL,
            )
            tasks = tasks[:self.SAFETY_NET_MAX_WITHOUT_SIGNAL]

        return AnalysisResult(
            topics=topics,
            decisions=decisions,
            tasks=tasks,
            people=people_list,
            entities=entities,
            relations=relations,
        )
        
    def extract(self, transcript: str) -> AnalysisResult:
        """Run LLM extraction and return a normalised AnalysisResult."""
        try:
            safe_transcript = truncate_text(transcript, max_tokens=27_000)
            raw = self.chain.invoke({"transcript": safe_transcript})
            return self._normalize(raw, transcript)
        except Exception:
            logger.exception("Extractor error (%s)", self.model_name)
            raise
