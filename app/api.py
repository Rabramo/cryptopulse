# -----------------------------
# Batch server-side (refatorado)
# -----------------------------
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Dict, Any

from fastapi import Query
from app.ingestor import fetch_btc_price, polite_sleep
from app.db import upsert_price

log = logging.getLogger("cryptopulse.batch")

# Estado do batch com lock para evitar race conditions
BATCH_STATE: Dict[str, Any] = {
    "running": False,     # loop ativo
    "done": 0,            # coletas com sucesso
    "fail": 0,            # falhas
    "target": 0,          # total desejado
    "delay": None,        # intervalo solicitado (s)
    "started_at": None,   # ISO UTC do início
    "updated_at": None,   # ISO UTC última atualização
    "last_error": None,   # última exception textual
}
_BS_LOCK = threading.Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _run_batch(n: int, delay: float) -> None:
    """Laço do batch rodando no servidor (thread daemon)."""
    with _BS_LOCK:
        BATCH_STATE.update(
            {
                "running": True,
                "done": 0,
                "fail": 0,
                "target": int(n),
                "delay": float(delay),
                "started_at": _now_iso(),
                "updated_at": _now_iso(),
                "last_error": None,
            }
        )

    for _ in range(int(n)):
        with _BS_LOCK:
            if not BATCH_STATE["running"]:
                break

        try:
            price = fetch_btc_price()
            upsert_price(price["ts_utc"], price["price_usd"])
            with _BS_LOCK:
                BATCH_STATE["done"] += 1
                BATCH_STATE["updated_at"] = _now_iso()
        except Exception as e:
            log.exception("Falha em uma iteração do batch")
            with _BS_LOCK:
                BATCH_STATE["fail"] += 1
                BATCH_STATE["last_error"] = str(e)
                BATCH_STATE["updated_at"] = _now_iso()

        # Respeita limites e evita bursts
        polite_sleep(delay)

    with _BS_LOCK:
        BATCH_STATE["running"] = False
        BATCH_STATE["updated_at"] = _now_iso()


@app.post(
    "/ingest_batch",
    tags=["Batch"],
    summary="Inicia lote de coletas no servidor",
)
def ingest_batch(
    count: int = Query(
        60,
        ge=1,
        le=2000,
        description="Quantidade de coletas a executar (1–2000).",
    ),
    delay: float = Query(
        12.0,
        ge=1.0,
        le=600.0,
        description="Intervalo (segundos) entre coletas.",
    ),
):
    """Dispara uma *thread* daemon que executa `count` coletas com `delay` entre elas."""
    with _BS_LOCK:
        if BATCH_STATE["running"]:
            return {"status": "already_running", **BATCH_STATE}

    t = threading.Thread(target=_run_batch, args=(count, delay), daemon=True)
    t.start()
    return {
        "status": "started",
        "target": int(count),
        "delay": float(delay),
        "started_at": _now_iso(),
    }


@app.get(
    "/batch/status",
    tags=["Batch"],
    summary="Consulta status atual do lote",
)
def batch_status():
    with _BS_LOCK:
        state = dict(BATCH_STATE)  # cópia rasa segura
    # ETA simples (restante * delay)
    remaining = max(0, int(state.get("target") or 0) - int(state.get("done") or 0))
    delay = float(state.get("delay") or 0.0)
    eta_seconds = int(remaining * delay) if state.get("running") and delay > 0 else 0
    return {"status": "ok", "eta_seconds": eta_seconds, **state}


@app.post(
    "/batch/stop",
    tags=["Batch"],
    summary="Solicita parada graciosa do lote",
)
def batch_stop():
    with _BS_LOCK:
        BATCH_STATE["running"] = False
        BATCH_STATE["updated_at"] = _now_iso()
    return {"status": "stopping", **BATCH_STATE}


@app.post(
    "/batch/reset",
    tags=["Batch"],
    summary="Reseta estado do lote (útil para testes)",
)
def batch_reset():
    with _BS_LOCK:
        BATCH_STATE.update(
            {
                "running": False,
                "done": 0,
                "fail": 0,
                "target": 0,
                "delay": None,
                "started_at": None,
                "updated_at": _now_iso(),
                "last_error": None,
            }
        )
    return {"status": "reset", **BATCH_STATE}
