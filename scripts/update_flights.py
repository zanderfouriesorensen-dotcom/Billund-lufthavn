
import os
import json
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path

API_KEY = os.environ["AVIATIONSTACK_API_KEY"]
BASE = "https://api.aviationstack.com/v1"

now = datetime.now(ZoneInfo("Europe/Copenhagen"))
today = now.date()

def fetch(endpoint, params):
    params["access_key"] = API_KEY
    url = BASE + "/" + endpoint + "?" + urllib.parse.urlencode(params)

    with urllib.request.urlopen(url, timeout=40) as response:
        result = json.loads(response.read())

    if result.get("error"):
        raise RuntimeError(str(result["error"]))

    return result.get("data", [])

flights = []

# Historiske og aktuelle flybevægelser: seneste 7 dage
for offset in range(7):
    day = today - timedelta(days=offset)
    date_string = day.isoformat()

    for direction, parameter in [
        ("departure", "dep_iata"),
        ("arrival", "arr_iata")
    ]:
        records = fetch("flights", {
            "flight_date": date_string,
            parameter: "BLL",
            "limit": 100
        })

        for flight in records:
            flights.append({
                "direction": direction,
                "source": "historical",
                "date": date_string,
                "flight": flight
            })

# Fremtidige fly: i dag og i morgen
for offset in range(2):
    day = today + timedelta(days=offset)

    for direction in ["arrival", "departure"]:
        records = fetch("flightsFuture", {
            "iataCode": "BLL",
            "type": direction,
            "date": day.isoformat()
        })

        for flight in records:
            flights.append({
                "direction": direction,
                "source": "scheduled",
                "date": day.isoformat(),
                "flight": flight
            })

# Fjern eventuelle dubletter
unique = {}
for item in flights:
    flight = item["flight"]
    number = flight.get("flight", {}).get("iata")
    unique_key = (
        item["direction"],
        item["date"],
        number,
        item["source"]
    )
    unique[unique_key] = item

output = {
    "airport": "BLL",
    "updated": now.isoformat(),
    "timezone": "Europe/Copenhagen",
    "data": list(unique.values())
}

Path("data").mkdir(exist_ok=True)

Path("data/flights.json").write_text(
    json.dumps(output, ensure_ascii=False, indent=2),
    encoding="utf-8"
)

print("Flydata hentet:", len(unique))
