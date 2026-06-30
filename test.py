# debug_topics.py
from database.db import SessionLocal
from database.raw_models import GerritChange

repo = "silicon/dwdm/DIGI_G4_100GX_Firmware"   # replace exactly with a value from /projects
db = SessionLocal()
rows = db.query(GerritChange).filter(GerritChange.project == repo).limit(20).all()
#print("rows found:", len(rows))
for r in rows[:10]:
    raw = r.raw_json
    print("id:", r.change_id, "topic:", raw.get("topic"))
db.close()