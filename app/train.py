import joblib
import os
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.metrics import accuracy_score
from .features import load_prices, make_features

MODEL_PATH = os.path.join("models", "model.pkl")
os.makedirs("models", exist_ok=True)

def train_model():
    df = load_prices()
    if df.shape[0] < 60:
        return {"status":"not_enough_data","n_rows":int(df.shape[0])}
    X, y, df_feat, meta = make_features(df)
    if len(np.unique(y)) < 2:
        return {"status":"single_class","msg":"target sem variação suficiente"}
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.25, shuffle=False)
    pipe = Pipeline([("scaler", StandardScaler()),
                     ("clf", LogisticRegression(max_iter=1000))])
    pipe.fit(Xtr, ytr)
    acc = accuracy_score(yte, pipe.predict(Xte))
    joblib.dump({"model": pipe, "meta": meta}, MODEL_PATH)
    return {"status":"ok","acc_test":float(acc),"n_train":int(len(ytr)),"n_test":int(len(yte))}
