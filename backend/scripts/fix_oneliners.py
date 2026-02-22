import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, BACKEND_DIR)
os.chdir(BACKEND_DIR)

from database import get_db, init_db

init_db()
conn = get_db()
with open("data/gold_standard_reels_3.json") as f:
    reels = json.load(f)["reels"]
updated = 0
for r in reels:
    ol = r.get("one_liner")
    if ol:
        cur = conn.execute("UPDATE reels SET one_liner = ? WHERE title = ?", (ol, r["title"]))
        if cur.rowcount:
            updated += 1
            print("Updated: " + r["title"][:50])
conn.commit()
conn.close()
print(f"Done — {updated} reels updated")
