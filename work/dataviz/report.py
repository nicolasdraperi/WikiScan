import json
import re
from collections import Counter
from pathlib import Path


import numpy as np # type: ignore
import matplotlib.pyplot as plt # type: ignore


# ====== CONFIG ======
JSON_FILE = "frontend/data/recentchange_180s.json"  # <-- adapte si besoin
TOP_N = 10
N_EDITS_INSTABLE = 5  # pages avec >= N edits sur la période


# % revertés calculé sur ces types (tu peux mettre {"edit"} si tu veux strict)
EDITORIAL_TYPES = {"edit", "new", "categorize"}

# Histogramme diff: on ignore les extrêmes visuellement (zoom percentile)
DIFF_ZOOM_PCTL_LOW = 1    # 1%
DIFF_ZOOM_PCTL_HIGH = 99  # 99%

# ====== LABELS ======
NS_LABELS = {
    0: "Article",
    1: "Discussion (article)",
    2: "Utilisateur",
    3: "Discussion (utilisateur)",
    4: "Projet (Wikipedia)",
    5: "Discussion (projet)",
    6: "Fichier",
    7: "Discussion (fichier)",
    8: "MediaWiki",
    9: "Discussion (MediaWiki)",
    10: "Modèle",
    11: "Discussion (modèle)",
    12: "Aide",
    13: "Discussion (aide)",
    14: "Catégorie",
    15: "Discussion (catégorie)",
}

# ====== UTILS ======
IPV4_RE = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}$")
REVERT_HINTS = (
    "revert", "rv", "rvv", "undid", "undo", "rollback",
    "révocation", "annulation", "restore"
)

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
    return any(("rollback" in t) or ("undo" in t) or ("revert" in t) for t in tags_l)

def ns_label(ns: int) -> str:
    return NS_LABELS.get(ns, f"NS {ns}")

# ====== LOAD ======
path = Path(JSON_FILE)
with open(path, "r", encoding="utf-8") as f:
    events = json.load(f)

print(f"Loaded {len(events)} events from {path}")

# ====== STATS ======
by_page = Counter()
by_type = Counter()
by_user = Counter()
by_wiki = Counter()
by_namespace = Counter()

reverts_by_page = Counter()

bot = human = anon = account = 0
diffs = []
reverts_total = 0

# % d'édits revertés (sur types éditoriaux)
editorial_total = 0
editorial_reverts = 0

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
        reverts_total += 1
        reverts_by_page[title] += 1

    if etype in EDITORIAL_TYPES:
        editorial_total += 1
        if is_rev:
            editorial_reverts += 1

diffs = np.array(diffs, dtype=np.int64)

# ====== DERIVED METRICS ======
total_events = len(events)

unique_users = len([u for u in by_user.keys() if u != "∅"])
avg_edits_per_user = (total_events / unique_users) if unique_users else 0.0

pct_reverted = (editorial_reverts / editorial_total) * 100.0 if editorial_total else 0.0

# diff stats
if diffs.size:
    mean_diff = float(diffs.mean())
    median_diff = float(np.median(diffs))
    min_diff = int(diffs.min())
    max_diff = int(diffs.max())

    # outliers Tukey
    q1, q3 = np.percentile(diffs, [25, 75])
    iqr = q3 - q1
    outliers = int(((diffs < q1 - 1.5 * iqr) | (diffs > q3 + 1.5 * iqr)).sum())
else:
    mean_diff = median_diff = 0.0
    min_diff = max_diff = 0
    outliers = 0

# top lists
top_pages = by_page.most_common(TOP_N)
top_users = by_user.most_common(TOP_N)
top_types = by_type.most_common(10)
top_wikis = by_wiki.most_common(10)

# namespaces top avec label
top_namespaces = [(ns, c, ns_label(ns)) for ns, c in by_namespace.most_common(10)]

top_revert_pages = reverts_by_page.most_common(TOP_N)

unstable_pages = sorted(
    [(t, c) for t, c in by_page.items() if c >= N_EDITS_INSTABLE],
    key=lambda x: x[1],
    reverse=True
)[:TOP_N]

# wiki share
wiki_total = sum(by_wiki.values()) or 1
wiki_share_top10 = [(w, c, (c / wiki_total) * 100.0) for w, c in top_wikis]

# ====== PRINT SUMMARY ======
print("\n=== STATS (résumé) ===")
print(f"Total events: {total_events}")
print(f"Top actions: {top_types}")
print(f"Bot={bot} | Human={human}")
print(f"Anon(IP)={anon} | Accounts={account}")

