import asyncio
from mcp_client import get_all_tools

if __name__ == "__main__":
    result = asyncio.run(get_all_tools())
    print("Search result:", result)

     