from database.db import engine
from database.db import Base

import database.raw_models
import database.kpi_models

Base.metadata.create_all(
    bind=engine
)

print("Database created")