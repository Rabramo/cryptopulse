# app/api.py (trecho)
from fastapi import FastAPI, BackgroundTasks, Query
from time import sleep
from app.ingestor import fetch_btc_price, polite_sleep
from app.db import upsert_price

app = FastAPI()
BATCH_STATE = {"running": False, "done": 0, "fail": 0, "target": 0}

def _run_batch(n: int, delay: float):
    BATCH_STATE.update({"running": True, "done": 0, "fail": 0, "target": n})
    for i in range(n):
        if not BATCH_STATE["running"]:
            break
        try:
            price = fetch_btc_price()
            upsert_price(price["ts_utc"], price["price_usd"])
            BATCH_STATE["done"] += 1
        except Exception:
            BATCH_STATE["fail"] += 1
        polite_sleep(delay)
    BATCH_STATE["running"] = False

@app.post("/ingest_batch")
def ingest_batch(count: int = Query(60, ge=1, le=1000), delay: float = Query(12.0, ge=1.0)):
    if BATCH_STATE["running"]:
        return {"status": "already_running", **BATCH_STATE}
    from fastapi import BackgroundTasks
    bg = BackgroundTasks()
    bg.add_task(_run_batch, count, delay)
    # FastAPI: retorne a tarefa *ou* simplesmente dispare e retorne ok
    _ = bg  # se preferir gerenciar manualmente
    import threading
    threading.Thread(target=_run_batch, args=(count, delay), daemon=True).start()
    return {"status": "started", "target": count, "delay": delay}

@app.get("/batch/status")
def batch_status():
    return {"status": "ok", **BATCH_STATE}

@app.post("/batch/stop")
def batch_stop():
    BATCH_STATE["running"] = False
    return {"status": "stopping", **BATCH_STATE}

