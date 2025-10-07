from fastapi import FastAPI
from .db import init_db
from .ingestor import fetch_and_store
from .train import train_model
from .predict import predict_now
from .features import load_prices

app = FastAPI(title="CryptoPulse API", version="1.0")

@app.on_event("startup")
def _startup():
    init_db()

@app.get("/")
def root():
    return {"ok": True, "service": "CryptoPulse"}

@app.post("/ingest")
def ingest_once():
    try:
        out = fetch_and_store()
        return {"status": "ok", **out}
    except Exception as e:
        # status 502: erro na fonte externa
        raise HTTPException(status_code=502, detail=f"Ingest failed: {e}")

@app.post("/train")
def train():
    return train_model()

@app.get("/predict")
def predict():
    return predict_now()

@app.get("/data/last")
def last(n:int=200):
    df = load_prices(limit=n)
    return {"rows": len(df), "data": df.to_dict(orient="records")}