from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

class Extractor:
    def __init__(self, model_name="qwen2.5:14b"):
        self.model_name = model_name
        self.llm = ChatOllama(model=model_name, temperature=0.0, format="json")
        
    def extract(self, transcript):
        # 변수 중복을 피하기 위해 템플릿 구조 최적화
        system_prompt = """
        You are a professional meeting analyst. Extract information into a JSON object.
        Required JSON keys: "topics", "decisions", "tasks".
        
        Rules:
        1. "topics": list of {{"title": "...", "summary": "..."}}
        2. "decisions": list of {{"description": "..."}}
        3. "tasks": list of {{"description": "...", "assignee": "...", "status": "pending"}}
        4. Use Korean for all content.
        5. Respond ONLY with valid JSON.
        """
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", "Transcript to analyze: {transcript}")
        ])
        
        chain = prompt | self.llm | JsonOutputParser()
        
        try:
            return chain.invoke({"transcript": transcript})
        except Exception as e:
            # [Fix] 에러를 숨기지 않고 상위로 던짐
            print(f"❌ [Extractor Error] {self.model_name}: {str(e)}")
            raise e