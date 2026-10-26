"""
app.py — TripMate AI Web Server

This is the entry point of the TripMate application.
It uses FastAPI to create a web server that:
  - Serves the chat UI in the browser
  - Accepts travel planning requests from the user
  - Calls the AI travel agent (defined in backend.py) and returns results

How it works:
  1. User opens the browser at http://127.0.0.1:8000
  2. The home page (index.html) is loaded
  3. User types a travel question; the page sends it to POST /api/travel
  4. The server calls the AI agent and sends back flights, hotels, and an itinerary
"""

from pathlib import Path  # helps build file paths that work on any OS
import traceback          # used to print detailed error information
import uvicorn            # the web server that runs FastAPI

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles      # serves CSS/JS/images
from fastapi.templating import Jinja2Templates   # renders HTML templates
from pydantic import BaseModel                   # validates incoming JSON data
import nest_asyncio                 # allows asyncio.run() to be called inside an already running event loop (useful for Jupyter or FastAPI)
nest_asyncio.apply()

from backend import run_travel_agent  # the AI agent that does the actual planning

# Build the absolute path to this file's directory so we can find
# the static/ and templates/ folders regardless of where the app is run from.
BASE_DIR = Path(__file__).resolve().parent

# Create the FastAPI application. The title/description/version show up
# in the auto-generated API docs at http://127.0.0.1:8000/docs
app = FastAPI(
    title="TripMate AI",
    description="Multi Agent Travel Planner and FastAPI Application",
    version="1.0.0",
)

# Tell FastAPI where to find static files (CSS, JS, images).
# Any file in static/ will be accessible at /static/<filename> in the browser.
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

# Tell FastAPI where our HTML templates live.
# Jinja2 fills in dynamic data before sending HTML to the browser.
templates = Jinja2Templates(directory=BASE_DIR / "templates")


class TravelRequest(BaseModel):
    """
    Defines the shape of the JSON body expected by POST /api/travel.

    Fields:
        message   — the user's travel question (e.g. "Plan a 5-day trip to Paris")
        thread_id — optional ID that links messages in the same conversation;
                    if None, the backend starts a new conversation thread
    """
    message: str
    thread_id: str | None = None


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """
    Serves the main chat page.

    When a user visits http://127.0.0.1:8000 in their browser, this function
    renders templates/index.html and sends it back as an HTML page.
    """
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={},  # no extra variables needed by the template right now
    )


@app.post("/api/travel")
async def travel_planner(request_data: TravelRequest):
    """
    Main API endpoint — processes a travel planning request.

    The browser sends a POST request with JSON like:
        { "message": "I want to fly from NYC to Tokyo next month", "thread_id": null }

    Steps:
        1. Validate that the message is not empty
        2. Pass the message to the AI travel agent (run_travel_agent)
        3. Return the agent's answer, along with flight/hotel/itinerary data

    Returns a JSON object with:
        success        — True if everything went well
        thread_id      — ID to use in the next message to continue the conversation
        answer         — the AI's text reply
        flight_results — list of flight options found
        hotel_results  — list of hotel options found
        itinerary      — day-by-day travel plan
        llm_calls      — number of AI model calls made (useful for debugging)

    On error, returns HTTP 500 with the error message and stack trace.
    """
    try:
        # .strip() removes accidental leading/trailing spaces from the message
        user_message = request_data.message.strip()

        if not user_message:
            # HTTP 400 = "Bad Request" — the client sent invalid data
            return JSONResponse(
                status_code=400,
                content={"error": "Message cannot be empty"},
            )

        # Hand off to the AI agent and wait for it to finish
        result = run_travel_agent(user_message, request_data.thread_id)

        return JSONResponse(
            content={
                "success": True,
                "thread_id": result["thread_id"],
                "answer": result["answer"],
                "flight_results": result["flight_results"],
                "hotel_results": result["hotel_results"],
                "itinerary": result["itinerary"],
                "llm_calls": result["llm_calls"],
            }
        )
    except Exception as e:
        # Print the full error to the server console for debugging
        print("ERROR:", e)
        traceback.print_exc()
        # HTTP 500 = "Internal Server Error" — something unexpected went wrong
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "trace": traceback.format_exc()},
        )


@app.get("/health")
async def health_check():
    """
    Simple health check endpoint.

    Useful for monitoring tools or deployment platforms to verify
    the server is running. Visit http://127.0.0.1:8000/health to check.
    """
    return {
        "status": "ok",
        "message": "AI Travel Planner API is running",
    }


@app.get("/favicon.ico")
async def favicon():
    """
    Prevents 404 errors when browsers automatically request the site icon.
    Returns an empty response instead of an error.
    """
    return JSONResponse(content={})


# This block only runs when you execute the file directly with `python app.py`.
# It starts the uvicorn web server on localhost port 8000.
# reload=True means the server automatically restarts when you save a file —
# handy during development so you don't have to restart manually.
if __name__ == "__main__":
    uvicorn.run(
        "app:app",       # "module_name:fastapi_instance_name"
        host="127.0.0.1",
        port=8000,
        reload=True,
    )
    