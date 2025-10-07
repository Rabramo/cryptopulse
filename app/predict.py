import joblib, os, numpy as np
from .features import load_prices, make_features
MODEL_PATH = os.path.join("models","model.pkl")

def predict_now():
    if not os.path.exists(MODEL_PATH):
        return {"status":"no_model"}
    bundle = joblib.load(MODEL_PATH)
    model, meta = bundle["model"], bundle["meta"]
    df = load_prices()
    if df.shape[0] < 20:
        return {"status":"not_enough_data"}
    X, y, df_feat, _ = make_features(df, horizon=meta["horizon"])
    x_last = X[-1].reshape(1, -1)
    proba_up = float(model.predict_proba(x_last)[0,1])
    return {
        "status":"ok",
        "proba_up_next_%d" % meta["horizon"]: proba_up,
        "latest_ts": df_feat["ts_utc"].iloc[-1].isoformat(),
        "latest_price": float(df_feat["price_usd"].iloc[-1])
    }
