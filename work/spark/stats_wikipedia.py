import json
import re
from collections import Counter, defaultdict
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# ====== CONFIG ======
# Mets ici le bon chemin vers ton JSON (ex: frontend/data/recentchange_180s.json)
JSON_FILE = "frontend/data/recentchange_180s.json"

TOP_N = 10
N_EDITS_INSTABLE = 5   # pages avec >= N edits sur la période

# ====== UTILS ======
IPV4_RE = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}$")
REVERT_HINTS = ("revert", "rv", "rvv", "undid", "undo", "rollback", "révocation", "annulation", "restore")

def is_ip(user: str) -> bool:
    return bool(user and IPV4_RE.match(user))

def diff_size(evt):
    length = evt.get("length") or {}
    old, new = length.get("old"), length.get("new")
    if isinstance(old, int) and isinstance(new, int):
        return new - old
    return None

def looks_like_revert(evt) -> bool:
    comment = (evt.get("comment") or "").lower()
    if any(k in comment for k in REVERT_HINTS):
        return True
    tags = evt.get("tags") or []
    tags_l = [str(t).lower() for t in tags]
    if any(("rollback" in t) or ("undo" in t) or ("revert" in t) for t in tags_l):
        return True
    return False

# ====== LOAD ======
path = Path(JSON_FILE)
with open(path, "r", encoding="utf-8") as f:
    events = json.load(f)

print(f"Loaded {len(events)} events from {path}")

# ====== STATS CORE ======
by_page = Counter()
by_type = Counter()
by_user = Counter()
by_wiki = Counter()
by_namespace = Counter()

bot = human = anon = account = 0
diffs = []
reverts = 0

# Pour % d'édits revertés : on se limite aux événements éditoriaux
EDITORIAL_TYPES = {"edit", "new", "categorize"}  # tu peux enlever/ajouter si tu veux
editorial_total = 0
editorial_reverts = 0

# Reverts par page
reverts_by_page = Counter()

for evt in events:
    title = evt.get("title", "∅")
    etype = evt.get("type", "∅")
    user = evt.get("user", "∅")
    wiki = evt.get("wiki", evt.get("meta", {}).get("domain", "∅"))
    namespace = evt.get("namespace", -1)

    by_page[title] += 1
    by_type[etype] += 1
    by_user[user] += 1
    by_wiki[wiki] += 1
    by_namespace[namespace] += 1

    if evt.get("bot"):
        bot += 1
    else:
        human += 1

    if is_ip(user):
        anon += 1
    else:
        account += 1

    d = diff_size(evt)
    if d is not None:
        diffs.append(d)

    is_rev = looks_like_revert(evt)
    if is_rev:
        reverts += 1
        reverts_by_page[title] += 1

    # % d'édits revertés (sur types éditoriaux)
    if etype in EDITORIAL_TYPES:
        editorial_total += 1
        if is_rev:
            editorial_reverts += 1

# ====== DIFF STATS ======
diffs = np.array(diffs, dtype=np.int64)
mean = float(diffs.mean()) if diffs.size else 0.0
median = float(np.median(diffs)) if diffs.size else 0.0

# Tukey outliers
if diffs.size:
    q1, q3 = np.percentile(diffs, [25, 75])
    iqr = q3 - q1
    outliers = int(((diffs < q1 - 1.5 * iqr) | (diffs > q3 + 1.5 * iqr)).sum())
    minv, maxv = int(diffs.min()), int(diffs.max())
else:
    outliers = 0
    minv = maxv = 0

# ====== NEW STATS DEMANDÉES ======

# 1) Part (%) de chaque langue/wiki
total_events = sum(by_wiki.values()) if by_wiki else 0
wiki_share = [(w, c, (c / total_events) * 100.0) for w, c in by_wiki.most_common()]

# 2) Contenu édité : par namespace
# (déjà dans by_namespace)

# 3) Nb moyen d’edits par utilisateur
unique_users = len([u for u in by_user.keys() if u != "∅"])
avg_edits_per_user = (len(events) / unique_users) if unique_users else 0.0

# 4) % d’édits revertés (sur événements éditoriaux)
pct_reverted = (editorial_reverts / editorial_total) * 100.0 if editorial_total else 0.0

# 5) Pages avec le plus de reverts
top_revert_pages = reverts_by_page.most_common(TOP_N)

