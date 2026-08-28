#!/usr/bin/env python3
import os
import socket
import sys

host = os.getenv("VOICE_AGENT_HEALTH_HOST", "127.0.0.1")
port = int(os.getenv("VOICE_AGENT_PORT", "8765"))

try:
    with socket.create_connection((host, port), timeout=3):
        pass
except OSError:
    sys.exit(1)
