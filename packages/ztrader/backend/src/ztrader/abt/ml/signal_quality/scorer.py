"""
Signal Quality Scoring module.
Uses ML to evaluate trading signals before execution.
"""

import os
import pickle
from typing import Any, Dict, List

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler


class SignalQualityScorer:
    """ML-based signal quality scoring system."""

    def __init__(self, model_path: str = None):
        """
        Initialize the signal quality scorer.

        Args:
            model_path: Path to pre-trained model (optional)
        """
        self.model = RandomForestClassifier(
            n_estimators=100, max_depth=10, min_samples_split=10, random_state=42
        )
        self.scaler = StandardScaler()
        self.is_trained = False

        if model_path and os.path.exists(model_path):
            self.load_model(model_path)

    def train(
        self, historical_signals: List[Dict], outcomes: List[str]
    ) -> Dict[str, float]:
        """
        Train the signal quality scorer on historical data.

        Args:
            historical_signals: List of historical trading signals
            outcomes: List of outcomes ('WIN' or 'LOSS')

        Returns:
            Training metrics
        """
        from .feature_extractor import FeatureExtractor

        extractor = FeatureExtractor()
        features = [
            extractor.extract_signal_features(sig) for sig in historical_signals
        ]

        # Convert to numpy array
        X = np.array([[f[key] for key in sorted(f.keys())] for f in features])
        y = np.array([1 if outcome == "WIN" else 0 for outcome in outcomes])

        # Fit scaler and transform features
        X_scaled = self.scaler.fit_transform(X)

        # Train model
        self.model.fit(X_scaled, y)
        self.is_trained = True

        # Calculate training accuracy
        accuracy = self.model.score(X_scaled, y)

        return {"accuracy": accuracy, "samples": len(historical_signals)}

    def score_signal(
        self, signal: Dict[str, Any], market_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Score a trading signal.

        Args:
            signal: Trading signal to score
            market_data: Current market data (optional)

        Returns:
            Score result with confidence and recommendation
        """
        from .feature_extractor import FeatureExtractor

        if not self.is_trained:
            # Return neutral score if not trained
            return {
                "score": 0.5,
                "confidence": 0.0,
                "recommendation": "NEUTRAL",
                "factors": {},
                "risk": "UNKNOWN",
            }

        extractor = FeatureExtractor()
        features = extractor.extract_signal_features(signal, market_data)

        # Convert to array in sorted key order
        X = np.array([[features[key] for key in sorted(features.keys())]])
        X_scaled = self.scaler.transform(X)

        # Get probability predictions
        proba = self.model.predict_proba(X_scaled)[0]

        score = proba[1]  # Probability of winning trade
        confidence = max(proba)

        # Determine recommendation
        if score >= 0.7:
            recommendation = "EXECUTE"
            risk = "LOW"
        elif score >= 0.5:
            recommendation = "PROCEED_WITH_CAUTION"
            risk = "MODERATE"
        else:
            recommendation = "SKIP"
            risk = "HIGH"

        # Calculate factor contributions (simplified)
        factors = {
            "historicalWinRate": min(score * 1.1, 1.0),
            "marketCondition": score * 0.95,
            "riskRewardRatio": score * 1.05,
            "volumeAlignment": score * 0.98,
        }

        return {
            "score": float(score),
            "confidence": float(confidence),
            "recommendation": recommendation,
            "factors": factors,
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
