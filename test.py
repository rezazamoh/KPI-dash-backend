from database.db import SessionLocal
from database.raw_models import GerritChange

db = SessionLocal()

row = db.query(GerritChange).first()

print(row.raw_json)

db.close()