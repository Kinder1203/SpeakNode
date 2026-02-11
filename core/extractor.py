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

    def _normalize(self, raw: dict, transcript: str) -> dict:
        data = raw if isinstance(raw, dict) else {}

        # 1. Topics 처리 (proposer 추가)
        topics = []
        for item in data.get("topics", []):
            if not isinstance(item, dict): continue
            title = str(item.get("title", "")).strip()
            summary = str(item.get("summary", "")).strip()
            proposer = str(item.get("proposer", "Unknown")).strip()  # [New]
            
            if not title: continue
            topics.append({
                "title": title, 
                "summary": summary,
                "proposer": proposer
            })

        # 2. Decisions 처리 (related_topic 추가)
        decisions = []
        for item in data.get("decisions", []):
            if not isinstance(item, dict): continue
            description = str(item.get("description", "")).strip()
            related_topic = str(item.get("related_topic", "")).strip() # [New]
            
            # 관련 토픽이 비어있다면 첫 번째 토픽과 연결 (Safe fallback)
            if not related_topic and topics:
                related_topic = topics[0]['title']

            if not description: continue
            decisions.append({
                "description": description,
                "related_topic": related_topic
            })

        # 3. Tasks 처리
        tasks = []
        for item in data.get("tasks", []):
            if not isinstance(item, dict): continue
            description = str(item.get("description", "")).strip()
            assignee = str(item.get("assignee", "Unassigned")).strip() or "Unassigned"
            
            if not description: continue
            tasks.append({
                "description": description,
                "assignee": assignee,
                "status": "pending",
            })

        # 4. People 자동 생성 (모든 등장인물 수집) [New]
        people_set = set()
        # 토픽 제안자 수집
        for t in topics:
            if t['proposer'] and t['proposer'] not in ["Unknown", "None"]:
                people_set.add(t['proposer'])
        # 업무 담당자 수집
        for t in tasks:
            if t['assignee'] and t['assignee'] not in ["Unassigned", "None"]:
                people_set.add(t['assignee'])
        
        people_list = [{"name": p, "role": "Member"} for p in people_set]

        # Conservative safety-net
        if not self._has_decision_signal(transcript):
            decisions = []
        if not self._has_task_signal(transcript):
            tasks = []

        # 최종 반환 시 people 포함
        return {
            "topics": topics, 
            "decisions": decisions, 
            "tasks": tasks,
            "people": people_list
        }
        
    def extract(self, transcript):
        try:
            raw = self.chain.invoke({"transcript": transcript})
            return self._normalize(raw, transcript)
        except Exception as e:
            print(f"❌ [Extractor Error] {self.model_name}: {str(e)}")
            raise e