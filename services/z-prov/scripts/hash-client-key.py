#!/usr/bin/env python3
from __future__ import annotations

import getpass

from zeaz_provider.security import client_key_digest


def main() -> None:
    key = getpass.getpass("Client key (input hidden): ")
    if len(key) < 32:
        raise SystemExit("Client keys must contain at least 32 characters")
    print(f"sha256:{client_key_digest(key).hex()}")


if __name__ == "__main__":
    main()
