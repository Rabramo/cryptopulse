import requests
from sqlalchemy import text
from .db import engine
from .utils import utc_now_iso

COINGECKO = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
HEADERS = {"User-Agent": "cryptopulse/1.0 (+github.com/you)"}

def fetch_and_store():
    r = requests.get(COINGECKO, headers=HEADERS, timeout=10)
    r.raise_for_status()
    j = r.json()  # se não for JSON, vai levantar exceção e a API devolverá 502
    price = float(j["bitcoin"]["usd"])
    ts = utc_now_iso()
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT OR IGNORE INTO prices (ts_utc, price_usd) VALUES (:ts,:p)"
        ), {"ts": ts, "p": price})
    return {"ts_utc": ts, "price_usd": price}