"""
SpeakNode LangGraph Agent (Phase 4)
=====================================
회의 DB를 바탕으로 질의응답, 이메일 초안 작성, 데이터 검색 등을 수행하는
지능형 AI 에이전트.

Architecture:
    User Query → Router (LLM) → Tool Selection → Tool Execution → Synthesizer → Response

Tools:
    1. search_by_meaning   - Vector RAG: 의미 기반 유사 발언 검색
    2. search_by_structure  - Graph RAG: 구조적 관계 탐색
    3. hybrid_search        - 결합 검색 (Vector + Graph)
    4. get_meeting_summary  - 특정 회의 전체 요약
    5. draft_email          - 회의 결과 기반 이메일 초안 생성
"""

from __future__ import annotations

import json
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, END

from core.config import SpeakNodeConfig
from core.kuzu_manager import KuzuManager
from core.hybrid_rag import HybridRAG


# ================================================================
# 1. Agent State 정의
# ================================================================

class AgentState(TypedDict):
    """Agent가 각 노드 사이에서 주고받는 상태"""
    messages: list           # 대화 히스토리 (LangChain Message 객체)
    context: str             # RAG 검색 결과 컨텍스트
    tool_name: str           # 선택된 Tool 이름
    tool_args: dict          # Tool 인자
    tool_result: str         # Tool 실행 결과
    final_answer: str        # 최종 응답


# ================================================================
# 2. Tool 함수 정의
# ================================================================

TOOL_DESCRIPTIONS = """
Available tools:
1. search_by_meaning(query: str) - 의미 기반으로 관련 발언을 검색합니다. 특정 키워드나 주제에 대한 발언을 찾을 때 사용.
2. search_by_structure(entity_type: str, keyword: str) - 구조적 관계를 탐색합니다. entity_type은 "topic", "task", "decision", "person", "meeting" 중 하나. keyword는 검색 키워드 (선택사항).
3. hybrid_search(query: str) - 의미 + 구조 결합 검색. 복합적인 질문에 사용.
4. get_meeting_summary(meeting_id: str) - 특정 회의의 전체 요약. meeting_id가 없으면 빈 문자열.
5. draft_email(recipient: str, subject: str) - 회의 결과를 바탕으로 이메일 초안을 작성합니다.
6. direct_answer - DB 검색이 필요 없는 일반적인 질문에 직접 답변합니다.
"""


def _execute_tool(
    tool_name: str,
    tool_args: dict,
    db: KuzuManager,
    rag: HybridRAG,
) -> str:
    """Tool 이름과 인자를 받아 실행하고 결과 문자열을 반환합니다."""
    try:
        if tool_name == "search_by_meaning":
            query = tool_args.get("query", "")
            results = rag.vector_search(query, db, top_k=5)
            if not results:
                return "관련 발언을 찾지 못했습니다."
            lines = []
            for r in results:
                lines.append(f"[{r.get('start', 0):.1f}s] {r['text']} (유사도: {r.get('score', 0):.3f})")
            return "\n".join(lines)

        elif tool_name == "search_by_structure":
            entity_type = tool_args.get("entity_type", "topic")
            keyword = tool_args.get("keyword", "")

            if entity_type == "topic":
                items = rag.graph_search_topics(db, keyword=keyword)
                if not items:
                    return "등록된 주제가 없습니다."
                return "\n".join(f"- {t['title']}: {t.get('summary', '')}" for t in items)

            elif entity_type == "task":
                items = rag.graph_search_tasks(db, person_name=keyword)
                if not items:
                    return "등록된 할 일이 없습니다."
                return "\n".join(
                    f"- {t['description']} (담당: {t.get('assignee', '미지정')}, 상태: {t.get('status', '?')})"
                    for t in items
                )

            elif entity_type == "decision":
                items = rag.graph_search_decisions(db, topic_title=keyword)
                if not items:
                    return "등록된 결정 사항이 없습니다."
                return "\n".join(f"- {d['description']}" for d in items)

            elif entity_type == "person":
                items = rag.graph_search_people(db)
                if not items:
                    return "등록된 참여자가 없습니다."
                return "\n".join(f"- {p['name']} ({p.get('role', 'Member')})" for p in items)

            elif entity_type == "meeting":
                items = rag.graph_search_meetings(db)
                if not items:
                    return "등록된 회의가 없습니다."
                return "\n".join(f"- [{m['id']}] {m['title']} ({m.get('date', '')})" for m in items)

            else:
                return f"알 수 없는 entity_type: {entity_type}"

        elif tool_name == "hybrid_search":
            query = tool_args.get("query", "")
            result = rag.hybrid_search(query, db, top_k=5)
            return result.get("merged_context", "(결과 없음)")

        elif tool_name == "get_meeting_summary":
            meeting_id = tool_args.get("meeting_id", "")
            if not meeting_id:
                # meeting_id가 없으면 전체 회의 목록 반환
                meetings = rag.graph_search_meetings(db)
                if not meetings:
                    return "등록된 회의가 없습니다."
                return "회의 목록:\n" + "\n".join(
                    f"- [{m['id']}] {m['title']} ({m.get('date', '')})" for m in meetings
                )
            summary = db.get_meeting_summary(meeting_id)
            if not summary:
                return f"회의 '{meeting_id}'를 찾을 수 없습니다."
            return json.dumps(summary, ensure_ascii=False, indent=2)

        elif tool_name == "draft_email":
            # 이메일 초안 생성을 위한 컨텍스트 수집
            recipient = tool_args.get("recipient", "")
            subject = tool_args.get("subject", "회의 결과 공유")
            
            # DB에서 전체 정보 수집
            search_result = rag.hybrid_search(subject, db, top_k=3)
            context = search_result.get("merged_context", "")
            
            return json.dumps({
                "type": "email_draft_request",
                "recipient": recipient,
                "subject": subject,
                "context": context,
            }, ensure_ascii=False)

        elif tool_name == "direct_answer":
            return ""  # 직접 답변 — Tool 결과 없음

        else:
            return f"알 수 없는 도구: {tool_name}"

    except Exception as e:
        return f"도구 실행 오류 ({tool_name}): {e}"


