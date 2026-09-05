import logs
from sqlalchemy import inspect, text
from database.db import engine
from database.db import Base

import database.raw_models
import database.kpi_models

Base.metadata.create_all(
    bind=engine
)

with engine.begin() as connection:
    columns = {
        column["name"]
        for column in inspect(connection).get_columns("app_settings")
    }

    if "use_duration_windows" not in columns:
        connection.execute(
            text(
                "ALTER TABLE app_settings "
                "ADD COLUMN use_duration_windows BOOLEAN NOT NULL DEFAULT 1"
            )
        )

print("Database created")