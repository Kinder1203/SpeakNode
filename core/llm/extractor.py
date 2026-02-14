import logging
import re

from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from core.config import SpeakNodeConfig
from core.domain import AnalysisResult, Topic, Decision, Task, Person
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
You are a strict meeting transcript extractor for a conservative MVP.

Output JSON only, with exactly these keys:
{{
  "topics": [{{"title": "...", "summary": "...", "proposer": "Name (Optional)"}}],
  "decisions": [{{"description": "...", "related_topic": "Topic Title (Optional)"}}],
  "tasks": [{{"description": "...", "assignee": "Name", "status": "pending"}}]
}}

Hard rules:
1. Use Korean for all extracted content.
2. Do not infer or invent decisions/tasks.
3. If the transcript is informational narration and has no explicit decision or action assignment, set:
   - "decisions": []
   - "tasks": []
4. Only include a decision when there is an explicit commitment/agreement expression.
5. Only include a task when there is an explicit actionable assignment/request.
6. If unsure, return empty arrays for that field.
"""

    def _has_decision_signal(self, text: str) -> bool:
        pattern = r"(결정|합의|확정|승인|채택|결론|하기로\s*했|하기로\s*함|의결)"
        return re.search(pattern, text) is not None

    def _has_task_signal(self, text: str) -> bool:
        pattern = r"(할\s*일|액션\s*아이템|담당|요청|부탁|까지\s*(완료|제출|정리|작성|준비)|하겠습니다|진행하겠습니다|TODO|to do)"
        return re.search(pattern, text, flags=re.IGNORECASE) is not None

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
            
            if not related_topic and topics:
                related_topic = topics[0].title

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

        people_set = set()
        for t in topics:
            if t.proposer and t.proposer not in ["Unknown", "None"]:
                people_set.add(t.proposer)
        for t in tasks:
            if t.assignee and t.assignee not in ["Unassigned", "None"]:
                people_set.add(t.assignee)
        
        people_list = [Person(name=p, role="Member") for p in people_set]

        # Conservative safety net: transcript 신호가 없으면 결과를 비웁니다.
        if not self._has_decision_signal(transcript):
            decisions = []
        if not self._has_task_signal(transcript):
            tasks = []

        return AnalysisResult(
            topics=topics,
            decisions=decisions,
            tasks=tasks,
            people=people_list,
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
