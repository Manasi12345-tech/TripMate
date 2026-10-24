"""
flight_tool.py

This module helps look up flight information using the AviationStack API.

It provides:
- Lookup tables to map country names, city names, and aliases to IATA airport codes
  (e.g. "london" → "LHR", "india" → "DEL")
- A helper to clean and normalize user-typed text before searching
  (removes punctuation, stop words like "flight" or "hotel", and extra spaces)

To use this module, set the following in your .env file:
    AVIATIONSTACK_API_KEY=your_api_key_here
    DEFAULT_ORIGIN_IATA=BOM   # your home airport's IATA code
"""
import os
import re
import certifi
import airportsdata
import pycountry
import requests
from dotenv import load_dotenv

load_dotenv()

os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

API_KEY = os.getenv("AVIATIONSTACK_API_KEY")

DEFAULT_ORIGIN = os.getenv("DEFAULT_ORIGIN_IATA") 

BASE_URL = "https://api.aviationstack.com/v1/flights"

AIRPORTS = airportsdata.load("IATA")

COUNTRY_ALIASES = { 
    "usa": "US",
    "u.s.a": "US",
    "u.s.": "US",
    "america": "US",
    "united states": "US",
    "uk": "GB",
    "u.k.": "GB",
    "britain": "GB",
    "england": "GB",
    "uae": "AE",
    "dubai": "AE",
    "south korea": "KR",
    "korea": "KR",
    "russia": "RU",
    "vietnam": "VN",
    "bangladesh": "BD",
    "india": "IN",
    "japan": "JP",
    "china": "CN",
    "singapore": "SG",
    "malaysia": "MY",
    "thailand": "TH",
    "indonesia": "ID",
    "nepal": "NP",
    "qatar": "QA",
    "saudi arabia": "SA",
    "turkey": "TR",
    "canada": "CA",
    "australia": "AU",
    "germany": "DE",
    "france": "FR",
    "italy": "IT",
    "spain": "ES",
}

COUNTRY_MAIN_AIRPORT = {
    "BD": "DAC",
    "IN": "DEL",
    "JP": "NRT",
    "US": "JFK",
    "GB": "LHR",
    "AE": "DXB",
    "SG": "SIN",
    "MY": "KUL",
    "TH": "BKK",
    "ID": "CGK",
    "CN": "PEK",
    "KR": "ICN",
    "NP": "KTM",
    "QA": "DOH",
    "SA": "JED",
    "TR": "IST",
    "CA": "YYZ",
    "AU": "SYD",
    "DE": "FRA",
    "FR": "CDG",
    "IT": "FCO",
    "ES": "MAD",
}

CITY_MAIN_AIRPORT = {
    "dhaka": "DAC",
    "delhi": "DEL",
    "new delhi": "DEL",
    "mumbai": "BOM",
    "kolkata": "CCU",
    "chennai": "MAA",
    "bangalore": "BLR",
    "bengaluru": "BLR",
    "tokyo": "NRT",
    "osaka": "KIX",
    "kyoto": "KIX",
    "new york": "JFK",
    "london": "LHR",
    "dubai": "DXB",
    "singapore": "SIN",
    "kuala lumpur": "KUL",
    "bangkok": "BKK",
    "doha": "DOH",
    "istanbul": "IST",
    "toronto": "YYZ",
    "sydney": "SYD",
    "paris": "CDG",
    "rome": "FCO",
    "madrid": "MAD",
    "frankfurt": "FRA",
}

def clean_text(text: str) -> str:
    """
    Normalize a user-typed string so it can be matched against airport/city names.

    Steps performed:
    1. Converts to lowercase and strips leading/trailing spaces.
    2. Removes all characters except letters, digits, and spaces.
    3. Collapses multiple spaces into one.
    4. Removes travel-related stop words (e.g. "flight", "hotel", "budget")
       that don't help with location matching.

    Args:
        text: Raw user input, e.g. "Flights to New Delhi under budget"

    Returns:
        Cleaned string, e.g. "new delhi"

    Example:
        >>> clean_text("Flights to New Delhi under budget")
        'new delhi'
    """
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s]", "", text)
    text = re.sub(r"\s+"," ",text)
    stop_words = {
        "flight","flights","ticket","tickets","trip","travel","plan","complete","days","day","including","hotel","hotels","sightseeing","under","budget","info","information"
    }
    text = " ".join([word for word in text.split() if word not in stop_words])
    return text

