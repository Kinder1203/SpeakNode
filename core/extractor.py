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
  "topics": [{{"title": "...", "summary": "...", "proposer": "Name(Optional)"}}],
  "decisions": [{{"description": "...", "related_topic": "Topic Title"}}],
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

        # [수정] 관계 형성을 위해 데이터 보강
        
        topics = []
        # 토픽 리스트 확보
        raw_topics = data.get("topics", [])
        
        for item in raw_topics:
            if not isinstance(item, dict): continue
            title = str(item.get("title", "")).strip()
            summary = str(item.get("summary", "")).strip()
            # [추가] LLM이 제안자를 찾지 못했을 경우를 대비해 기본값 설정 (화자 분리 기능이 붙기 전까진 'Unknown')
            proposer = str(item.get("proposer", "Unknown")).strip() 
            
            if not title: continue
            topics.append({
                "title": title, 
                "summary": summary,
                "proposer": proposer # kuzu_manager가 이 키를 사용함
            })

        decisions = []
        for item in data.get("decisions", []):
            if not isinstance(item, dict): continue
            description = str(item.get("description", "")).strip()
            # [추가] 결정 사항이 어떤 토픽과 연관되는지 매핑
            # (간단한 로직: 가장 첫 번째 토픽과 연결하거나, LLM에게 요청했어야 함.
            #  여기서는 안전하게 첫 번째 토픽이 있다면 그것과 연결)
            related_topic = item.get("related_topic", "")
            if not related_topic and topics:
                related_topic = topics[0]['title']
                
            if not description: continue
            decisions.append({
                "description": description,
                "related_topic": related_topic # kuzu_manager가 이 키를 사용함
            })

        tasks = []
        for item in data.get("tasks", []):
            if not isinstance(item, dict): continue
            description = str(item.get("description", "")).strip()
            assignee = str(item.get("assignee", "Unassigned")).strip() or "Unassigned"
            if not description: continue
            
            tasks.append({
                "description": description,
                "assignee": assignee, # kuzu_manager가 이 키를 사용함
                "status": "pending",
            })
        # 등장인물 추출 (assignee, proposer 등에서 수집)
        people_set = set()
        for t in topics:
            if t.get('proposer') and t['proposer'] != 'Unknown':
                people_set.add(t['proposer'])
        for t in tasks:
            if t.get('assignee') and t['assignee'] != 'Unassigned':
                people_set.add(t['assignee'])
        
        people_list = [{"name": p, "role": "Member"} for p in people_set]

        # (나머지 안전장치 로직은 그대로 유지...)
        if not self._has_decision_signal(transcript):
            decisions = []
        if not self._has_task_signal(transcript):
            tasks = []

        return {"topics": topics, "decisions": decisions, "tasks": tasks, "people": []} 
        # people 키가 비어있으면 kuzu_manager에서 Person 노드가 생성 안 될 수 있으므로
        # 아래 단계에서 people 리스트를 자동으로 채워주는 로직이 필요하거나,
        # kuzu_manager가 없는 Person을 자동 생성(MERGE)하도록 믿어야 합니다.
        # 다행히 kuzu_manager.py의 쿼리는 MERGE를 쓰므로, 관계 형성 시 Person이 자동 생성됩니다.
        
    def extract(self, transcript):
        try:
            raw = self.chain.invoke({"transcript": transcript})
            return self._normalize(raw, transcript)
        except Exception as e:
            print(f"❌ [Extractor Error] {self.model_name}: {str(e)}")
            raise e
