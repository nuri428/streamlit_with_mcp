from langgraph.graph import StateGraph, END
from .react_graph import graph as react_graph
from .pe_graph import plan_and_execute_graph as pe_graph
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver

llm_model = "gpt-4o"

llm = ChatOpenAI(model="gpt-4o")
# supervisor graph

async def decide_user_intent(state):
    user_input = state["messages"][-1].content
    prompt = f"""사용자 입력이 도구 실행(plan) 또는 단순 질의응답(react) 중 무엇이 적절한가요?
입력: "{user_input}" 
출력은 'plan' 또는 'react'만 주세요."""
    resp = await llm.apredict(prompt)
    return resp.strip().lower()

workflow = StateGraph(StateGraph)
workflow.add_node("decide_user_intent", decide_user_intent)
workflow.add_node("react_graph", react_graph)
workflow.add_node("pe_graph", pe_graph)
# 예외 분기
workflow.add_conditional_edges("decide_user_intent", lambda x: x if x in ["react", "plan"] else "react", {
    "react": "react_graph",
    "plan": "pe_graph",
})
workflow.add_edge("react_graph", END)
workflow.add_edge("pe_graph", END)
workflow.set_entry_point("decide_user_intent")

graph = workflow.compile(MemorySaver())