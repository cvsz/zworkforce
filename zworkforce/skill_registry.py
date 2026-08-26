from __future__ import annotations

import ipaddress
import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .capabilities import CapabilityError, assert_safe_capability_upgrade, is_enterprise_manifest
from .skills import validate_manifest, verify_manifest


class SkillRegistryError(ValueError):
    pass


def _host_allowed(host: str, allow_hosts: tuple[str, ...]) -> bool:
    host = host.lower().rstrip(".")
    return any(
        host == suffix.lower().rstrip(".")
        or host.endswith("." + suffix.lower().rstrip("."))
        for suffix in allow_hosts
    )


def _assert_public_host(host: str) -> None:
    try:
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise SkillRegistryError("skill registry host cannot be resolved") from exc
    if not infos:
        raise SkillRegistryError("skill registry host cannot be resolved")
    for info in infos:
        addr = ipaddress.ip_address(info[4][0])
        if (
            addr.is_private
            or addr.is_loopback
            or addr.is_link_local
            or addr.is_multicast
            or addr.is_reserved
            or addr.is_unspecified
        ):
            raise SkillRegistryError("skill registry host resolves to a non-public address")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class RemoteSkillRegistry:
    def __init__(
        self,
        db,
        signing_key: str,
        allow_hosts: tuple[str, ...] = (),
        timeout: float = 10.0,
        max_bytes: int = 1_000_000,
    ):
        self.db = db
        self.signing_key = signing_key
        self.allow_hosts = tuple(x.strip().lower() for x in allow_hosts if x.strip())
        self.timeout = max(1.0, float(timeout))
        self.max_bytes = max(1024, min(int(max_bytes), 10_000_000))

    def _validate_url(self, url: str) -> str:
        parts = urllib.parse.urlsplit(str(url))
        if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
            raise SkillRegistryError("skill registry URL must be HTTPS without userinfo")
        if not self.allow_hosts or not _host_allowed(parts.hostname, self.allow_hosts):
            raise SkillRegistryError("skill registry host is not allowlisted")
        return urllib.parse.urlunsplit(parts)

    def _network_validate(self, url: str) -> str:
        current = self._validate_url(url)
        parts = urllib.parse.urlsplit(current)
        _assert_public_host(parts.hostname or "")
        return current

    def _fetch_json(self, url: str) -> dict[str, Any]:
        current = self._network_validate(url)
        opener = urllib.request.build_opener(_NoRedirect())
        for _ in range(5):
            req = urllib.request.Request(
                current,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "zWorkforce-skill-registry/3",
                },
            )
            try:
                response = opener.open(req, timeout=self.timeout)
            except urllib.error.HTTPError as exc:
                if exc.code in {301, 302, 303, 307, 308}:
                    location = exc.headers.get("Location", "")
                    if not location:
                        raise SkillRegistryError("skill registry redirect missing Location") from exc
                    current = self._network_validate(urllib.parse.urljoin(current, location))
                    continue
                raise SkillRegistryError(f"skill registry returned HTTP {exc.code}") from exc
            except OSError as exc:
                raise SkillRegistryError("skill registry request failed") from exc
            with response:
                length = response.headers.get("Content-Length")
                if length and int(length) > self.max_bytes:
                    raise SkillRegistryError("skill package exceeds maximum size")
                body = response.read(self.max_bytes + 1)
                if len(body) > self.max_bytes:
                    raise SkillRegistryError("skill package exceeds maximum size")
            try:
                payload = json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise SkillRegistryError("skill package is not valid UTF-8 JSON") from exc
            if not isinstance(payload, dict):
                raise SkillRegistryError("skill package must be a JSON object")
            return payload
        raise SkillRegistryError("too many skill registry redirects")

    def install(
        self,
        tenant_id: str,
        url: str,
        actor: str,
        require_signature: bool = True,
    ) -> dict[str, Any]:
        package = self._fetch_json(url)
        manifest = package.get("manifest", package.get("skill"))
        signature = str(package.get("signature", ""))
        if not isinstance(manifest, dict):
            raise SkillRegistryError("skill package requires a manifest object")
        try:
            validate_manifest(manifest)
        except ValueError as exc:
            raise SkillRegistryError(str(exc)) from exc
        if not verify_manifest(manifest, signature, self.signing_key, require_signature):
            raise SkillRegistryError("skill signature verification failed")

        existing = self.db.get_skill(tenant_id, manifest["id"])
        if (
            existing
            and is_enterprise_manifest(existing.get("manifest", {}))
            and is_enterprise_manifest(manifest)
        ):
            try:
                assert_safe_capability_upgrade(existing["manifest"], manifest)
            except CapabilityError as exc:
                raise SkillRegistryError(str(exc)) from exc

        result = self.db.upsert_skill(tenant_id, manifest, signature, actor, enabled=True)
        try:
            self.db.audit(
                tenant_id,
                actor,
                "skill.remote_install",
                "skill",
                manifest["id"],
                {"source": self._validate_url(url), "version": manifest["version"]},
            )
        except AttributeError:
            pass
        return result
