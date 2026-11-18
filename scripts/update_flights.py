
import os
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path

API_KEY = os.environ["AVIATIONSTACK_API_KEY"]
BASE = "https://api.aviationstack.com/v1"
TZ = ZoneInfo("Europe/Copenhagen")
now = datetime.now(TZ)

def fetch(endpoint, params):
    params["access_key"] = API_KEY
    url = BASE + "/" + endpoint + "?" + urllib.parse.urlencode(params)

    with urllib.request.urlopen(url, timeout=40) as response:
        result = json.loads(response.read())

    if result.get("error"):
        raise RuntimeError(str(result["error"]))

    return result.get("data", [])

def normalize(f, direction, source):
    if source == "future":
        side = f.get(direction, {})
        other = f.get("departure" if direction == "arrival" else "arrival", {})
        scheduled = side.get("scheduledTime")
        actual = None
        status = "Planlagt"
        number = f.get("flight", {}).get("iataNumber")
        airline = f.get("airline", {}).get("name")
        airport = other.get("iataCode")
    else:
        side = f.get("arrival" if direction == "arrival" else "departure", {})
        other = f.get("departure" if direction == "arrival" else "arrival", {})
        scheduled = side.get("scheduled")
        actual = side.get("actual") or side.get("estimated")
        status = f.get("flight_status", "Ukendt")
        number = f.get("flight", {}).get("iata")
        airline = f.get("airline", {}).get("name")
        airport = other.get("iata")

    if not scheduled:
        return None

    return {
        "direction": direction,
        "flight": number or "Ukendt",
        "airline": airline or "Ukendt",
        "airport": airport or "Ukendt",
        "scheduled": scheduled,
        "actual": actual,
        "status": status,
        "source": source
    }

flights = []
# Seneste syv kalenderdage inklusive i dag
for offset in range(7):
    day = now.date() - timedelta(days=offset)

    for direction, parameter in [
        ("arrival", "arr_iata"),
        ("departure", "dep_iata")
    ]:
        records = fetch("flights", {
            "flight_date": day.isoformat(),
            parameter: "BLL",
            "limit": 100
        })

        for f in records:
            item = normalize(f, direction, "actual")
            if item:
                flights.append(item)

# Næste kalenderdag: fremtidige flyplaner
tomorrow = now.date() + timedelta(days=1)

for index, direction in enumerate(["arrival", "departure"]):
    if index:
        time.sleep(11)

    records = fetch("flightsFuture", {
        "iataCode": "BLL",
        "type": direction,
        "date": tomorrow.isoformat()
    })

    for f in records:
        item = normalize(f, direction, "future")
        if item:
            flights.append(item)

# Kun fremtidige fly inden for de næste 24 timer
end_time = now + timedelta(hours=24)

def parse_time(value):
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo:
            return dt.astimezone(TZ)
        return dt.replace(tzinfo=TZ)
    except (ValueError, TypeError):
        return None

filtered = []
for f in flights:
    dt = parse_time(f["scheduled"])
    if not dt:
        continue

    # Fremtidige poster fra API'et begrænses til 24 timer
    if f["source"] == "future" and not (now <= dt <= end_time):
        continue

    filtered.append(f)

# Fjern dubletter
unique = {}
for f in filtered:
    key = (f["direction"], f["flight"], f["scheduled"])
    unique[key] = f

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

print("Flydata gemt:", len(unique))
