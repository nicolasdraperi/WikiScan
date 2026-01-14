import json

with open("../frontend/data/recentchange_15s.json", encoding="utf-8") as f:
    events = json.load(f)

domains = sorted({e["meta"]["domain"] for e in events if "meta" in e})
wikis = sorted({e["wiki"] for e in events if "wiki" in e})

print("Domaines :")
for d in domains:
    print("-", d)

print("\nWikis :")
for w in wikis:
    print("-", w)
