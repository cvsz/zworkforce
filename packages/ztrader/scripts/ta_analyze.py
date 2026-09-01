#!/usr/bin/env python3
"""TradingAgents CLI analysis tool for ztrader.

Usage:
    python scripts/ta_analyze.py NVDA
    python scripts/ta_analyze.py BTC-USD --provider anthropic --date 2024-05-10
"""

import argparse
import sys
import os

# Add backend src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend", "src"))

from ztrader.tradingagents_integration.adapter import TradingAgentsStrategy


def main() -> None:
    parser = argparse.ArgumentParser(
        description="TradingAgents multi-agent LLM analysis",
    )
    parser.add_argument("symbol", help="Ticker symbol (e.g., NVDA, BTC-USD)")
    parser.add_argument(
        "--provider", "-p",
        default="openai",
        choices=["openai", "anthropic", "google", "azure", "bedrock", "deepseek", "qwen", "groq", "mistral", "ollama", "openrouter"],
        help="LLM provider",
    )
    parser.add_argument("--date", "-d", help="Analysis date (YYYY-MM-DD)")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")

    args = parser.parse_args()

    strategy = TradingAgentsStrategy(
        llm_provider=args.provider,
        debug=args.debug,
    )

    print(f"\n{'='*60}")
    print(f"TradingAgents Analysis: {args.symbol}")
    print(f"Provider: {args.provider}")
    print(f"{'='*60}\n")

    result = strategy.analyze(args.symbol, args.date)

    print(f"Signal:     {result.signal.upper()}")
    print(f"Confidence: {result.confidence:.1%}")
    print(f"Risk Score: {result.risk_score:.1%}")
    print(f"Date:       {result.analysis_date}")
    print(f"\nReasoning: {result.reasoning}")
    print(f"\nAgents:    {', '.join(result.agents_used) if result.agents_used else 'N/A'}")

    if result.supporting_data:
        print(f"\nSupporting Data:")
        for key, value in result.supporting_data.items():
            if value:
                print(f"  {key}: {str(value)[:100]}...")

    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    main()