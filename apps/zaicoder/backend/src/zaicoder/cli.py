"""Command-line entry point for the Z Platform ZAI Coder gateway client."""

from __future__ import annotations

import argparse
import os

from .gateway_client import GatewayClient, GatewayError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="zaicoder")
    parser.add_argument("prompt", help="User prompt sent to the approved AI gateway")
    parser.add_argument("--model", default="default", help="Gateway model alias")
    parser.add_argument(
        "--gateway-url",
        default=os.getenv("Z_PLATFORM_AI_GATEWAY_URL"),
        help="OpenAI-compatible gateway base URL",
    )
    parser.add_argument(
        "--token-env",
        default="Z_PLATFORM_SERVICE_TOKEN",
        help="Environment variable containing the gateway service token",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.gateway_url:
        raise SystemExit("Set Z_PLATFORM_AI_GATEWAY_URL or pass --gateway-url")

    token = os.getenv(args.token_env)
    if not token:
        raise SystemExit(f"Set the gateway token in {args.token_env}")

    try:
        content = GatewayClient(args.gateway_url, token).chat(
            model=args.model,
            prompt=args.prompt,
        )
    except (GatewayError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc

    print(content)
    return 0
