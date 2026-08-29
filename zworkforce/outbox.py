from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import socket
import time
import urllib.parse
import urllib.request
import uuid
from typing import Any


class OutboxError(RuntimeError): pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise OutboxError(f"outbox does not follow redirects (HTTP {code})")


class OutboxDispatcher:
    def __init__(self, db, signing_secret: str = "", timeout_seconds: int = 10, allow_hosts: tuple[str,...] = ()):
        self.db=db;self.secret=signing_secret.encode("utf-8") if signing_secret else b"";self.timeout_seconds=max(1,int(timeout_seconds))
        self.allow_hosts=tuple(x.lower().rstrip(".") for x in allow_hosts if x)
        self.owner_id=f"outbox-{socket.gethostname()}-{uuid.uuid4().hex[:8]}"
        self.claim_lease_seconds=max(30,self.timeout_seconds*2)

    def _claim_limit(self, requested: int) -> int:
        requested = max(1, min(int(requested), 500))
        # A claim is processed serially. Keep the worst-case request time
        # inside the lease so another worker cannot reclaim later items while
        # this dispatcher is still delivering the earlier ones.
        safe_seconds = max(1, self.claim_lease_seconds - 5)
        return min(requested, max(1, safe_seconds // self.timeout_seconds))

    def sign(self,payload:bytes)->str:return hmac.new(self.secret,payload,hashlib.sha256).hexdigest() if self.secret else ""

    def _validate_destination(self,url:str)->None:
        p=urllib.parse.urlsplit(url);host=(p.hostname or "").lower().rstrip(".")
        if p.scheme not in {"https","http"} or not host:raise OutboxError("outbox destination must be HTTP(S)")
        if p.scheme=="http" and host not in {"localhost","127.0.0.1","::1"}:raise OutboxError("remote outbox destinations must use HTTPS")
        if not self.allow_hosts and host not in {"localhost","127.0.0.1","::1"}:raise OutboxError("remote outbox requires ZWORKFORCE_OUTBOX_ALLOWLIST")
        if self.allow_hosts and not any(host==h or host.endswith("."+h) for h in self.allow_hosts):raise OutboxError("outbox destination host is not allowlisted")

    def enqueue(self,tenant_id:str,topic:str,destination:str,payload:dict[str,Any])->str:
        self._validate_destination(destination)
        raw=json.dumps(payload,separators=(",",":"),ensure_ascii=False,sort_keys=True).encode("utf-8")
        return self.db.enqueue_outbox(tenant_id,topic,destination,payload,self.sign(raw))

    def tick(self,limit:int=100,owner_id:str|None=None)->dict[str,int]:
        stats={"delivered":0,"failed":0}
        owner_id=owner_id or self.owner_id
        opener=urllib.request.build_opener(_NoRedirect())
        for item in self.db.claim_outbox(owner_id,self.claim_lease_seconds,self._claim_limit(limit)):
            raw=json.dumps(item.get("payload") or {},separators=(",",":"),ensure_ascii=False,sort_keys=True).encode("utf-8")
            headers={"Content-Type":"application/json","User-Agent":"zWorkforce-outbox/3","X-ZWorkforce-Topic":item["topic"],"X-ZWorkforce-Tenant":item["tenant_id"],"X-ZWorkforce-Delivery-ID":item["id"]}
            signature=item.get("signature") or self.sign(raw)
            if signature:headers["X-ZWorkforce-Signature"]=signature
            try:
                self._validate_destination(item["destination"])
                req=urllib.request.Request(item["destination"],data=raw,headers=headers,method="POST")
                with opener.open(req,timeout=self.timeout_seconds) as response:
                    response.read(4096)
                    if response.status<200 or response.status>=300:raise RuntimeError(f"destination HTTP {response.status}")
                if self.db.finish_outbox(item["id"],True,owner=owner_id):stats["delivered"]+=1
            except Exception as exc:
                attempts=int(item.get("attempts") or 0)+1
                if self.db.finish_outbox(item["id"],False,str(exc),min(2**min(attempts,10),3600),owner=owner_id):stats["failed"]+=1
        return stats

    def loop(self,poll_seconds:float=2.0,owner_id:str=""):
        owner_id=owner_id or self.owner_id;lease_seconds=max(10,int(max(1.0,poll_seconds)*5))
        try:
            while True:
                if self.db.acquire_service_lease("outbox",owner_id,lease_seconds):self.tick(owner_id=owner_id)
                time.sleep(max(.2,float(poll_seconds)))
        finally:self.db.release_service_lease("outbox",owner_id)
