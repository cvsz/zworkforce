from __future__ import annotations

import argparse
import hashlib
import hmac
import os
import re
import stat
import sys
from pathlib import Path

CHUNK_SIZE = 1024 * 1024
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")


class PlanValidationError(ValueError):
    """Raised when a Terraform plan cannot be safely verified."""


def _open_regular_file(path: Path, flags: int, mode: int = 0o600) -> int:
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags, mode)
    except OSError as exc:
        raise PlanValidationError(f"cannot safely open plan file: {path}") from exc
    if not stat.S_ISREG(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise PlanValidationError(f"plan path must be a regular file: {path}")
    return descriptor


def compute_sha256(plan_path: str | Path) -> str:
    path = Path(plan_path)
    descriptor = _open_regular_file(path, os.O_RDONLY)
    with os.fdopen(descriptor, "rb") as stream:
        if os.fstat(stream.fileno()).st_size <= 0:
            raise PlanValidationError("Terraform plan file is empty")
        digest = hashlib.sha256()
        for chunk in iter(lambda: stream.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_and_copy_plan(
    plan_path: str | Path,
    expected_sha256: str,
    copy_to: str | Path,
) -> str:
    if not SHA256_PATTERN.fullmatch(expected_sha256):
        raise PlanValidationError("approved_plan_sha256 must be 64 lowercase hexadecimal characters")

    source_path = Path(plan_path)
    destination_path = Path(copy_to)
    source_fd = _open_regular_file(source_path, os.O_RDONLY)
    destination_fd = -1
    try:
        destination_fd = _open_regular_file(destination_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC)
        source_stat = os.fstat(source_fd)
        destination_stat = os.fstat(destination_fd)
        if (source_stat.st_dev, source_stat.st_ino) == (destination_stat.st_dev, destination_stat.st_ino):
            raise PlanValidationError("verified plan copy must be a different file")
        if source_stat.st_size <= 0:
            raise PlanValidationError("Terraform plan file is empty")

        digest = hashlib.sha256()
        with os.fdopen(source_fd, "rb") as source, os.fdopen(destination_fd, "wb") as destination:
            source_fd = -1
            destination_fd = -1
            for chunk in iter(lambda: source.read(CHUNK_SIZE), b""):
                digest.update(chunk)
                destination.write(chunk)
            destination.flush()
            os.fsync(destination.fileno())

        actual_sha256 = digest.hexdigest()
        if not hmac.compare_digest(actual_sha256, expected_sha256):
            raise PlanValidationError("Terraform plan digest mismatch; apply was not authorized")
        return actual_sha256
    except Exception:
        if source_fd >= 0:
            os.close(source_fd)
        if destination_fd >= 0:
            os.close(destination_fd)
        try:
            destination_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print or verify an exact Terraform plan SHA-256.")
    parser.add_argument("plan_path", help="Path to the ignored local Terraform plan file")
    parser.add_argument("expected_sha256", nargs="?", help="Approved 64-character lowercase SHA-256")
    parser.add_argument("--copy-to", help="Write the verified plan bytes to a fresh temporary file")
    args = parser.parse_args(argv)

    try:
        if args.expected_sha256 is None:
            if args.copy_to:
                raise PlanValidationError("--copy-to requires an approved SHA-256")
            print(f"plan_sha256={compute_sha256(args.plan_path)}")
            return 0
        if not args.copy_to:
            raise PlanValidationError("--copy-to is required when verifying an approved plan")
        digest = verify_and_copy_plan(args.plan_path, args.expected_sha256, args.copy_to)
        print(f"verified_plan_sha256={digest}")
        return 0
    except PlanValidationError as exc:
        print(f"terraform-plan-verification: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
