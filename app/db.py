import os
from sqlalchemy import create_engine, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

DB_URL = os.environ.get("DB_URL", "sqlite:///data/prices.db")

# conexão mais resiliente (Render/Neon)
engine = create_engine(
    DB_URL,
    future=True,
    pool_pre_ping=True,
    pool_recycle=180,
    pool_size=5,
    max_overflow=5,
)

def init_db():
    with engine.begin() as conn:
        # Postgres: timestamptz; SQLite: TEXT (compat)
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

def upsert_price(ts_iso: str, price: float):
    with engine.begin() as conn:
        if DB_URL.startswith("postgresql"):
            # ON CONFLICT DO NOTHING
            conn.execute(
                text("""
                    INSERT INTO prices (ts_utc, price_usd)
                    VALUES (:ts, :p)
                    ON CONFLICT (ts_utc) DO NOTHING;
                """),
                {"ts": ts_iso, "p": price}
            )
        else:
            # SQLite: REPLACE INTO emula upsert; aqui ignoramos conflito manualmente
            try:
                conn.execute(text(
                    "INSERT INTO prices (ts_utc, price_usd) VALUES (:ts, :p)"
                ), {"ts": ts_iso, "p": price})
            except Exception:
                pass
# app/db.py