print("\n--- Langues / wikis (Top 10) ---")
for w, c, p in wiki_share_top10:
    print(f"{w:18s} {c:6d}  {p:6.2f}%")

print("\n--- Contenu édité (namespace Top 10) ---")
for ns, c, label in top_namespaces:
    print(f"{ns:>4}: {c:<6d} -> {label}")

print("\n--- Utilisateurs ---")
print(f"Unique users: {unique_users}")
print(f"Nb moyen d'edits par utilisateur: {avg_edits_per_user:.2f}")
print("Top users:", top_users)

print("\n--- Reverts ---")
print(f"Approx reverts (tous events): {reverts_total}")
print(f"% d'édits revertés (types {sorted(EDITORIAL_TYPES)}): {pct_reverted:.2f}%")
print("Pages avec le plus de reverts:", top_revert_pages)

print("\n--- Pages instables ---")
print(f"Pages avec >= {N_EDITS_INSTABLE} edits (Top {TOP_N}):", unstable_pages)

print("\n--- Diff sizes ---")
print(f"mean={mean_diff:.2f} | median={median_diff:.2f} | min={min_diff} | max={max_diff} | outliers={outliers}")

# ====== GRAPHS ======

# 1) Part (%) des wikis (camembert Top 10)
if top_wikis:
    labels = [w for w, _ in top_wikis]
    values = [c for _, c in top_wikis]
    plt.figure(figsize=(7, 7))
    plt.pie(values, labels=labels, autopct="%1.1f%%")
    plt.title("Part (%) des wikis / langues (Top 10)")
    plt.show()

# 2) Activité par namespace (barres Top 10) avec labels
if top_namespaces:
    labels = [f"{ns}\n{label}" for ns, _, label in top_namespaces]
    values = [c for _, c, _ in top_namespaces]
    plt.figure(figsize=(10, 4))
    plt.bar(labels, values)
    plt.title("Activité par namespace (Top 10)")
    plt.xlabel("namespace")
    plt.ylabel("events")
    plt.xticks(rotation=0)
    plt.show()

# 3) Types d’actions
if by_type:
    labels = [t for t, _ in by_type.most_common()]
    values = [v for _, v in by_type.most_common()]
    plt.figure()
    plt.bar(labels, values)
    plt.title("Types d’actions")
    plt.show()

# 4) Bot vs Humain
plt.figure()
plt.bar(["Bot", "Human"], [bot, human])
plt.title("Bot vs Humain")
plt.show()

# 5) Anonymes vs Comptes
plt.figure()
plt.bar(["Anon (IP)", "Accounts"], [anon, account])
plt.title("Anonymes vs Comptes")
plt.show()

# 6) Top pages éditées
if top_pages:
    pages, counts = zip(*top_pages)
    plt.figure(figsize=(10, 5))
    plt.barh(pages, counts)
    plt.title(f"Top {TOP_N} pages les plus éditées")
    plt.gca().invert_yaxis()
    plt.show()

# 7) Diff sizes histogram (ZOOM en ignorant les extrêmes)
if diffs.size:
    low, high = np.percentile(diffs, [DIFF_ZOOM_PCTL_LOW, DIFF_ZOOM_PCTL_HIGH])
    clipped = diffs[(diffs >= low) & (diffs <= high)]

    plt.figure()
    plt.hist(clipped, bins=30)
    plt.title(f"Distribution des tailles de diff (zoom {DIFF_ZOOM_PCTL_LOW}%–{DIFF_ZOOM_PCTL_HIGH}%)")
    plt.xlabel("length.new - length.old")
    plt.ylabel("count")
    plt.show()

    # Bonus: afficher l'info de zoom dans la console
    print(f"\n[Diff zoom] showing values in [{low:.0f}, {high:.0f}] (percentiles {DIFF_ZOOM_PCTL_LOW}–{DIFF_ZOOM_PCTL_HIGH})")

# 8) Pages avec le plus de reverts
if top_revert_pages:
    pages, counts = zip(*top_revert_pages)
    plt.figure(figsize=(10, 5))
    plt.barh(pages, counts)
    plt.title(f"Top {TOP_N} pages avec le plus de reverts (approx)")
    plt.gca().invert_yaxis()
    plt.show()

# 9) Pages instables (>= N edits)
if unstable_pages:
    pages, counts = zip(*unstable_pages)
    plt.figure(figsize=(10, 5))
    plt.barh(pages, counts)
    plt.title(f"Pages instables : >= {N_EDITS_INSTABLE} edits (Top {TOP_N})")
    plt.gca().invert_yaxis()
    plt.show()
