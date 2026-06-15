from database.db import engine
from database.db import Base

Base.metadata.create_all(bind=engine)

print("Database created")