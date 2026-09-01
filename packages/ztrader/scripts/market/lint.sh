#!/usr/bin/env bash
set -Eeuo pipefail

ruff check src tests
mypy src
