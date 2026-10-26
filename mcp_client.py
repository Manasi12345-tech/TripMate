import os
import asyncio
from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_groq import ChatGroq 

# Load environment variables from the .env file so TAVILY_API_KEY is available.
load_dotenv()

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
AVIATIONSTACK_API_KEY = os.getenv("AVIATIONSTACK_API_KEY") 
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")


llm = ChatGroq(
    model="openai/gpt-oss-120b",
    api_key=GROQ_API_KEY
)
client = MultiServerMCPClient(
    {
        "tavily": {
            "transport": "streamable_http",
            "url": f"https://mcp.tavily.com/mcp/?tavilyApiKey={TAVILY_API_KEY}"
        },
        "aviationstack": {
            "transport": "stdio",
            "command": "uvx",
            "args": [
                "aviationstack-mcp"
            ],
            "env": {
                "AVIATION_STACK_API_KEY": AVIATIONSTACK_API_KEY
            }
        },
        "weather": {
            "transport": "stdio",
            "command": "/Users/I550464/Documents/TripMate/.venv/bin/python",
            "args": [
                "/Users/I550464/Documents/TripMate/custom_weather_mcp_server.py"
            ],
            "env": {
                "OPENWEATHER_API_KEY": OPENWEATHER_API_KEY
            } 
        }
    }
)

async def get_all_tools():
    """Print every tool available from all configured MCP servers.

    Useful during development to explore what a new MCP server offers
    before writing code that calls a specific tool.
    """
    tools = await client.get_tools()
    print("Available tools:", tools)
    for tool in tools:
        print("\nTool:", tool)

search_tools = None
aviation_tools = {}

async def initialize_mcp():
    global search_tools, aviation_tools

    if search_tools is not None and aviation_tools:
        return
    
    tools = await client.get_tools()

    # tools are StructuredTool objects — use .name attribute, not dict access
    search_tools = next((t for t in tools if t.name == "tavily_search"), None)
    aviation_tools = {t.name: t for t in tools if t.name != "tavily_search"}


async def tavily_mcp_search(query: str):
    """Run a web search using the Tavily MCP tool.

    This is the only function that backend.py needs to import. It handles
    tool discovery, caching, and invocation internally so the caller does
    not need to know anything about MCP.

    Args:
        query: A natural-language search query, e.g.
               "Best hotels in Paris for a family of 4 under $200/night"

    Returns:
        A string containing Tavily's search results, ready to be passed
        to the LLM as context for generating hotel recommendations.
    """
    # Ensure the tool is fetched and cached before we try to use it.
    await initialize_mcp()

    # ainvoke() is the async version of calling the tool. We pass a dict
    # with a "query" key because that is the input schema the tavily_search
    # tool expects (discovered from the MCP server's tool definition).
    
    result = await search_tools.ainvoke({"query": query})
    return result

async def aviationstack_mcp_search(tool_name: str, tool_args: dict = None):
    """Run a search using the Aviationstack MCP tool.

    Args:
        tool_name: The name of the Aviationstack tool to use.
        tool_args: A dictionary of arguments to pass to the Aviationstack tool .

    Returns:
        The result of invoking the specified Aviationstack tool.
    """
    await initialize_mcp()

    tool = aviation_tools.get(tool_name)
    if not tool:
        raise ValueError(f"Aviationstack tool '{tool_name}' not found")

    result = await tool.ainvoke(tool_args or {})
    return result 

weather_tool = None
forecast_tool = None

async def initialize_weather_tools():
    global weather_tool, forecast_tool

    if weather_tool is not None and forecast_tool is not None:
        return

    tools = await client.get_tools()
    weather_tool = next((t for t in tools if t.name == "get_current_weather"), None)
    forecast_tool = next((t for t in tools if t.name == "get_forecast"), None) 

async def weather_mcp_search(city: str):
    await initialize_weather_tools()

    if not weather_tool:
        raise ValueError("Weather tool not found")

    result = await weather_tool.ainvoke({"city": city})
    return result

async def forecast_mcp_search(city: str):
    await initialize_weather_tools()

    if not forecast_tool:
        raise ValueError("Forecast tool not found")

    result = await forecast_tool.ainvoke({"city": city})
    return result

def extract_destination(query: str) -> str:
    """
    Extract the destination city from a natural-language query.

    Args:
        query: A natural-language search query, e.g.
               "Best hotels in Paris for a family of 4 under $200/night"

    Returns:
        The extracted city name as a string.
    """
    prompt = f"Extract the destination city from the following query: '{query}' return only the extracted city or country name"
    response = llm.invoke(prompt)
    return response.content.strip() 