# ================================================================
# 3. Graph Nodes (LangGraph 노드 함수들)
# ================================================================

def router_node(state: AgentState, llm: ChatOllama) -> AgentState:
    """
    Router: 사용자 질문을 분석하여 적절한 Tool을 선택합니다.
    LLM이 JSON으로 {tool_name, tool_args}를 반환합니다.
    """
    user_messages = state["messages"]
    
    router_prompt = f"""You are a tool router for a meeting analysis system.
Analyze the user's question and select the most appropriate tool.

{TOOL_DESCRIPTIONS}

Respond with JSON only:
{{"tool_name": "<tool_name>", "tool_args": {{<args>}}}}

Rules:
- For questions about specific content/what was said: use "search_by_meaning"
- For questions about people, topics, tasks, decisions: use "search_by_structure"
- For complex questions combining multiple aspects: use "hybrid_search"
- For meeting overview/summary: use "get_meeting_summary"
- For email drafting requests: use "draft_email"
- For general greetings or questions not related to meeting data: use "direct_answer"
"""

    messages = [SystemMessage(content=router_prompt)] + user_messages
    
    response = llm.invoke(messages)
    
    try:
        # JSON 파싱
        content = response.content.strip()
        parsed = json.loads(content)
        state["tool_name"] = parsed.get("tool_name", "direct_answer")
        state["tool_args"] = parsed.get("tool_args", {})
    except (json.JSONDecodeError, AttributeError):
        # 파싱 실패 → hybrid_search로 fallback
        state["tool_name"] = "hybrid_search"
        last_human = ""
        for msg in reversed(user_messages):
            if isinstance(msg, HumanMessage):
                last_human = msg.content
                break
        state["tool_args"] = {"query": last_human}

    return state


def tool_executor_node(
    state: AgentState, db: KuzuManager, rag: HybridRAG
) -> AgentState:
    """Tool을 실행하고 결과를 state에 저장합니다."""
    tool_name = state.get("tool_name", "direct_answer")
    tool_args = state.get("tool_args", {})

    result = _execute_tool(tool_name, tool_args, db, rag)
    state["tool_result"] = result
    state["context"] = result
    return state


