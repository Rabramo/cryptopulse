from fastapi import FastAPI, BackgroundTasks
from datetime import datetime, timezone
from .ingestor import fetch_btc_price, polite_sleep
from .db import init_db, upsert_price

app = FastAPI(title="CryptoPulse")

BATCH_STATE = {"running": False, "done": 0, "fail": 0, "target": 0}

@app.on_event("startup")
def _startup():
    init_db()

@app.get("/")
def health():
    return {"ok": True, "service": "CryptoPulse"}

@app.post("/ingest")
def ingest():
    try:
        price = fetch_btc_price()
        ts = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        upsert_price(ts, price)
        return {"status": "ok", "ts_utc": ts, "price_usd": price}
    except Exception as e:
        return {"status": "error", "error": str(e)}

# -------- LOTE SERVER-SIDE ----------
def _run_batch(count: int, delay: float):
    BATCH_STATE.update({"running": True, "done": 0, "fail": 0, "target": count})
    for i in range(count):
        try:
            price = fetch_btc_price()
            ts = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
            upsert_price(ts, price)
            BATCH_STATE["done"] += 1
        except Exception as e:
            BATCH_STATE["fail"] += 1
        polite_sleep(delay)
    BATCH_STATE["running"] = False

@app.post("/ingest_batch")
def ingest_batch(count: int = 60, delay: float = 12.0, bg: BackgroundTasks = None):
    # warm-up: primeira chamada já “acorda” o Render
    if BATCH_STATE.get("running"):
        return {"status": "already_running", **BATCH_STATE}
    bg.add_task(_run_batch, count, delay)
    return {"status": "started", "count": count, "delay": delay}

@app.get("/batch/status")
def batch_status():
    return {"status": "running" if BATCH_STATE["running"] else "idle", **BATCH_STATE}

@app.post("/batch/stop")
def batch_stop():
    # simples: marca target = done para encerrar loop na próxima iteração
    if BATCH_STATE["running"]:
        BATCH_STATE["target"] = BATCH_STATE["done"]  # encerra
    return {"status": "stopping"}
