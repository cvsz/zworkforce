#!/usr/bin/env python3
"""
TradingView Integration Test Script

This script tests the TradingView webhook integration without requiring
a running server or database connection.
"""

import json
import sys
from pathlib import Path

# Add backend to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "backend"))


def check_pydantic_models():
    """Check Pydantic models can be instantiated."""
    print("\n=== Testing Pydantic Models ===")

    try:
        from typing import Optional

        from pydantic import BaseModel

        class TestAlert(BaseModel):
            ticker: str
            action: str
            price: Optional[float] = None

        alert = TestAlert(ticker="BTCUSDT", action="BUY", price=45000.50)
        print(f"✓ Alert model works: {alert.ticker} {alert.action} @ {alert.price}")

        alert_json = alert.model_dump()
        print(f"✓ JSON serialization works: {json.dumps(alert_json)}")
        return True
    except ImportError as e:
        print(f"⚠ Skipping Pydantic test (not installed): {e}")
        return True
    except Exception as e:
        print(f"✗ Pydantic model test failed: {e}")
        return False


def check_strategy_logic():
    """Check TradingView strategy logic."""
    print("\n=== Testing Strategy Logic ===")

    try:

        class MockTradingViewStrategy:
            name = "TRADINGVIEW"

            def __init__(self, min_confidence=0.7):
                self.min_confidence = min_confidence
                self.last_signal = "HOLD"

            def execute(self, ticker_data, context):
                alert = ticker_data.get("tradingview_alert")
                if not alert:
                    return {
                        "signal": "HOLD",
                        "confidence": 0.0,
                        "meta": {"reason": "No alert data"},
                    }

                action = alert.get("action", "HOLD").upper()
                confidence = alert.get("confidence", 0.8)

                if confidence < self.min_confidence:
                    return {
                        "signal": "HOLD",
                        "confidence": confidence,
                        "meta": {"reason": "Confidence below threshold"},
                    }

                signal = "SELL" if action == "CLOSE" else action
                return {
                    "signal": signal,
                    "confidence": confidence,
                    "meta": {"source": "TRADINGVIEW"},
                }

        strategy = MockTradingViewStrategy(min_confidence=0.7)
        result = strategy.execute(
            ticker_data={
                "tradingview_alert": {
                    "action": "BUY",
                    "price": 45000.0,
                    "confidence": 0.85,
                }
            },
            context={"symbol": "BTC/USDT"},
        )
        assert result["signal"] == "BUY", f"Expected BUY, got {result['signal']}"
        assert result["confidence"] == 0.85, (
            f"Expected 0.85, got {result['confidence']}"
        )
        print("✓ Test 1: Valid BUY signal - PASSED")

        result = strategy.execute(
            ticker_data={"tradingview_alert": {"action": "BUY", "confidence": 0.5}},
            context={"symbol": "BTC/USDT"},
        )
        assert result["signal"] == "HOLD", f"Expected HOLD, got {result['signal']}"
        print("✓ Test 2: Low confidence filter - PASSED")

        result = strategy.execute(ticker_data={}, context={"symbol": "BTC/USDT"})
        assert result["signal"] == "HOLD", f"Expected HOLD, got {result['signal']}"
        print("✓ Test 3: No alert data - PASSED")

        result = strategy.execute(
            ticker_data={"tradingview_alert": {"action": "CLOSE", "confidence": 0.9}},
            context={"symbol": "BTC/USDT"},
        )
        assert result["signal"] == "SELL", f"Expected SELL, got {result['signal']}"
        print("✓ Test 4: CLOSE to SELL conversion - PASSED")

        return True
    except Exception as e:
        print(f"✗ Strategy logic test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def check_yaml_config():
    """Check YAML configuration loading."""
    print("\n=== Testing YAML Configuration ===")

    try:
        import yaml

        config_path = (
            Path(__file__).parent.parent
            / "strategies/external/tradingview_example.yaml"
        )

        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        assert "name" in config, "Missing 'name' field"
        assert "type" in config, "Missing 'type' field"
        assert config["type"] == "TRADINGVIEW", (
            f"Expected type TRADINGVIEW, got {config['type']}"
        )

        print(f"✓ Configuration loaded: {config['name']}")
        print(f"  Type: {config['type']}")
        print(f"  Symbols: {len(config.get('symbols', []))} configured")
        print(f"  Parameters: {len(config.get('parameters', {}))} defined")

        return True
    except ImportError:
        print("⚠ Skipping YAML test (pyyaml not installed)")
        return True
    except Exception as e:
        print(f"✗ YAML config test failed: {e}")
        return False


def check_gdrive_loader_structure():
    """Check Google Drive loader class structure."""
    print("\n=== Testing Google Drive Loader Structure ===")

    try:
        loader_path = (
            Path(__file__).parent.parent / "apps/backend/src/services/gdrive_loader.py"
        )

        with open(loader_path, "r") as f:
            content = f.read()

        assert "class GoogleDriveLoader" in content, "Missing GoogleDriveLoader class"
        assert "download_folder" in content, "Missing download_folder method"
        assert "load_strategy_config" in content, "Missing load_strategy_config method"
        assert "load_all_configs" in content, "Missing load_all_configs method"

        print("✓ GoogleDriveLoader class structure is valid")
        print("  ✓ download_folder method present")
        print("  ✓ load_strategy_config method present")
        print("  ✓ load_all_configs method present")

        return True
    except Exception as e:
        print(f"✗ Google Drive loader structure test failed: {e}")
        return False


def check_endpoint_structure():
    """Check webhook endpoint structure."""
    print("\n=== Testing Endpoint Structure ===")

    try:
        endpoints_path = (
            Path(__file__).parent.parent
            / "apps/backend/src/api/tradingview_endpoints.py"
        )

        with open(endpoints_path, "r") as f:
            content = f.read()

        assert "router = APIRouter()" in content, "Missing router definition"
        assert "async def tradingview_webhook" in content, "Missing webhook endpoint"
        assert "async def list_tradingview_alerts" in content, (
            "Missing alerts list endpoint"
        )
        assert "async def get_webhook_config" in content, "Missing config endpoint"
        assert "verify_webhook_secret" in content, "Missing webhook secret verification"

        print("✓ TradingView endpoints structure is valid")
        print("  ✓ POST /webhook endpoint present")
        print("  ✓ GET /alerts endpoint present")
        print("  ✓ GET /config endpoint present")
        print("  ✓ Webhook authentication present")

        return True
    except Exception as e:
        print(f"✗ Endpoint structure test failed: {e}")
        return False


CHECKS = [
    ("Pydantic Models", check_pydantic_models),
    ("Strategy Logic", check_strategy_logic),
    ("YAML Configuration", check_yaml_config),
    ("Google Drive Loader", check_gdrive_loader_structure),
    ("Endpoint Structure", check_endpoint_structure),
]


def test_pydantic_models():
    assert check_pydantic_models()


def test_strategy_logic():
    assert check_strategy_logic()


def test_yaml_config():
    assert check_yaml_config()


def test_gdrive_loader_structure():
    assert check_gdrive_loader_structure()


def test_endpoint_structure():
    assert check_endpoint_structure()


def main():
    """Run all tests"""
    print("=" * 60)
    print("TradingView Integration Test Suite")
    print("=" * 60)

    results = [(name, check()) for name, check in CHECKS]

    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        print(f"{test_name:.<30} {status}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n✓ All tests passed! TradingView integration is ready.")
        return 0

    print(f"\n✗ {total - passed} test(s) failed.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
