# app/train.py
import os
import time
import joblib
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.metrics import accuracy_score

from .features import load_prices, make_features

MODEL_PATH = os.path.join("models", "model.pkl")
os.makedirs("models", exist_ok=True)

# mínimo de linhas para liberar treino (padrão 120)
MIN_TRAIN_ROWS = int(os.environ.get("MIN_TRAIN_ROWS", "120"))
RANDOM_STATE = int(os.environ.get("RANDOM_STATE", "42"))

def train_model():
    # 1) carrega dados brutos
    df = load_prices()
    n_rows = int(df.shape[0])
    if n_rows < MIN_TRAIN_ROWS:
        return {
            "status": "not_enough_data",
            "n_rows": n_rows,
            "min_required": MIN_TRAIN_ROWS
        }

    # 2) engenharia de atributos / target
    X, y, df_feat, meta = make_features(df)

    # 3) sanity checks do target
    classes, counts = np.unique(y, return_counts=True)
    if len(classes) < 2:
        return {
            "status": "single_class",
            "msg": "target sem variação suficiente",
            "class": int(classes[0]),
            "count": int(counts[0])
        }
    # opcional: exigir ao menos 3 exemplos da minoria
    if counts.min() < 3:
        return {
            "status": "too_imbalanced",
            "msg": "classe minoritária com menos de 3 exemplos",
            "counts": {int(c): int(n) for c, n in zip(classes, counts)}
        }

    # 4) split temporal (sem embaralhar)
    Xtr, Xte, ytr, yte = train_test_split(
        X, y, test_size=0.25, shuffle=False
    )

    # 5) pipeline
    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression(max_iter=1000, random_state=RANDOM_STATE))
    ])

    # 6) treino e avaliação
    pipe.fit(Xtr, ytr)
    yhat = pipe.predict(Xte)
    acc = float(accuracy_score(yte, yhat))

    # 7) salvar artefato + metadados
    artifact = {
        "model": pipe,
        "meta": {
            **meta,
            "trained_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "n_rows_raw": n_rows,
            "n_train": int(len(ytr)),
            "n_test": int(len(yte)),
            "classes": [int(c) for c in classes],
            "counts": [int(n) for n in counts],
            "acc_test": acc,
            "random_state": RANDOM_STATE,
        }
    }
    joblib.dump(artifact, MODEL_PATH)

    return {
        "status": "ok",
        "acc_test": acc,
        "n_train": int(len(ytr)),
        "n_test": int(len(yte)),
        "model_path": MODEL_PATH
    }
