"""LangGraph-based AI agent for meeting data queries.

Architecture:
    User Query -> Router (LLM) -> ToolRegistry.execute() -> Synthesizer -> Response

New tools are registered via @registry.register() in core/agent/tools/.
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
from core.utils import truncate_text

logger = logging.getLogger(__name__)

# Import tool modules to trigger registration
from core.agent.tools import default_registry as tool_registry
import core.agent.tools.search_tools    # noqa: F401
import core.agent.tools.cypher_tools    # noqa: F401
import core.agent.tools.meeting_tools   # noqa: F401
import core.agent.tools.email_tools     # noqa: F401
import core.agent.tools.general_tools   # noqa: F401


class AgentState(TypedDict):
    messages: list
    context: str
    tool_name: str
    tool_args: dict
    tool_result: str
    final_answer: str


def router_node(state: AgentState, llm: ChatOllama) -> AgentState:
    """Analyze the user query and select an appropriate tool."""
    user_messages = state["messages"]

    MAX_ROUTER_MESSAGES = 10
    recent_messages = user_messages[-MAX_ROUTER_MESSAGES:] if len(user_messages) > MAX_ROUTER_MESSAGES else user_messages

    # Tool descriptions are auto-generated from the registry
    tool_descriptions = tool_registry.get_descriptions()

    router_prompt = f"""You are a tool router for a meeting analysis system.
Analyze the user's question and select the most appropriate tool.

{tool_descriptions}

Respond with JSON only:
{{"tool_name": "<tool_name>", "tool_args": {{<args>}}}}

Rules (in priority order):
1. General greetings or off-topic questions → "direct_answer"
2. Email drafting requests → "draft_email"
3. Summary of a specific meeting (meeting ID or title known) → "get_meeting_summary"
4. Questions explicitly about what someone said or direct quotes → "search_by_meaning"
   - include tool_args.query as the search phrase
5. Simple listing requests ("주제 목록", "할 일 목록", "참여자 목록", "회의 목록") → "search_by_structure"
   - include entity_type in ["topic","task","decision","person","meeting","entity"]
   - include keyword when relevant
6. Questions about a specific person (e.g. "김태훈에 대해") → "search_by_structure"
   - set entity_type to "person" and keyword to the person's name
7. Precise DB queries requiring exact counts, aggregation, or complex filtering → "search_by_cypher"
   - include tool_args.query as the natural language question
   - e.g. "몇 개의 토픽이 있어?", "결정 사항이 없는 토픽은?", "가장 많이 발언한 사람은?"
8. For ALL other questions → "hybrid_search" (default choice)
   - include tool_args.query as the full user question
   - include tool_args.search_hints as a list of relevant data categories to search:
     "task" = action items, to-dos, assignments, progress, deadlines
     "decision" = agreements, conclusions, approvals, commitments
     "people" = participants, speakers, who did what
     "meeting" = meeting info, dates, schedules
     "entity" = technologies, concepts, organizations, events, relationships
   - Example: "진행 상황 어때?" → {{"query": "진행 상황 어때?", "search_hints": ["task"]}}
   - Example: "React 관련 내용" → {{"query": "React 관련 내용", "search_hints": ["entity"]}}
   - Example: "누가 뭘 하기로 했어?" → {{"query": "누가 뭘 하기로 했어?", "search_hints": ["task", "people", "decision"]}}
   - If unsure, include multiple relevant hints rather than none
   - This includes: complex questions, multi-aspect queries, concept questions, relationship questions, analysis requests, and any ambiguous queries
"""

    messages = [SystemMessage(content=router_prompt)] + recent_messages
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
    """Execute the selected tool via the registry."""
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
    """Generate a natural language answer from tool results."""
    tool_name = state.get("tool_name", "")
    tool_result = state.get("tool_result", "")

    safe_tool_result = truncate_text(tool_result, max_tokens=20_000)

    all_messages = state.get("messages", [])
    MAX_HISTORY_MESSAGES = 20
    recent_messages = all_messages[-MAX_HISTORY_MESSAGES:] if len(all_messages) > MAX_HISTORY_MESSAGES else all_messages

    if tool_name == "draft_email":
        try:
            email_data = json.loads(tool_result)
            email_context = truncate_text(
                email_data.get('context', '(데이터 없음)'), max_tokens=15_000
            )
            synth_prompt = f"""You are a professional email writer.
Based on the meeting data below, draft a business email in Korean.

수신자: {email_data.get('recipient', '팀원')}
제목: {email_data.get('subject', '회의 결과')}

회의 데이터:
{email_context}

Write a clear, professional email in Korean. Include:
- 인사말
- 회의 주요 내용 요약
- 결정 사항
- 할 일 (담당자 포함)
- 마무리 인사
"""
        except (json.JSONDecodeError, TypeError):
            synth_prompt = f"이메일 초안을 작성해주세요. 데이터: {safe_tool_result}"
        messages = [SystemMessage(content=synth_prompt)]

    elif tool_name == "direct_answer":
        synth_prompt = """You are a helpful meeting analysis assistant called SpeakNode.
Answer the user's question naturally in Korean.
If the question is about meeting data, let them know they can ask specific questions about topics, tasks, decisions, or people."""
        messages = [SystemMessage(content=synth_prompt)] + recent_messages

    else:
        synth_prompt = f"""You are a meeting analysis assistant called SpeakNode.
Based on the search results below, provide a clear and helpful answer to the user's question in Korean.
Cite specific data from the results. If results are empty, let the user know.

검색 결과:
{safe_tool_result}
"""
        messages = [SystemMessage(content=synth_prompt)] + recent_messages

    response = llm.invoke(messages)
    state["final_answer"] = response.content
    state["messages"] = state["messages"] + [AIMessage(content=state["final_answer"])]
    return state


class SpeakNodeAgent:
    """LangGraph-based agent with per-query DB lifecycle."""

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
        """Reuse the DB connection kept open during query()."""
        db = getattr(self._local, "active_db", None)
        if db is None:
            raise RuntimeError("Agent DB not initialised. Call query() instead.")
        return tool_executor_node(state, db, self.rag)

    def query(self, user_question: str, chat_history: list | None = None) -> str:
        """Run the agent graph, managing DB lifecycle per call."""
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
                return final_state.get("final_answer", "Unable to generate a response.")
            except Exception as e:
                logger.exception("Agent processing error")
                return f"An error occurred: {e}"
            finally:
                self._local.active_db = None
