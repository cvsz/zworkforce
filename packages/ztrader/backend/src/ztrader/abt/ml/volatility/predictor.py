"""
Volatility prediction using machine learning.
"""

import os
import pickle
from typing import Any, Dict, List

import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler


class VolatilityPredictor:
    """ML-based volatility prediction system."""

    def __init__(self, model_path: str = None):
        """
        Initialize the volatility predictor.

        Args:
            model_path: Path to pre-trained model (optional)
        """
        self.model = RandomForestRegressor(
            n_estimators=100, max_depth=15, min_samples_split=5, random_state=42
        )
        self.scaler = StandardScaler()
        self.is_trained = False

        if model_path and os.path.exists(model_path):
            self.load_model(model_path)

    def train(
        self, historical_data: List[Dict], realized_volatility: List[float]
    ) -> Dict[str, float]:
        """
        Train the volatility predictor on historical data.

        Args:
            historical_data: List of historical market data
            realized_volatility: List of realized volatility values

        Returns:
            Training metrics
        """
        from .features import VolatilityFeatures

        extractor = VolatilityFeatures()
        features = [extractor.extract(data) for data in historical_data]

        # Convert to numpy array
        X = np.array([[f[key] for key in sorted(f.keys())] for f in features])
        y = np.array(realized_volatility)

        # Fit scaler and transform features
        X_scaled = self.scaler.fit_transform(X)

        # Train model
        self.model.fit(X_scaled, y)
        self.is_trained = True

        # Calculate training metrics
        predictions = self.model.predict(X_scaled)
        mae = np.mean(np.abs(predictions - y))
        rmse = np.sqrt(np.mean((predictions - y) ** 2))

        return {"mae": float(mae), "rmse": float(rmse), "samples": len(historical_data)}

    def predict_volatility(
        self, market_data: Dict[str, Any], horizon: int = 24
    ) -> Dict[str, Any]:
        """
        Predict future volatility.

        Args:
            market_data: Current market data
            horizon: Prediction horizon in hours

        Returns:
            Volatility prediction with confidence interval
        """
        from .features import VolatilityFeatures

        if not self.is_trained:
            # Return default volatility if not trained
            return {
                "predicted": 0.02,
                "confidence": 0.0,
                "range": {"low": 0.015, "high": 0.025},
                "horizon": horizon,
                "regime": "UNKNOWN",
                "risk": "MODERATE",
            }

        extractor = VolatilityFeatures()
        features = extractor.extract(market_data)

        # Convert to array in sorted key order
        X = np.array([[features[key] for key in sorted(features.keys())]])
        X_scaled = self.scaler.transform(X)

        # Get prediction
        predicted_vol = self.model.predict(X_scaled)[0]

        # Get confidence interval from individual trees
        tree_predictions = np.array(
            [tree.predict(X_scaled)[0] for tree in self.model.estimators_]
        )

        confidence = (
            1 - (np.std(tree_predictions) / np.mean(tree_predictions))
            if np.mean(tree_predictions) > 0
            else 0
        )
        lower = np.percentile(tree_predictions, 10)
        upper = np.percentile(tree_predictions, 90)

        # Determine volatility regime
        current_vol = features.get("realized_vol_24h", 0.02)
        if predicted_vol > current_vol * 1.2:
            regime = "INCREASING_VOLATILITY"
            risk = "HIGH"
        elif predicted_vol < current_vol * 0.8:
            regime = "DECREASING_VOLATILITY"
            risk = "LOW"
        else:
            regime = "STABLE_VOLATILITY"
            risk = "MODERATE"

        return {
            "predicted": float(predicted_vol),
            "confidence": float(max(0, min(1, confidence))),
            "range": {"low": float(lower), "high": float(upper)},
            "horizon": horizon,
            "regime": regime,
            "risk": risk,
            "features": features,
        }

    def save_model(self, path: str):
        """Save trained model to file."""
        os.makedirs(os.path.dirname(path), exist_ok=True)

        model_data = {
            "model": self.model,
            "scaler": self.scaler,
            "is_trained": self.is_trained,
        }

        with open(path, "wb") as f:
            pickle.dump(model_data, f)

    def load_model(self, path: str):
        """Load trained model from file."""
        with open(path, "rb") as f:
            model_data = pickle.load(f)

        self.model = model_data["model"]
        self.scaler = model_data["scaler"]
        self.is_trained = model_data["is_trained"]