def country_name_to_code(text: str):
    """
    Convert a country name or alias in plain text to its 2-letter ISO country code.

    The function tries the following strategies in order:
    1. Checks the COUNTRY_ALIASES lookup table (e.g. "usa" → "US", "uk" → "GB")
    2. Uses pycountry's exact lookup (e.g. "Germany" → "DE")
    3. Scans the text for any known country name as a substring
    4. Scans the text for any alias as a substring

    Args:
        text: Raw user input containing a country name, e.g. "flights to usa"

    Returns:
        2-letter ISO country code (e.g. "US"), or None if no match is found.
    """
    text = clean_text(text)

    if text in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[text]

    try:
        country = pycountry.countries.lookup(text)
        return country.alpha_2
    except LookupError:
        pass

    for country in pycountry.countries:
        if country.name.lower() in text:
            return country.alpha_2

    for alias, code in COUNTRY_ALIASES.items():
        if alias in text:
            return code

    return None

def get_best_airport_for_country(country_code: str) -> str | None:
    """
    Find the best international airport for a given country.

    Strategy:
    1. Return the curated entry from COUNTRY_MAIN_AIRPORT if available.
    2. Otherwise, score all airports in AIRPORTS for that country and return
       the highest-scoring one. Scoring favours airports with "international"
       or "intl" in the name (+50) and "capital" in the name (+20).

    Args:
        country_code: 2-letter ISO country code (e.g. "IN", "GB").

    Returns:
        IATA code of the best airport (e.g. "DEL"), or None if not found.
    """
    preferred = COUNTRY_MAIN_AIRPORT.get(country_code)
    if preferred and preferred in AIRPORTS:
        return preferred

    candidates = []
    for iata, airport in AIRPORTS.items():
        if not iata or not airport_country_matches(airport, country_code):
            continue

        name = str(airport.get("name", "")).lower()
        score = 0
        if "international" in name or "intl" in name:
            score += 50
        if "capital" in name:
            score += 20

        candidates.append((score, iata))

    if not candidates:
        return None

    candidates.sort(reverse=True)
    return candidates[0][1]


def airport_country_matches(airport: dict, country_code: str) -> bool:
    """
    Check if the given airport belongs to the specified country.

    Args:
        airport: Dictionary containing airport details, must include 'country_code' key.
        country_code: 2-letter ISO country code to match against.

    Returns:
        True if the airport's country code matches the given country code, False otherwise.
    """
    airport_country = str(airport.get("country", "")).upper().strip()

    if airport_country == country_code:
        return True

    try:
        country = pycountry.countries.lookup(airport_country)
        if country and airport_country.lower() == country.name.lower():
            return True
    except Exception:
        pass

    return False

def resolve_location_to_iata(location: str) -> str | None:
    """
    Convert any location string into a 3-letter IATA airport code.

    This is the main entry point for resolving user-typed locations.
    It tries four strategies in order, returning as soon as one succeeds:

    1. Direct IATA code — if the input is already a valid 3-letter code
       (e.g. "DAC", "LHR"), it is validated against the airport database
       and returned immediately.

    2. City lookup — checks CITY_MAIN_AIRPORT for common city names
       (e.g. "tokyo" → "NRT", "mumbai" → "BOM").

    3. Country lookup — uses country_name_to_code() to get an ISO country
       code, then get_best_airport_for_country() to find its main airport
       (e.g. "india" → "IN" → "DEL").

    4. Fuzzy airport scan — scores every airport in AIRPORTS based on how
       well its city/name matches the input and returns the best match:
         - Exact city name match       → +100
         - City name contains input    → +70
         - Airport name contains input → +50
         - Name contains "international" → +10

    Args:
        location: Any location string — IATA code, city name, country name,
                  or alias (e.g. "DAC", "Dhaka", "Bangladesh", "usa").

    Returns:
        3-letter IATA code (e.g. "DAC"), or None if no match is found.

    Examples:
        >>> resolve_location_to_iata("Bangladesh")
        'DAC'
        >>> resolve_location_to_iata("Tokyo")
        'NRT'
        >>> resolve_location_to_iata("DAC")
        'DAC'
        >>> resolve_location_to_iata("usa")
        'JFK'
    """

    if not location:
        return None

    raw_location = location.strip()

    # Direct IATA code
    if re.fullmatch(r"[A-Za-z]{3}", raw_location):
        code = raw_location.upper()
        if code in AIRPORTS:
            return code

    location_clean = clean_text(raw_location)

    if not location_clean:
        return None

    # City preferred airport
    if location_clean in CITY_MAIN_AIRPORT:
        return CITY_MAIN_AIRPORT[location_clean]

    # Country preferred airport
    country_code = country_name_to_code(location_clean)
    if country_code:
        airport = get_best_airport_for_country(country_code)
        if airport:
            return airport

    # Exact city match from airport database
    city_matches = []

    for iata, airport in AIRPORTS.items():
        city = str(airport.get("city", "")).lower().strip()
        name = str(airport.get("name", "")).lower().strip()

        score = 0

        if city == location_clean:
            score += 100
        elif location_clean in city:
            score += 70

        if location_clean in name:
            score += 50

        if "international" in name:
            score += 10

        if score > 0:
            city_matches.append((score, iata))

    if city_matches:
        city_matches.sort(reverse=True)
        return city_matches[0][1]

    return None

