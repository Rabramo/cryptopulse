import os
from sqlalchemy import create_engine, text

DB_PATH = os.path.join("data", "prices.db")
os.makedirs("data", exist_ok=True)
engine = create_engine(f"sqlite:///{DB_PATH}", future=True)

def init_db():
    with engine.begin() as conn:
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS prices (
          ts_utc TEXT PRIMARY KEY,
          price_usd REAL NOT NULL
        );
        """))
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS meta (
          k TEXT PRIMARY KEY,
          v TEXT
        );
        """))
