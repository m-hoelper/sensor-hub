from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
import sensor_hub.config as config

class Base(DeclarativeBase):
    pass

engine = create_engine(config.get_settings().database_url.get_secret_value())
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()