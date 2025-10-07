from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import (
    BackgroundTasks,
    FastAPI,
    HTTPException,
    Query,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import text

from app.db import engine, init_db, upsert_price
from app.ingestor import fetch_btc_price, polite_sleep
from app.features import load_prices, make_features  # mantidos se usados por /train
from app.train import train_model

# predict_next é opcional (evita crash se não existir)
try:
    from app.predict import predict_next as _predict_next  # type: ignore[attr-defined]
except Exception:
    _predict_next = None

log = logging.getLogger("cryptopulse.api")

# =============================================================================
# App & CORS
# =============================================================================
app = FastAPI(
    title="CryptoPulse API",
    version="1.2",
    description="API para coleta de preço BTC, treino/predição e operações em lote.",
)

# Suporte a *.streamlit.app via regex de origem
ALLOW_ORIGIN_REGEX = r"^https:\/\/([a-z0-9-]+\.)*streamlit\.app$"

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=ALLOW_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================================
# Models (Pydantic)
# =============================================================================
class RootResp(BaseModel):
    name: str = "cryptopulse"
    status: str = "ok"
    time_utc: str


class IngestResp(BaseModel):
    status: str
    ts_utc: Optional[str] = None
    price_usd: Optional[float] = None
    msg: Optional[str] = None


class TrainResp(BaseModel):
    status: str
    acc_test: Optional[float] = None
    n_train: Optional[int] = None
    n_test: Optional[int] = None
    n_rows: Optional[int] = None
    msg: Optional[str] = None


class PredictResp(BaseModel):
    status: str
    proba_up_next_5: Optional[float] = None
    msg: Optional[str] = None


class Row(BaseModel):
    ts_utc: str
    price_usd: float


class ListResp(BaseModel):
    status: str
    data: List[Row]


# =============================================================================
# Helpers
# =============================================================================
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _normalize_fetch_output(d: Any) -> Dict[str, Any]:
    """
    Normaliza a saída do fetch:
    - Se vier float/int: gera ts_utc=agora e price_usd=float(valor)
    - Se vier dict: exige price_usd e opcionalmente usa ts_utc fornecido
    """
    if isinstance(d, dict):
        ts = d.get("ts_utc") or _now_iso()
        price = float(d["price_usd"])
        return {"ts_utc": ts, "price_usd": price}
    return {"ts_utc": _now_iso(), "price_usd": float(d)}


def _do_one_ingest() -> Dict[str, Any]:
    """Executa uma coleta e persiste (upsert). Retorna payload pronto para IngestResp."""
    raw = fetch_btc_price()
    p = _normalize_fetch_output(raw)
    upsert_price(p["ts_utc"], p["price_usd"])
    return {"status": "ok", "ts_utc": p["ts_utc"], "price_usd": float(p["price_usd"])}


# =============================================================================
# Startup
# =============================================================================
@app.on_event("startup")
def _startup():
    try:
        init_db()
        log.info("DB inicializado com sucesso")
    except Exception as e:  # pragma: no cover
        log.exception("Falha ao inicializar DB")
        # Opcional: propagar erro para falhar o container em ambientes que exigem readiness estrito
        # raise


# =============================================================================
# Endpoints principais
# =============================================================================
@app.get(
    "/",
    response_model=RootResp,
    tags=["default"],
    summary="Root",
    response_model_exclude_none=True,
)
def root():
    return RootResp(time_utc=_now_iso())


@app.post(
    "/ingest_async",
    response_model=IngestResp,
    tags=["default"],
    summary="Dispara coleta em background",
    status_code=status.HTTP_202_ACCEPTED,      # 202: aceitei e vou processar depois
    response_model_exclude_none=True,          # oculta chaves com None
)
def ingest_async(bg: BackgroundTasks):
    """
    Agenda uma coleta em background e responde imediatamente.
    Use /ingest para execução síncrona que retorna ts_utc e price_usd.
    """
    try:
        bg.add_task(_do_one_ingest)
        return IngestResp(status="accepted", msg="ingest agendado")
    except Exception as e:
        log.exception("Falha no ingest_async")
        raise HTTPException(status_code=503, detail=f"ingest indisponível: {e}")


@app.post(
    "/ingest",
    response_model=IngestResp,
    tags=["default"],
    summary="Coleta 1 leitura (síncrono)",
    status_code=status.HTTP_200_OK,
    response_model_exclude_none=True,
)
def ingest_once_sync():
    """
    Executa a coleta e só responde depois de persistir,
    garantindo ts_utc e price_usd no corpo da resposta.
    """
    try:
        return IngestResp(**_do_one_ingest())
    except Exception as e:
        log.exception("Falha no ingest síncrono")
        raise HTTPException(status_code=502, detail=f"falha na coleta: {e}")


@app.post(
    "/train",
    response_model=TrainResp,
    tags=["default"],
    summary="Train",
    response_model_exclude_none=True,
)
def train():
    """Treina o modelo (mínimo definido em train_model())."""
    try:
        res = train_model()
        # Esperado: res já no formato compatível com TrainResp
        return TrainResp(**res)
    except Exception as e:
        log.exception("Falha no treino")
        raise HTTPException(status_code=500, detail=f"falha no treino: {e}")


@app.get(
    "/predict",
    response_model=PredictResp,
    tags=["default"],
    summary="Predict",
    response_model_exclude_none=True,
)
def predict():
    """Prediz probabilidade de alta em 5min (se `predict_next` existir e retornar probabilidade)."""
    try:
        if _predict_next is None:
            raise HTTPException(status_code=503, detail="predict_next indisponível no servidor.")

        res: Dict[str, Any] = _predict_next({"horizon": 5})

        # Caminho 1: chave explícita
        if isinstance(res, dict) and "proba_up_next_5" in res:
            return PredictResp(status="ok", proba_up_next_5=float(res["proba_up_next_5"]))

        # Caminho 2: lista de predictions
        if isinstance(res, dict) and "prediction" in res:
            pred = res["prediction"]
            if isinstance(pred, list) and pred:
                return PredictResp(status="ok", proba_up_next_5=float(pred[0]))

        # Sem dado útil -> falha de dependência (predict não retornou probabilidade)
        raise HTTPException(status_code=424, detail="predict_next não retornou probabilidade.")
    except HTTPException:
        raise
    except Exception as e:
        log.exception("Falha na predição")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/data/last",
    response_model=ListResp,
    tags=["default"],
    summary="Últimas leituras",
    response_model_exclude_none=True,
)
def last(n: int = Query(300, ge=1, le=5000)):
    """Retorna as últimas N leituras (ASC). Se vazio, devolve status='empty' e data=[]."""
    try:
        with engine.begin() as c:
            rows = c.execute(
                text(
                    """
                    SELECT ts_utc, price_usd
                    FROM prices
                    ORDER BY ts_utc ASC
                    OFFSET GREATEST( (SELECT COUNT(*) FROM prices) - :n, 0 )
                    """
                ),
                {"n": n},
            ).mappings().all()

        data = [Row(ts_utc=r["ts_utc"], price_usd=float(r["price_usd"])) for r in rows]
        status_str = "ok" if data else "empty"
        return ListResp(status=status_str, data=data)
    except Exception as e:
        log.exception("Falha em /data/last")
        raise HTTPException(status_code=500, detail=f"Falha ao consultar as últimas leituras: {e}")


