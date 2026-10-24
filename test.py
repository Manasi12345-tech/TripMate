from tools.tavily_tool import tavily_search
from tools.flight_tool import search_flights
# res = tavily_search("Best hotels in India")
# print(res)
# res = search_flights("plan 7 days Nepal trip from Bangladesh")
# print(res)

#test the run_travel_agent
from backend import run_travel_agent

res = run_travel_agent("plan 7 days Nepal trip from India","test_user")
print(res["answer"])