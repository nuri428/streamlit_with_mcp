# Create server parameters for stdio connection
from mcp import ClientSession
# from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client
from dotenv import load_dotenv, find_dotenv
# import os
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.prebuilt import create_react_agent

from langchain_openai import ChatOpenAI
load_dotenv(find_dotenv())
model = ChatOpenAI(model="gpt-4o")


async def main():
    # async with stdio_client(server_params) as (read, write):
    async with sse_client(url="http://127.0.0.1:6274/sse/") as (read, write):
        print("Connected to MCP server")
        async with ClientSession(read, write) as session:
            print("Session initialized")
            # Initialize the connection
            await session.initialize()
            print("Initialized")

            # Get tools
            tools = await load_mcp_tools(session)
            print(f"🎯 Loaded tools: {tools}")
            for tool in tools:
                print("Loaded tool:", getattr(tool, "name", "unknown"))
            # Create and run the agent
            agent = create_react_agent(model, tools)
            agent_response = await agent.ainvoke({"messages": "what's (3 + 5) x 12?"})
            print(agent_response)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
