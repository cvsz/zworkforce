#!/usr/bin/env bash
set -Eeuo pipefail

python -m pip install -e '.[dev]'
pytest