def find_location_mentions(query: str):
    """
    Finds country or city names inside a natural language query.
    """

    q = query.lower()
    mentions = []

    # Country aliases
    for alias in COUNTRY_ALIASES:
        if re.search(rf"\b{re.escape(alias)}\b", q):
            mentions.append(alias)

    # Country names from pycountry
    for country in pycountry.countries:
        name = country.name.lower()
        if len(name) >= 4 and re.search(rf"\b{re.escape(name)}\b", q):
            mentions.append(name)

    # City names from our preferred city map
    for city in CITY_MAIN_AIRPORT:
        if re.search(rf"\b{re.escape(city)}\b", q):
            mentions.append(city)

    # Remove duplicate while keeping order
    unique_mentions = []
    for item in mentions:
        if item not in unique_mentions:
            unique_mentions.append(item)

    return unique_mentions

def parse_route(query: str) -> tuple[str | None, str | None]:
    """
    Parse a free-text flight query and return departure and arrival IATA codes.

    Tries six strategies in order, returning as soon as one succeeds:

    1. Global keywords — phrases like "all flights" or "worldwide flights"
       return (None, None), meaning no route filter (show all live flights).

    2. Direct IATA codes — if two 3-letter uppercase codes appear in the query
       (e.g. "DAC to NRT"), they are used directly as departure and arrival.

    3. "from X to Y" pattern — extracts origin and destination from natural
       language (e.g. "flights from Dhaka to Tokyo") and resolves each via
       resolve_location_to_iata().

    4. "to Y from X" pattern — same as above but handles reversed word order
       (e.g. "flights to Tokyo from Dhaka").

    5. One-sided patterns — "from X" returns (dep, None); "to X" returns
       (None, arr), useful for queries like "flights from India".

    6. Fallback location scan — uses find_location_mentions() to detect any
       city or country names in the text. If two are found, they become
       departure and arrival. If only one is found, DEFAULT_ORIGIN_IATA is
       used as the departure.

    Args:
        query: Raw user input, e.g. "show me flights from Dhaka to Tokyo on Friday"

    Returns:
        A tuple (dep_iata, arr_iata) where either value can be None:
          (None, None)  → global/all flights, no route filter
          ("DAC", "NRT") → specific route
          ("DAC", None)  → all flights departing from DAC
          (None, "NRT")  → all flights arriving at NRT

    Examples:
        >>> parse_route("flights from Dhaka to Tokyo")
        ('DAC', 'NRT')
        >>> parse_route("all flights worldwide")
        (None, None)
        >>> parse_route("flights to India")
        (None, 'DEL')
    """

    q = query.strip()
    q_lower = q.lower()

    # Global / all-country query
    global_keywords = [
        "all country",
        "all countries",
        "global flight",
        "global flights",
        "all flight",
        "all flights",
        "worldwide flight",
        "worldwide flights",
    ]

    if any(keyword in q_lower for keyword in global_keywords):
        return None, None

    # Direct IATA code route: DAC to NRT
    codes = re.findall(r"\b[A-Z]{3}\b", q)

    if len(codes) >= 2:
        dep = codes[0].upper()
        arr = codes[1].upper()
        return dep, arr

    # Pattern: from X to Y
    match = re.search(
        r"\bfrom\s+(.+?)\s+\bto\s+(.+?)(?:\s+(?:on|for|under|including|with|in|at)\b|[.!?]|$)",
        q_lower,
    )

    if match:
        origin_text = match.group(1)
        dest_text = match.group(2)

        dep_iata = resolve_location_to_iata(origin_text)
        arr_iata = resolve_location_to_iata(dest_text)

        return dep_iata, arr_iata

    # Pattern: to Y from X
    match = re.search(
        r"\bto\s+(.+?)\s+\bfrom\s+(.+?)(?:\s+(?:on|for|under|including|with|in|at)\b|[.!?]|$)",
        q_lower,
    )

    if match:
        dest_text = match.group(1)
        origin_text = match.group(2)

        dep_iata = resolve_location_to_iata(origin_text)
        arr_iata = resolve_location_to_iata(dest_text)

        return dep_iata, arr_iata

    # Pattern: flights from X
    match = re.search(r"\bfrom\s+(.+?)(?:[.!?]|$)", q_lower)

    if match:
        origin_text = match.group(1)
        dep_iata = resolve_location_to_iata(origin_text)
        return dep_iata, None

    # Pattern: flights to X
    match = re.search(r"\bto\s+(.+?)(?:[.!?]|$)", q_lower)

    if match:
        dest_text = match.group(1)
        arr_iata = resolve_location_to_iata(dest_text)
        return None, arr_iata

    # Fallback: find country/city mentions
    mentions = find_location_mentions(q)

    if len(mentions) >= 2:
        dep_iata = resolve_location_to_iata(mentions[0])
        arr_iata = resolve_location_to_iata(mentions[1])
        return dep_iata, arr_iata

    if len(mentions) == 1:
        arr_iata = resolve_location_to_iata(mentions[0])
        return DEFAULT_ORIGIN, arr_iata

    return None, None

