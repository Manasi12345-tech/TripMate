from tavily import TavilyClient
import os
from dotenv import load_dotenv

load_dotenv(dotenv_path=".env")

tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

def tavily_search(query):
    response = tavily_client.search(query, max_results=5)
    results = [
        f"{i}. **{r.get('title', 'Unknown')}**\n {r.get('url', '')}\n {r.get('content', '').strip()[:300]}"
        for i, r in enumerate(response["results"])
    ]
    return "\n\n".join(results)