# 6) Pages avec >= N edits sur la période
unstable_pages = [(t, c) for t, c in by_page.items() if c >= N_EDITS_INSTABLE]
unstable_pages_sorted = sorted(unstable_pages, key=lambda x: x[1], reverse=True)[:TOP_N]

# ====== PRINT RESULTS ======
print("\n=== STATS (résumé) ===")
print(f"Total events: {len(events)}")
print(f"Top actions: {by_type.most_common(10)}")
print(f"Bot={bot} | Human={human}")
print(f"Anon(IP)={anon} | Accounts={account}")

print("\n--- Langues / wikis (Top) ---")
for w, c, p in wiki_share[:10]:
    print(f"{w:15s}  {c:6d}  {p:6.2f}%")

print("\n--- Contenu édité (namespace Top) ---")
print(by_namespace.most_common(10))

print("\n--- Utilisateurs ---")
print(f"Unique users: {unique_users}")
print(f"Nb moyen d'edits par utilisateur: {avg_edits_per_user:.2f}")
print("Top users:", by_user.most_common(TOP_N))

print("\n--- Reverts ---")
print(f"Approx reverts (tous events): {reverts}")
print(f"% d'édits revertés (types {sorted(EDITORIAL_TYPES)}): {pct_reverted:.2f}%")
print("Pages avec le plus de reverts:", top_revert_pages)

print("\n--- Pages instables ---")
print(f"Pages avec >= {N_EDITS_INSTABLE} edits (Top):", unstable_pages_sorted)

print("\n--- Diff sizes ---")
print(f"mean={mean:.2f} | median={median:.2f} | min={minv} | max={maxv} | outliers={outliers}")

# ====== GRAPHIQUES ======

# A) Part (%) par wiki (Top 10 en camembert)
top_wikis = by_wiki.most_common(10)
if top_wikis:
    labels = [w for w, _ in top_wikis]
    values = [c for _, c in top_wikis]
    plt.figure(figsize=(7, 7))
    plt.pie(values, labels=labels, autopct="%1.1f%%")
    plt.title("Part (%) des wikis / langues (Top 10)")
    plt.show()

# B) Contenu édité par namespace (Top 10)
ns = by_namespace.most_common(10)
if ns:
    labels = [str(k) for k, _ in ns]
    values = [v for _, v in ns]
    plt.figure()
    plt.bar(labels, values)
    plt.title("Activité par namespace (Top 10)")
    plt.xlabel("namespace")
    plt.ylabel("events")
    plt.show()

# C) Actions (type)
types = by_type.most_common()
if types:
    labels = [t for t, _ in types]
    values = [v for _, v in types]
    plt.figure()
    plt.bar(labels, values)
    plt.title("Types d’actions")
    plt.show()

# D) Bot vs humain
plt.figure()
plt.bar(["Bot", "Human"], [bot, human])
plt.title("Bot vs Humain")
plt.show()

# E) Anon vs comptes
plt.figure()
plt.bar(["Anon (IP)", "Accounts"], [anon, account])
plt.title("Anonymes vs Comptes")
plt.show()

# F) Top pages éditées
top_pages = by_page.most_common(TOP_N)
if top_pages:
    pages, counts = zip(*top_pages)
    plt.figure(figsize=(10, 5))
    plt.barh(pages, counts)
    plt.title(f"Top {TOP_N} pages les plus éditées")
    plt.gca().invert_yaxis()
    plt.show()

# G) Distribution des tailles de diff
if diffs.size:
    plt.figure()
    plt.hist(diffs, bins=30)
    plt.title("Distribution des tailles de diff (length.new - length.old)")
    plt.xlabel("diff size")
    plt.ylabel("count")
    plt.show()

# H) Pages avec le plus de reverts
if top_revert_pages:
    pages, counts = zip(*top_revert_pages)
    plt.figure(figsize=(10, 5))
    plt.barh(pages, counts)
    plt.title(f"Top {TOP_N} pages avec le plus de reverts (approx)")
    plt.gca().invert_yaxis()
    plt.show()

# I) Pages instables (>= N edits)
if unstable_pages_sorted:
    pages, counts = zip(*unstable_pages_sorted)
    plt.figure(figsize=(10, 5))
    plt.barh(pages, counts)
    plt.title(f"Pages instables : >= {N_EDITS_INSTABLE} edits (Top {TOP_N})")
    plt.gca().invert_yaxis()
    plt.show()