def format_flight(flight: dict) -> str:
    """
    Format a raw AviationStack flight dictionary into a human-readable string.

    Safely extracts nested fields using .get() with sensible fallbacks so the
    function never crashes on missing or partial API data. Departure and arrival
    are each unpacked into airport name, IATA code, terminal, gate, scheduled
    time, and delay.

    Delay is handled specially:
    - None (field absent from API response) → "N/A"
    - 0 or any number                       → "X minutes"

    Args:
        flight: A single flight dict from the AviationStack API response,
                expected to contain nested "airline", "flight", "departure",
                and "arrival" keys.

    Returns:
        A formatted multi-line string with airline, flight number, status,
        and full departure/arrival details, ready to display to the user.

    Example output:
        Airline: Biman Bangladesh Airlines
        Flight: BG148
        Status: active

        Departure:
        - Airport: Hazrat Shahjalal International Airport
        - IATA: DAC
        - Terminal: 1
        - Gate: A3
        - Scheduled: 2024-01-15T08:30:00+00:00
        - Delay: N/A

        Arrival:
        - Airport: Narita International Airport
        - IATA: NRT
        ...
    """
    airline = flight.get("airline", {}).get("name") or "Unknown airline"
    flight_number = flight.get("flight", {}).get("iata") or "Unknown flight number"
    status = flight.get("flight_status") or "Unknown"

    dep = flight.get("departure", {}) or {}
    arr = flight.get("arrival", {}) or {}

    dep_airport = dep.get("airport") or "Unknown departure airport"
    dep_iata = dep.get("iata") or "Unknown"
    dep_terminal = dep.get("terminal") or "N/A"
    dep_gate = dep.get("gate") or "N/A"
    dep_scheduled = dep.get("scheduled") or "Unknown"
    dep_delay = dep.get("delay")
    dep_delay_text = f"{dep_delay} minutes" if dep_delay is not None else "N/A"

    arr_airport = arr.get("airport") or "Unknown arrival airport"
    arr_iata = arr.get("iata") or "Unknown"
    arr_terminal = arr.get("terminal") or "N/A"
    arr_gate = arr.get("gate") or "N/A"
    arr_scheduled = arr.get("scheduled") or "Unknown"
    arr_delay = arr.get("delay")
    arr_delay_text = f"{arr_delay} minutes" if arr_delay is not None else "N/A"

    return f"""
            Airline: {airline}
            Flight: {flight_number}
            Status: {status}

            Departure:
            - Airport: {dep_airport}
            - IATA: {dep_iata}
            - Terminal: {dep_terminal}
            - Gate: {dep_gate}
            - Scheduled: {dep_scheduled}
            - Delay: {dep_delay_text}

            Arrival:
            - Airport: {arr_airport}
            - IATA: {arr_iata}
            - Terminal: {arr_terminal}
            - Gate: {arr_gate}
            - Scheduled: {arr_scheduled}
            - Delay: {arr_delay_text}
            """.strip()

