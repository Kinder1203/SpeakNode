import re

from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

class Extractor:
    def __init__(self, model_name="qwen2.5:14b"):
        self.model_name = model_name
        self.llm = ChatOllama(model=model_name, temperature=0.0, format="json")
        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self._build_system_prompt()),
                ("user", "Transcript to analyze:\n{transcript}"),
            ]
        )
        self.chain = self.prompt | self.llm | JsonOutputParser()

    def _build_system_prompt(self):
        # Current phase is a conservative extractor, not an autonomous agent planner.
        return """
You are a strict meeting transcript extractor for a conservative MVP.

Output JSON only, with exactly these keys:
{{
  "topics": [{{"title": "...", "summary": "..."}}],
  "decisions": [{{"description": "..."}}],
  "tasks": [{{"description": "...", "assignee": "...", "status": "pending"}}]
}}

Hard rules:
1. Use Korean for all extracted content.
2. Do not infer or invent decisions/tasks.
3. If the transcript is informational narration (explanation/news/script) and has no explicit decision or action assignment, set:
   - "decisions": []
   - "tasks": []
4. Only include a decision when there is an explicit commitment/agreement expression.
5. Only include a task when there is an explicit actionable assignment/request.
6. If unsure, return empty arrays for that field.
"""

    def _has_decision_signal(self, text: str) -> bool:
        # Explicit agreement/decision markers only.
        pattern = r"(결정|합의|확정|승인|채택|결론|하기로\s*했|하기로\s*함|의결)"
        return re.search(pattern, text) is not None

    def _has_task_signal(self, text: str) -> bool:
        # Explicit assignment/request markers only.
        pattern = r"(할\s*일|액션\s*아이템|담당|요청|부탁|까지\s*(완료|제출|정리|작성|준비)|하겠습니다|진행하겠습니다|TODO|to do)"
        return re.search(pattern, text, flags=re.IGNORECASE) is not None

    def _normalize(self, raw: dict, transcript: str) -> dict:
        data = raw if isinstance(raw, dict) else {}

        topics = []
        for item in data.get("topics", []):
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "")).strip()
            summary = str(item.get("summary", "")).strip()
            if not title:
                continue
            topics.append({"title": title, "summary": summary})

        decisions = []
        for item in data.get("decisions", []):
            if not isinstance(item, dict):
                continue
            description = str(item.get("description", "")).strip()
            if not description:
                continue
            decisions.append({"description": description})

        tasks = []
        for item in data.get("tasks", []):
            if not isinstance(item, dict):
                continue
            description = str(item.get("description", "")).strip()
            assignee = str(item.get("assignee", "Unassigned")).strip() or "Unassigned"
            if not description:
                continue
            tasks.append(
                {
                    "description": description,
                    "assignee": assignee,
                    "status": "pending",
                }
            )

        # Conservative safety-net:
        # If transcript has no explicit cue, force empty arrays for decisions/tasks.
        if not self._has_decision_signal(transcript):
            decisions = []
        if not self._has_task_signal(transcript):
            tasks = []

        return {"topics": topics, "decisions": decisions, "tasks": tasks}
        
    def extract(self, transcript):
        try:
            raw = self.chain.invoke({"transcript": transcript})
            return self._normalize(raw, transcript)
        except Exception as e:
            print(f"❌ [Extractor Error] {self.model_name}: {str(e)}")
            raise e