def synthesizer_node(state: AgentState, llm: ChatOllama) -> AgentState:
    """
    Synthesizer: Tool 결과를 바탕으로 자연어 응답을 생성합니다.
    """
    tool_name = state.get("tool_name", "")
    tool_result = state.get("tool_result", "")

    if tool_name == "draft_email":
        # 이메일 초안은 별도 프롬프트
        try:
            email_data = json.loads(tool_result)
            synth_prompt = f"""You are a professional email writer.
Based on the meeting data below, draft a business email in Korean.

수신자: {email_data.get('recipient', '팀원')}
제목: {email_data.get('subject', '회의 결과')}

회의 데이터:
{email_data.get('context', '(데이터 없음)')}

Write a clear, professional email in Korean. Include:
- 인사말
- 회의 주요 내용 요약
- 결정 사항
- 할 일 (담당자 포함)
- 마무리 인사
"""
        except (json.JSONDecodeError, TypeError):
            synth_prompt = f"이메일 초안을 작성해주세요. 데이터: {tool_result}"

        messages = [SystemMessage(content=synth_prompt)]
        response = llm.invoke(messages)
        state["final_answer"] = response.content

    elif tool_name == "direct_answer":
        # Tool 없이 직접 답변
        synth_prompt = """You are a helpful meeting analysis assistant called SpeakNode.
Answer the user's question naturally in Korean.
If the question is about meeting data, let them know they can ask specific questions about topics, tasks, decisions, or people."""
        messages = [SystemMessage(content=synth_prompt)] + state["messages"]
        response = llm.invoke(messages)
        state["final_answer"] = response.content

    else:
        # 일반 검색 결과 기반 응답 생성
        synth_prompt = f"""You are a meeting analysis assistant called SpeakNode.
Based on the search results below, provide a clear and helpful answer to the user's question in Korean.
Cite specific data from the results. If results are empty, let the user know.

검색 결과:
{tool_result}
"""
        messages = [SystemMessage(content=synth_prompt)] + state["messages"]
        response = llm.invoke(messages)
        state["final_answer"] = response.content

    # 응답을 messages에 추가
    state["messages"] = state["messages"] + [AIMessage(content=state["final_answer"])]
    return state


# ================================================================
# 4. SpeakNodeAgent — 외부에서 사용하는 진입점
# ================================================================

class SpeakNodeAgent:
    """
    LangGraph 기반 SpeakNode AI Agent.
    
    사용법:
        agent = SpeakNodeAgent(db_path="/path/to/db.kuzu")
        response = agent.query("이번 회의에서 결정된 사항은?")
    """

    def __init__(self, db_path: str, config: SpeakNodeConfig = None):
        self.config = config or SpeakNodeConfig()
        self.db_path = db_path
        
        # LLM 초기화
        self.llm = ChatOllama(
            model=self.config.agent_model,
            temperature=self.config.llm_temperature,
            format="json",  # Router용 JSON 모드
        )
        self.llm_free = ChatOllama(
            model=self.config.agent_model,
            temperature=0.3,  # Synthesizer는 약간의 창의성 허용
        )
        
        # RAG 엔진
        self.rag = HybridRAG(config=self.config)
        
        # LangGraph 빌드
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """LangGraph StateGraph를 구성합니다."""

        workflow = StateGraph(AgentState)

        # 노드 등록 (클로저로 의존성 주입)
        workflow.add_node("router", lambda state: router_node(state, self.llm))
        workflow.add_node("tool_executor", lambda state: self._tool_executor(state))
        workflow.add_node("synthesizer", lambda state: synthesizer_node(state, self.llm_free))

        # 엣지 연결: router → tool_executor → synthesizer → END
        workflow.set_entry_point("router")
        workflow.add_edge("router", "tool_executor")
        workflow.add_edge("tool_executor", "synthesizer")
        workflow.add_edge("synthesizer", END)

        return workflow.compile()

    def _tool_executor(self, state: AgentState) -> AgentState:
        """Tool 실행 노드 (DB connection을 여기서 관리)"""
        with KuzuManager(db_path=self.db_path, config=self.config) as db:
            return tool_executor_node(state, db, self.rag)

    def query(self, user_question: str, chat_history: list = None) -> str:
        """
        사용자 질문을 받아 Agent가 처리한 최종 응답을 반환합니다.
        
        Args:
            user_question: 사용자 질문 문자열
            chat_history: 이전 대화 히스토리 (Optional, list[Message])
        
        Returns:
            str: Agent의 최종 응답
        """
        messages = chat_history or []
        messages.append(HumanMessage(content=user_question))

        initial_state: AgentState = {
            "messages": messages,
            "context": "",
            "tool_name": "",
            "tool_args": {},
            "tool_result": "",
            "final_answer": "",
        }

        try:
            final_state = self.graph.invoke(initial_state)
            return final_state.get("final_answer", "응답을 생성할 수 없습니다.")
        except Exception as e:
            print(f"❌ [Agent] 처리 중 오류: {e}")
            return f"죄송합니다, 처리 중 오류가 발생했습니다: {e}"

    def get_chat_history_from_state(self, final_state: dict) -> list:
        """최종 상태에서 대화 히스토리를 추출합니다 (다음 쿼리에 전달 가능)."""
        return final_state.get("messages", [])