def search_flights(query: str, limit: int = 10) -> str:
    """
    The main entry point — takes a natural language flight query and returns
    formatted live flight results as a string.

    Ties together all the helpers in this module in order:
    1. Validates that AVIATIONSTACK_API_KEY is set; returns a setup hint if not.
    2. Calls parse_route() to extract departure/arrival IATA codes from the query.
    3. Builds the AviationStack API request, adding dep_iata/arr_iata only when found.
    4. Makes the HTTP request with a 30-second timeout.
    5. Handles three error cases separately:
       - Network/connection failure  → RequestException
       - Invalid response body       → ValueError (bad JSON)
       - API-level error             → "error" key in the response JSON
    6. If no flights are returned, gives a helpful message that also clarifies
       this API provides live flight status, not ticket prices.
    7. Formats each flight via format_flight() and joins them with "---" separators,
       prefixed with a route summary line (e.g. "Live flights from DAC to NRT").

    Args:
        query: Natural language flight query, e.g. "flights from Dhaka to Tokyo"
               or "Plan a 7 day Japan trip from Bangladesh".
        limit: Maximum number of flights to return. Capped at 100 (API limit).
               Defaults to 10.

    Returns:
        A formatted string of live flight results, or an error/info message
        if something went wrong or no data was found.

    Examples:
        >>> search_flights("flights from Dhaka to Tokyo")
        'Live flights from DAC to NRT\\n\\n...'

        >>> search_flights("all flights worldwide")
        'Global live flights\\n\\n...'
    """
    if not API_KEY:
        return (
            "Flight API error: AVIATIONSTACK_API_KEY is missing.\n"
            "Please add this in your .env file:\n"
            "AVIATIONSTACK_API_KEY=your_api_key_here"
        )

    dep_iata, arr_iata = parse_route(query)

    params = {
        "access_key": API_KEY,
        "limit": min(limit, 100),
    }

    if dep_iata:
        params["dep_iata"] = dep_iata

    if arr_iata:
        params["arr_iata"] = arr_iata

    try:
        response = requests.get(BASE_URL, params=params, timeout=30)
        data = response.json()
    except requests.exceptions.RequestException as e:
        return f"Flight API request failed: {e}"
    except ValueError:
        return "Flight API returned invalid JSON."

    if "error" in data:
        error = data["error"]
        return (
            "Flight API error:\n"
            f"Code: {error.get('code', 'Unknown')}\n"
            f"Message: {error.get('message', 'Unknown error')}"
        )

    flight_data = data.get("data", [])

    if not flight_data:
        route_text = ""

        if dep_iata and arr_iata:
            route_text = f" for route {dep_iata} to {arr_iata}"
        elif dep_iata:
            route_text = f" from {dep_iata}"
        elif arr_iata:
            route_text = f" to {arr_iata}"

        return (
            f"No live flight data found{route_text}.\n\n"
            "Note: AviationStack provides live/status flight data, not ticket prices. "
            "For actual fare prices, use a flight-pricing API such as Amadeus."
        )

    route_info = "Global live flights"

    if dep_iata and arr_iata:
        route_info = f"Live flights from {dep_iata} to {arr_iata}"
    elif dep_iata:
        route_info = f"Live flights from {dep_iata}"
    elif arr_iata:
        route_info = f"Live flights to {arr_iata}"

    formatted_flights = [format_flight(flight) for flight in flight_data[:limit]]

    return f"{route_info}\n\n" + "\n\n---\n\n".join(formatted_flights)


if __name__ == "__main__":
    print(search_flights("Plan a 7 days Japan trip from Bangladesh"))
    print("\n" + "=" * 80 + "\n")
    print(search_flights("all country flight info"))






