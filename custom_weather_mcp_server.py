"""
custom_weather_mcp_server.py — TripMate Custom Weather MCP Server

What is this file?
------------------
This file creates a small "tool server" that gives the TripMate AI agent
the ability to check live weather data. It uses a protocol called MCP
(Model Context Protocol), which is a standard way for AI agents to call
external tools.

How does it work?
-----------------
1. This script starts a local server using FastMCP.
2. The server exposes two tools: get_current_weather and get_forecast.
3. When TripMate's AI needs weather info, it calls one of these tools.
4. The tool makes an HTTP request to the OpenWeatherMap API and returns
   the result to the AI.

How to run this server?
-----------------------
Make sure OPENWEATHER_API_KEY is set in your .env file, then run:

    python custom_weather_mcp_server.py

The server will start and wait for the AI agent to connect and call tools.

Prerequisites:
--------------
- A free API key from https://openweathermap.org/api
- The key saved in your .env file as:  OPENWEATHER_API_KEY=your_key_here
"""

from mcp.server.fastmcp import FastMCP  # FastMCP makes it easy to create MCP tool servers
import requests                          # used to call the OpenWeatherMap HTTP API
import os                                # used to read environment variables
from dotenv import load_dotenv           # reads key=value pairs from the .env file into os.getenv()

# Load environment variables from the .env file in the project root.
# This must happen before calling os.getenv() below.
load_dotenv()

# Create the MCP server. The string "Weather MCP server" is the server's
# display name — it shows up in logs and in the AI agent's tool list.
mcp = FastMCP("Weather MCP server")

# Read the OpenWeatherMap API key from the environment.
# If this is None, the API calls below will return 401 Unauthorized.
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")


# ─── Tool 1: Current weather ────────────────────────────────────────────────
#
# The @mcp.tool() decorator registers this function as a callable tool.
# The string inside is the tool's description — the AI reads it to decide
# when to use this tool.

@mcp.tool()
def get_current_weather(city: str):
    """
    Fetch the current weather conditions for a given city.

    How it works:
    - Calls the OpenWeatherMap "current weather" endpoint.
    - &units=metric means temperatures are returned in Celsius.
    - On success, returns a flat dict the AI can read directly.
    - On failure (bad city name, network error, etc.) returns an error message.

    Args:
        city: The name of the city, e.g. "Paris" or "New York".

    Returns:
        A dict with temperature, humidity, wind, and sky conditions,
        or {"error": "..."} if the request failed.
    """
    # Build the API URL. f-strings let us embed variables directly in the string.
    url = (
        f"http://api.openweathermap.org/data/2.5/weather"
        f"?q={city}&appid={OPENWEATHER_API_KEY}&units=metric"
    )

    response = requests.get(url)

    if response.status_code == 200:
        # .json() parses the raw JSON text into a Python dictionary.
        data = response.json()

        # Pull out only the fields the AI needs — the full API response
        # contains dozens of fields we don't care about.
        return {
            "city":          data["name"],               # official city name from the API
            "temperature_c": data["main"]["temp"],       # current temperature in °C
            "feels_like_c":  data["main"]["feels_like"], # "feels like" temperature in °C
            "humidity":      data["main"]["humidity"],   # humidity as a percentage (0–100)
            "condition":     data["weather"][0]["description"],  # e.g. "light rain"
            "wind_speed":    data["wind"]["speed"],      # wind speed in m/s
        }
    else:
        # Return a plain error dict so the AI can tell the user something went wrong.
        return {"error": "Unable to fetch weather data"}


# ─── Tool 2: Weather forecast ───────────────────────────────────────────────

@mcp.tool()
def get_forecast(city: str):
    """
    Fetch a short weather forecast (next 5 time slots) for a given city.

    How it works:
    - Calls the OpenWeatherMap "5-day forecast" endpoint, which returns
      weather predictions every 3 hours.
    - We take only the first 5 entries (covering roughly the next 15 hours)
      to keep the response compact and easy for the AI to summarise.

    Args:
        city: The name of the city, e.g. "Tokyo" or "Mumbai".

    Returns:
        A dict with the city name and a list of up to 5 forecast snapshots,
        or {"error": "..."} if the request failed.

    Example return value:
        {
            "city": "Tokyo",
            "forecast": [
                {"datetime": "2024-06-01 12:00:00", "temperature": 28.3, "weather": "clear sky"},
                {"datetime": "2024-06-01 15:00:00", "temperature": 29.1, "weather": "few clouds"},
                ...
            ]
        }
    """
    url = (
        f"http://api.openweathermap.org/data/2.5/forecast"
        f"?q={city}&appid={OPENWEATHER_API_KEY}&units=metric"
    )

    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()

        # data["list"] contains one entry per 3-hour window for 5 days (40 total).
        # [:5] slices just the first 5 so we don't overwhelm the AI with data.
        forecast_list = []
        for item in data["list"][:5]:
            forecast_list.append({
                "datetime":    item["dt_txt"],                    # e.g. "2024-06-01 12:00:00"
                "temperature": item["main"]["temp"],              # temperature in °C
                "weather":     item["weather"][0]["description"], # e.g. "overcast clouds"
            })

        return {
            "city":     city,
            "forecast": forecast_list,
        }
    else:
        return {"error": "Unable to fetch forecast data"}


# ─── Entry point ────────────────────────────────────────────────────────────
#
# This block only runs when you execute the file directly:
#   python custom_weather_mcp_server.py
#
# mcp.run() starts the server and keeps it running, waiting for the AI agent
# to connect and call the tools above.

if __name__ == "__main__":
    mcp.run()
