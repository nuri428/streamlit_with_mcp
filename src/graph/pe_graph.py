import json
import logging
from typing_extensions import Optional, Dict,  List
from typing import TypedDict, Any
from pathlib import Path
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.runnables import RunnableConfig
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import  StateGraph
from dotenv import load_dotenv, find_dotenv
import re
from .config import DEFAULT_MCP_CONFIG

class AgentState(TypedDict, total=False):
    messages: List[Dict[str, Any]]
    plan: Optional[List[Dict[str, Any]]]
    results: Optional[List[Dict[str, Any]]]
    mcp_config: Optional[Dict[str, Any]]

CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "mcp_config.json"
if CONFIG_PATH.exists():
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        DEFAULT_MCP_CONFIG = json.load(f)
else:
    DEFAULT_MCP_CONFIG = {}

load_dotenv(find_dotenv())
logger = logging.getLogger("mcp_main")
logger.setLevel(logging.DEBUG)

def extract_json_from_markdown(text: str) -> str:
    """Extracts JSON from a ```json code block``` or returns the original if none found."""
    match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text.strip()


async def plan_node(state: AgentState, config: RunnableConfig) -> Dict[str, List[Dict]]:
    mcp_config = state.get("mcp_config", DEFAULT_MCP_CONFIG)
    user_input = state["messages"][-1].content
    logger.info(f"User input: {user_input}")
    model = ChatOpenAI(model="gpt-4o", streaming=False)
    tools = []
    async with MultiServerMCPClient(mcp_config) as mcp_client:
        tools = mcp_client.get_tools()
        logger.info(f"tools: {tools}")

    prompt = (
        "You are an agent planner. Given the user request, "
        "return a JSON array of steps, each step is an object with keys "
        "'tool' (the tool name) and 'args' (a dict of arguments).\n"
        f"Available tools: {tools}\n"
        f"User request: {user_input}\n"
        "Output only valid JSON."
        "Do not include any other text or characters in the output."
        "###OUTPUT FORMAT###\n"
        "```json\n"
        "{}\n"
        "```\n"
)
    plain_chain = model | JsonOutputParser()
    steps = await plain_chain.ainvoke([HumanMessage(content=prompt)])
    logger.info(f"plan_str: {steps}")

    if not steps:
        logger.error("Planner returned empty response.")
        raise ValueError("Planner returned empty plan response.")

    state["plan"] = steps
    logger.info(f"Generated plan: {steps}")
    return {"plan": steps}

async def execute_node(state: AgentState, config: RunnableConfig) -> Dict[str, List[Dict]]:
    mcp_config = state.get("mcp_config", DEFAULT_MCP_CONFIG)
    results = []
    async with MultiServerMCPClient(mcp_config) as mcp_client:
        for step in state["plan"]:
            tool_name = step["tool"]
            args = step.get("args", {})
            tools = mcp_client.get_tools()
            result = {}
            for tool in tools:
                if tool.name == tool_name:
                    logger.info(f"Executing tool {tool_name} with args {args}")
                    result = await tool.arun(args)
                    results.append({"step": step, "result": result})
                    break
    state["results"] = results
    return {"results": results}

async def finalize_node(state: AgentState, config: RunnableConfig) -> Dict[str, str]:
    results = state.get("results", [])
    messages = [
        f"{r['step']['tool']}: {r['result']}" for r in results
    ]
    final_msg = "\n".join(messages)
    return {"final": final_msg}

# Build the Plan & Execute graph
plan_and_execute_graph = StateGraph(AgentState)
plan_and_execute_graph.add_node("plan_node", plan_node)
plan_and_execute_graph.add_node("execute_node", execute_node)
plan_and_execute_graph.add_node("finalize_node", finalize_node)
plan_and_execute_graph.add_edge("plan_node", "execute_node")
plan_and_execute_graph.add_edge("execute_node", "finalize_node")
plan_and_execute_graph.set_entry_point("plan_node")
plan_and_execute_graph = plan_and_execute_graph.compile(MemorySaver())