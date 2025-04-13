# Create server parameters for stdio connection
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from dotenv import load_dotenv, find_dotenv
import os
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.prebuilt import create_react_agent

from langchain_openai import ChatOpenAI
load_dotenv(find_dotenv())
model = ChatOpenAI(model="gpt-4o")


server_params = StdioServerParameters(
    command="docker",
    # Make sure to update to the full absolute path to your math_server.py file
    args=["run", "-i", "--rm", "mcp-kipris"],
    env={"OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
         "KIPRIS_API_KEY": os.getenv("KIPRIS_API_KEY")},
    
)

async def main():
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
        # Initialize the connection
            await session.initialize()

            # Get tools
            tools = await load_mcp_tools(session)
            for tool in tools:
                print(tool)
            # Create and run the agent
            agent = create_react_agent(model, tools)
            agent_response = await agent.ainvoke({"messages": "what's (3 + 5) x 12?"})
            print(agent_response)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