# =============================================================================
# Batch server-side (coleta em lote)
# =============================================================================
BATCH_STATE: Dict[str, Any] = {
    "running": False,
    "done": 0,
    "fail": 0,
    "target": 0,
    "delay": None,
    "started_at": None,
    "updated_at": None,
    "last_error": None,
}
_BS_LOCK = threading.Lock()


def _run_batch(n: int, delay: float) -> None:
    def _set(**kw):
        with _BS_LOCK:
            BATCH_STATE.update(kw)
            BATCH_STATE["updated_at"] = _now_iso()

    _set(
        running=True,
        done=0,
        fail=0,
        target=int(n),
        delay=float(delay),
        started_at=_now_iso(),
        last_error=None,
    )

    for _ in range(int(n)):
        with _BS_LOCK:
            if not BATCH_STATE["running"]:
                break
        try:
            p = _normalize_fetch_output(fetch_btc_price())
            upsert_price(p["ts_utc"], p["price_usd"])
            _set(done=BATCH_STATE["done"] + 1)
        except Exception as e:
            log.exception("Falha em uma iteração do batch")
            _set(fail=BATCH_STATE["fail"] + 1, last_error=f"{type(e).__name__}: {e}")
        polite_sleep(delay)

    _set(running=False)


@app.post(
    "/ingest_batch",
    tags=["Batch"],
    summary="Inicia lote no servidor",
)
def ingest_batch(
    count: int = Query(60, ge=1, le=2000, description="Quantidade de coletas (1–2000)."),
    delay: float = Query(12.0, ge=1.0, le=600.0, description="Intervalo entre coletas (s)."),
):
    with _BS_LOCK:
        if BATCH_STATE["running"]:
            return {"status": "already_running", **BATCH_STATE}
    threading.Thread(target=_run_batch, args=(count, delay), daemon=True).start()
    return {"status": "started", "target": int(count), "delay": float(delay), "started_at": _now_iso()}


@app.get(
    "/batch/status",
    tags=["Batch"],
    summary="Status do lote",
)
def batch_status():
    with _BS_LOCK:
        state = dict(BATCH_STATE)
    remaining = max(0, int(state.get("target") or 0) - int(state.get("done") or 0))
    d = float(state.get("delay") or 0.0)
    eta_seconds = int(remaining * d) if state.get("running") and d > 0 else 0
    return {"status": "ok", "eta_seconds": eta_seconds, **state}


@app.post(
    "/batch/stop",
    tags=["Batch"],
    summary="Parada graciosa do lote",
)
def batch_stop():
    with _BS_LOCK:
        BATCH_STATE["running"] = False
        BATCH_STATE["updated_at"] = _now_iso()
    return {"status": "stopping", **BATCH_STATE}


@app.post(
    "/batch/reset",
    tags=["Batch"],
    summary="Reset do estado do lote (testes/CI)",
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
