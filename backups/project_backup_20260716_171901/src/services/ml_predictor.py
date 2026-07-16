import logging
from typing import Dict, Any, Optional

import pandas as pd


class MLPredictor:
    """
    XGBoost tabanlı yön tahminleyici.
    Fallback: sklearn GradientBoostingClassifier
    """

    def __init__(self):
        self.logger = logging.getLogger("services.ml_predictor")
        self.model = None
        self.backend = None
        self._init_model()

    def _init_model(self):
        try:
            from xgboost import XGBClassifier  # type: ignore

            self.model = XGBClassifier(
                n_estimators=200,
                max_depth=4,
                learning_rate=0.05,
                subsample=0.9,
                colsample_bytree=0.9,
                objective="binary:logistic",
                eval_metric="logloss",
                random_state=42,
            )
            self.backend = "xgboost"
            self.logger.info("ML backend: xgboost")
        except Exception:
            from sklearn.ensemble import GradientBoostingClassifier

            self.model = GradientBoostingClassifier(random_state=42)
            self.backend = "sklearn_gb"
            self.logger.warning("xgboost bulunamadı, fallback backend: sklearn_gb")

    def train(self, X: pd.DataFrame, y: pd.Series):
        if len(X) < 50:
            self.logger.warning("Model eğitimi için veri az, eğitim atlandı.")
            return
        self.model.fit(X, y)

    def predict_next(self, latest_features: pd.DataFrame) -> Dict[str, Any]:
        if latest_features.empty:
            return {"direction": "HOLD", "prob_up": 0.5, "prob_down": 0.5}

        x_last = latest_features.tail(1)

        if hasattr(self.model, "predict_proba"):
            proba = self.model.predict_proba(x_last)[0]
            prob_down = float(proba[0])
            prob_up = float(proba[1])
        else:
            pred = int(self.model.predict(x_last)[0])
            prob_up = 0.6 if pred == 1 else 0.4
            prob_down = 1.0 - prob_up

        if prob_up > 0.55:
            direction = "LONG"
        elif prob_down > 0.55:
            direction = "SHORT"
        else:
            direction = "HOLD"

        return {
            "direction": direction,
            "prob_up": prob_up,
            "prob_down": prob_down,
            "backend": self.backend,
        }
