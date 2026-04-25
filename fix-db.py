from src.config.db import SessionLocal
from sqlalchemy import text

db = SessionLocal()
db.execute(text("UPDATE alembic_version SET version_num = '1036a16afd94'"))
db.commit()
db.close()
print("Done")