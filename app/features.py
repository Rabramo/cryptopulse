import pandas as pd
import numpy as np
from sqlalchemy import text
from .db import engine

def load_prices(limit: int = 2000) -> pd.DataFrame:
    q = f"SELECT ts_utc, price_usd FROM prices ORDER BY ts_utc DESC LIMIT {limit}"
    with engine.connect() as conn:
        df = pd.read_sql(text(q), conn)
    if df.empty: return df
    df = df[::-1].reset_index(drop=True)
    df["ts_utc"] = pd.to_datetime(df["ts_utc"], utc=True)
    return df

def make_features(df: pd.DataFrame, horizon=5):
    df = df.copy()
    df["ret1"] = np.log(df["price_usd"]).diff()
    df["ret3"] = np.log(df["price_usd"]).diff(3)
    df["vol5"] = df["ret1"].rolling(5).std()
    df["ma5"]  = df["price_usd"].rolling(5).mean()
    df["ma15"] = df["price_usd"].rolling(15).mean()
    df["mom5"] = df["price_usd"].diff(5)
    # target: sobe (1) se preço futuro em 5 passos > preço atual
    df["y"] = (df["price_usd"].shift(-horizon) > df["price_usd"]).astype(int)
    feat_cols = ["ret1","ret3","vol5","ma5","ma15","mom5"]
    df = df.dropna().reset_index(drop=True)
    X = df[feat_cols].values
    y = df["y"].values
    meta = {"feat_cols": feat_cols, "horizon": horizon}
    return X, y, df, meta
