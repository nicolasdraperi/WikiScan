import requests
import json
import time

URL = "https://stream.wikimedia.org/v2/stream/recentchange"
OUTPUT_FILE = "recentchange_180s.json"
DURATION_SECONDS = 180

headers = {
    "Accept": "text/event-stream",
    "User-Agent": "wikimedia-stream-test/1.0"
}

events = []
start_time = time.time()

with requests.get(URL, headers=headers, stream=True) as response:
    response.raise_for_status()

    buffer = ""

    for line in response.iter_lines(decode_unicode=True):
        if time.time() - start_time > DURATION_SECONDS:
            break

        if not line:
            continue

        if line.startswith("data:"):
            data_str = line.replace("data:", "", 1).strip()
            try:
                event = json.loads(data_str)
                events.append(event)
            except json.JSONDecodeError:
                pass

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(events, f, ensure_ascii=False, indent=2)

print(f"{len(events)} événements sauvegardés dans {OUTPUT_FILE}")
