"""Minimal check that the EIA API key works and the route is correct."""
import os
import requests
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("EIA_API_KEY")

if not API_KEY:
    raise SystemExit("No EIA_API_KEY found. Check your .env file.")

url = "https://api.eia.gov/v2/electricity/rto/region-data/data/"
params = [
    ("api_key", API_KEY),
    ("frequency", "hourly"),
    ("data[0]", "value"),
    ("facets[respondent][]", "PJM"),
    ("facets[type][]", "D"),
    ("start", "2026-01-01T00"),
    ("end", "2026-01-02T00"),
    ("sort[0][column]", "period"),
    ("sort[0][direction]", "asc"),
    ("offset", 0),
    ("length", 5),
]

r = requests.get(url, params=params, timeout=30)
print("HTTP status:", r.status_code)
payload = r.json()

if "response" not in payload:
    print("Unexpected payload:", payload)
    raise SystemExit("Check your key and the route.")

print("Total rows available:", payload["response"].get("total"))
for row in payload["response"]["data"]:
    print(row)
