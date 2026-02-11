import re
import json
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

class Extractor:
    def __init__(self, model_name="deepseek-r1:14b", base_url="http://localhost:11434"):
        """
        LLM 추출기 초기화
        :param model_name: 사용할 Ollama 모델명 (예: deepseek-r1:14b, llama3)
        :param base_url: Ollama 서버 주소 (RunPod 내부이므로 localhost)
        """
        print(f"🧠 [Extractor] Initializing with model: {model_name}...")
        
        # 1. LLM 설정 (temperature=0으로 설정하여 일관된 결과 유도)
        self.llm = ChatOllama(
            model=model_name,
            base_url=base_url,
            temperature=0.1,
            format="json"  # JSON 모드 강제
        )
        
        # 2. 프롬프트 설계 (그래프 DB 스키마에 맞춰 추출 지시)
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """
            당신은 회의록 분석 전문가입니다. 회의 내용을 분석하여 아래 JSON 형식으로 정보를 추출하세요.
            
            [추출 지침]
            1. people: 회의에 참여한 모든 인물과 그들의 역할을 추출하세요.
            2. topics: 논의된 주제를 추출하되, 해당 주제를 누가 처음 꺼냈는지(proposer) 반드시 포함하세요.
            3. decisions/tasks: 결정사항과 할 일을 추출하고, 담당자(assignee)를 연결하세요.
            
            [JSON 형식]
            {{
                "people": [{{"name": "이름", "role": "직책"}}],
                "topics": [{{"title": "주제명", "summary": "요약", "proposer": "이름"}}],
                "decisions": [{{"description": "결정사항", "proposer": "이름"}}],
                "tasks": [{{"description": "할 일", "assignee": "이름", "deadline": "날짜"}}]
            }}
            """),
            ("user", "{text}")
        ])
        
        # 3. 체인 생성
        self.chain = self.prompt | self.llm

    def _clean_think_tags(self, text):
        """DeepSeek 모델의 <think> 태그 제거"""
        return re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()

    def extract(self, transcription_text):
        """
        텍스트에서 구조화된 정보 추출
        """
        print("🧠 [Extractor] Analyzing text...")
        
        try:
            # LLM 호출
            response = self.chain.invoke({"text": transcription_text})
            
            # LangChain 객체에서 실제 내용(content)만 추출
            content = response.content if hasattr(response, 'content') else str(response)
            
            # <think> 태그 제거 (DeepSeek-R1 사용 시 필수)
            clean_content = self._clean_think_tags(content)
            
            # JSON 파싱 시도
            try:
                data = json.loads(clean_content)
                print(f"✅ [Extractor] Extraction successful: {len(data.get('topics', []))} topics found.")
                return data
            except json.JSONDecodeError:
                # JSON 형식이 깨져서 올 경우, 뒷수습 시도 (단순 텍스트 반환)
                print("⚠️ [Extractor] JSON parsing failed. Returning raw text.")
                return {"raw_summary": clean_content}
                
        except Exception as e:
            print(f"❌ [Extractor] Error: {e}")
            return {}

# ==========================================
# 🧪 테스트 실행 코드
# ==========================================
if __name__ == "__main__":
    # 테스트용 가짜 회의록
    test_text = """
    김철수: 이번 프로젝트 서버 비용이 너무 많이 나옵니다.
    이영희: 그럼 스팟 인스턴스를 도입해서 비용을 줄입시다.
    김철수: 좋아요. 제가 다음 주 금요일까지 비용 분석 보고서를 작성해 올게요.
    박민수: 알겠습니다. 스팟 인스턴스 도입은 바로 진행하는 걸로 결정하죠.
    """
    
    # 모델명은 RunPod에 설치한 것과 일치해야 함 (예: deepseek-r1:14b 또는 llama3)
    extractor = Extractor(model_name="deepseek-r1:14b") # 설치한 모델명 확인!
    
    result = extractor.extract(test_text)
    print("\n--- [Extraction Result] ---")
    print(json.dumps(result, indent=2, ensure_ascii=False))