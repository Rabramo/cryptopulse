# app/predict.py
from __future__ import annotations

import os
from typing import Any, Dict, Tuple, Optional, List, Union

import joblib
import numpy as np

from .features import load_prices, make_features

# Permite sobrescrever o caminho via variável de ambiente (útil no Render/Docker)
MODEL_PATH = os.getenv("MODEL_PATH", os.path.join("models", "model.pkl"))

JsonDict = Dict[str, Any]


def _load_model_bundle(path: str = MODEL_PATH) -> Tuple[Any, Dict[str, Any]]:
    """
    Carrega o bundle salvo com joblib: {"model": <estimador>, "meta": {...}}.

    Levanta ValueError se a estrutura do bundle estiver inválida.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(path)

    try:
        bundle = joblib.load(path, mmap_mode="r")
    except Exception as exc:
        raise RuntimeError(f"Falha ao carregar modelo: {exc}") from exc

    if not isinstance(bundle, dict) or "model" not in bundle or "meta" not in bundle:
        raise ValueError("Bundle inválido: esperado dict com chaves 'model' e 'meta'.")

    model = bundle["model"]
    meta = bundle["meta"]
    if not isinstance(meta, dict):
        raise ValueError("Campo 'meta' deve ser um dict.")

    if "horizon" not in meta:
        raise ValueError("Meta sem 'horizon'.")

    return model, meta


def _latest_ts_iso(ts_val: Any) -> str:
    """
    Converte timestamp/Datetime para ISO 8601. Tolerante a valores timezone-naive.
    """
    try:
        # pandas Timestamp tem .isoformat(); datetime também
        return ts_val.isoformat()
    except AttributeError:
        # fallback: str simples
        return str(ts_val)


def _predict_proba_or_value(model: Any, X_last: np.ndarray) -> JsonDict:
    """
    Tenta obter probabilidade (classificação binária). Se o modelo não expõe
    predict_proba, retorna previsão direta (regressão).
    """
    # Classificador com predict_proba (2 classes)
    if hasattr(model, "predict_proba"):
        proba = model.predict_proba(X_last)
        # Assume segunda coluna como "classe 1 / alta"
        proba_up = float(proba[0, 1])
        return {"kind": "classifier", "proba_up": proba_up}

    # DecisionFunction (SVM/LinearSVC etc.)
    if hasattr(model, "decision_function"):
        score = float(model.decision_function(X_last)[0])
        return {"kind": "classifier_margin", "margin": score}

    # Regressor
    if hasattr(model, "predict"):
        y_hat = float(model.predict(X_last)[0])
        return {"kind": "regressor", "y_hat": y_hat}

    raise ValueError("Modelo não suporta predict_proba, decision_function ou predict.")


def _build_features(horizon: int) -> Dict[str, Any]:
    """
    Carrega preços e monta features para o horizonte solicitado.
    Retorna dicionário com X, y, df_feat e info mínima.
    """
    df = load_prices()
    if df.shape[0] < 20:
        return {"status": "not_enough_data"}

    X, y, df_feat, _misc = make_features(df, horizon=horizon)
    if X is None or len(X) == 0:
        return {"status": "no_features"}

    x_last = np.asarray(X[-1]).reshape(1, -1)

    # Checagens de colunas esperadas no df_feat (não quebra se ausentes)
    ts_col = "ts_utc" if "ts_utc" in df_feat.columns else df_feat.columns[-1]
    price_col = "price_usd" if "price_usd" in df_feat.columns else df_feat.columns[0]

    latest_ts = _latest_ts_iso(df_feat[ts_col].iloc[-1])
    latest_price = float(df_feat[price_col].iloc[-1])

    return {
        "status": "ok",
        "X_last": x_last,
        "latest_ts": latest_ts,
        "latest_price": latest_price,
    }


def predict_now() -> JsonDict:
    """
    Usa o modelo salvo e a fonte de dados corrente para estimar o próximo passo.
    Retorna estrutura estável com 'status' e campos auxiliares.
    """
    try:
        model, meta = _load_model_bundle()
    except FileNotFoundError:
        return {"status": "no_model"}
    except Exception as exc:
        return {"status": "load_error", "error": str(exc)}

    horizon = int(meta.get("horizon", 1))

    feat = _build_features(horizon=horizon)
    if feat.get("status") != "ok":
        return feat  # Propaga 'not_enough_data' ou 'no_features'

    try:
        out = _predict_proba_or_value(model, feat["X_last"])
    except Exception as exc:
        return {"status": "predict_error", "error": str(exc)}

    payload: JsonDict = {
        "status": "ok",
        "horizon": horizon,
        "latest_ts": feat["latest_ts"],
        "latest_price": feat["latest_price"],
    }

    # Normaliza chaves de saída
    if out["kind"] == "classifier":
        payload[f"proba_up_next_{horizon}"] = out["proba_up"]
    elif out["kind"] == "classifier_margin":
        payload[f"margin_next_{horizon}"] = out["margin"]
    else:  # regressor
        payload[f"yhat_next_{horizon}"] = out["y_hat"]

    return payload


def predict_next(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Endpoint genérico chamado pela API.
    - Tenta usar o modelo salvo com o horizonte solicitado em 'payload["horizon"]'.
    - Se não houver modelo, cai para um stub ingênuo baseado na última observação de 'series'.
    """
    # 1) Tenta com modelo salvo
    try:
        model, meta = _load_model_bundle()
        horizon = int(payload.get("horizon", meta.get("horizon", 1)))
        feat = _build_features(horizon=horizon)
        if feat.get("status") != "ok":
            raise RuntimeError(feat.get("status"))  # cai para stub

        out = _predict_proba_or_value(model, feat["X_last"])

        if out["kind"] == "classifier":
            prediction = [out["proba_up"]]  # probabilidade de alta num único passo
            meta_out = {
                "source": "model",
                "type": "classifier_proba",
                "latest_ts": feat["latest_ts"],
                "latest_price": feat["latest_price"],
            }
        elif out["kind"] == "classifier_margin":
            prediction = [out["margin"]]
            meta_out = {
                "source": "model",
                "type": "classifier_margin",
                "latest_ts": feat["latest_ts"],
                "latest_price": feat["latest_price"],
            }
        else:  # regressor
            prediction = [out["y_hat"]]
            meta_out = {
                "source": "model",
                "type": "regressor",
                "latest_ts": feat["latest_ts"],
                "latest_price": feat["latest_price"],
            }

        return {"prediction": prediction * horizon, "metadata": meta_out}

    except Exception:
        # 2) Stub ingênuo: repete o último valor da série (se houver)
        horizon = int(payload.get("horizon", 1))
        series: List[Union[int, float]] = payload.get("series") or []
        last = float(series[-1]) if series else 0.0
        return {
            "prediction": [last] * horizon,
            "metadata": {"source": "stub", "reason": "no_model_or_feature_error"},
        }
