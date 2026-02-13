"""
SpeakNode LangGraph Agent (Phase 4 — Refactored)
==================================================
회의 DB를 바탕으로 질의응답, 이메일 초안 작성, 데이터 검색 등을 수행하는
지능형 AI 에이전트.

Architecture:
    User Query → Router (LLM) → ToolRegistry.execute() → Synthesizer → Response

Tool 추가 방법:
    core/tools/ 내 파일에서 @registry.register("name", "desc") 데코레이터 사용.
    agent.py 수정 불필요.
"""

from __future__ import annotations

import json
import logging
import threading
from typing import TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, END

from core.config import SpeakNodeConfig
from core.db.kuzu_manager import KuzuManager
from core.agent.hybrid_rag import HybridRAG

logger = logging.getLogger(__name__)

# --- Tool 자동 수집 --------------------------------
# tools 패키지의 default_registry에 모든 도구가 등록됨
from core.agent.tools import default_registry as tool_registry
import core.agent.tools.search_tools    # noqa: F401  — 등록 트리거
import core.agent.tools.cypher_tools    # noqa: F401
import core.agent.tools.meeting_tools   # noqa: F401
import core.agent.tools.email_tools     # noqa: F401
import core.agent.tools.general_tools   # noqa: F401


# ================================================================
# 1. Agent State
# ================================================================

class AgentState(TypedDict):
    messages: list
    context: str
    tool_name: str
    tool_args: dict
    tool_result: str
    final_answer: str


# ================================================================
# 2. Graph Nodes
# ================================================================

def router_node(state: AgentState, llm: ChatOllama) -> AgentState:
    """사용자 질문을 분석하여 적절한 Tool을 선택합니다."""
    user_messages = state["messages"]

    # Tool 설명을 Registry에서 자동 생성
    tool_descriptions = tool_registry.get_descriptions()

    router_prompt = f"""You are a tool router for a meeting analysis system.
Analyze the user's question and select the most appropriate tool.

{tool_descriptions}

Respond with JSON only:
{{"tool_name": "<tool_name>", "tool_args": {{<args>}}}}

Rules:
- For questions about specific content/what was said: use "search_by_meaning"
- For questions about people, topics, tasks, decisions: use "search_by_structure"
  - include tool_args.entity_type in ["topic","task","decision","person","meeting"]
  - include tool_args.keyword when relevant
- For complex questions combining multiple aspects: use "hybrid_search"
  - include tool_args.query as the full user question
- For conditional/structured graph questions requiring explicit filters or custom joins: use "search_by_cypher"
  - include tool_args.query as the full user question
  - include tool_args.limit when user requests count/limit
- For meeting overview/summary: use "get_meeting_summary"
- For email drafting requests: use "draft_email"
- For general greetings or questions not related to meeting data: use "direct_answer"
"""

    messages = [SystemMessage(content=router_prompt)] + user_messages
    response = llm.invoke(messages)

    try:
        parsed = json.loads(response.content.strip())
        state["tool_name"] = parsed.get("tool_name", "direct_answer")
        tool_args = parsed.get("tool_args", {})
        state["tool_args"] = tool_args if isinstance(tool_args, dict) else {}
    except (json.JSONDecodeError, AttributeError):
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
    """ToolRegistry를 통해 선택된 Tool을 실행합니다."""
    result = tool_registry.execute(
        state.get("tool_name", "direct_answer"),
        state.get("tool_args", {}),
        db,
        rag,
    )
    state["tool_result"] = result
    state["context"] = result
    return state


def synthesizer_node(state: AgentState, llm: ChatOllama) -> AgentState:
    """Tool 결과를 바탕으로 자연어 응답을 생성합니다."""
    tool_name = state.get("tool_name", "")
    tool_result = state.get("tool_result", "")

    if tool_name == "draft_email":
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

    elif tool_name == "direct_answer":
        synth_prompt = """You are a helpful meeting analysis assistant called SpeakNode.
Answer the user's question naturally in Korean.
If the question is about meeting data, let them know they can ask specific questions about topics, tasks, decisions, or people."""
        messages = [SystemMessage(content=synth_prompt)] + state["messages"]

    else:
        synth_prompt = f"""You are a meeting analysis assistant called SpeakNode.
Based on the search results below, provide a clear and helpful answer to the user's question in Korean.
Cite specific data from the results. If results are empty, let the user know.

검색 결과:
{tool_result}
"""
        messages = [SystemMessage(content=synth_prompt)] + state["messages"]

    response = llm.invoke(messages)
    state["final_answer"] = response.content
    state["messages"] = state["messages"] + [AIMessage(content=state["final_answer"])]
    return state


# ================================================================
# 3. SpeakNodeAgent — 외부 진입점
# ================================================================

class SpeakNodeAgent:
    """
    LangGraph 기반 SpeakNode AI Agent.

    사용법:
        agent = SpeakNodeAgent(db_path="/path/to/db.kuzu")
        response = agent.query("이번 회의에서 결정된 사항은?")
    """

    def __init__(self, db_path: str, config: SpeakNodeConfig | None = None):
        self.config = config or SpeakNodeConfig()
        self.db_path = db_path

        self.llm = ChatOllama(
            model=self.config.agent_model,
            temperature=self.config.llm_temperature,
            format="json",
        )
        self.llm_free = ChatOllama(
            model=self.config.agent_model,
            temperature=0.3,
        )

        self.rag = HybridRAG(config=self.config)
        self._local = threading.local()
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(AgentState)

        workflow.add_node("router", lambda s: router_node(s, self.llm))
        workflow.add_node("tool_executor", lambda s: self._tool_executor(s))
        workflow.add_node("synthesizer", lambda s: synthesizer_node(s, self.llm_free))

        workflow.set_entry_point("router")
        workflow.add_edge("router", "tool_executor")
        workflow.add_edge("tool_executor", "synthesizer")
        workflow.add_edge("synthesizer", END)

        return workflow.compile()

    def _tool_executor(self, state: AgentState) -> AgentState:
        """query() 수명주기 동안 열려 있는 DB 연결을 재사용합니다."""
        db = getattr(self._local, "active_db", None)
        if db is None:
            raise RuntimeError("Agent DB가 초기화되지 않았습니다. query() 메서드를 통해 호출하세요.")
        return tool_executor_node(state, db, self.rag)

    def query(self, user_question: str, chat_history: list | None = None) -> str:
        """DB 연결을 쿼리 수명주기 동안 유지하고, 완료 후 해제합니다."""
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

        with KuzuManager(db_path=self.db_path, config=self.config) as db:
            self._local.active_db = db
            try:
                final_state = self.graph.invoke(initial_state)
                return final_state.get("final_answer", "응답을 생성할 수 없습니다.")
            except Exception as e:
                logger.exception("❌ [Agent] 처리 중 오류")
                return f"죄송합니다, 처리 중 오류가 발생했습니다: {e}"
            finally:
                self._local.active_db = None
