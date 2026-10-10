# Network isolation acceptance and evidence

The network policies define a browser pod's deny-all baseline and optional
same-namespace proxy-only egress. **Neither policy has been applied to a real
cluster.** The proxy-only rule is not safe without an independently secured
filtering proxy and verified network-policy enforcement (CNI).

Deployment order:
1. Verify the actual Kubernetes CNI implements NetworkPolicy egress. Establish
   a dedicated namespace and disposable worker service account.
2. Deploy and secure a proxy that denies private/link-local/metadata networks,
   redirects, DNS rebinding and unauthorized origins at the resolved-IP layer.
3. Apply deny-all first; prove blocked DNS, Internet, RFC1918, loopback and
   169.254.169.254 attempts with command, result and timestamp.
4. Only then apply the proxy-only policy; verify the worker can reach only the
   proxy endpoint and the proxy blocks forbidden destinations.
5. Record pod UID, image digest, CNI version, policies, proxy settings, traffic
   capture/counters, and audit event IDs.
6. Verify emergency-stop cancels running Chromium and revokes its network
   access; restart attempts must not replay consumed approvals.

The network policy cannot govern a browser running directly on a Windows host,
WSL2 host process or an externally networked Docker container. The local
reference tests are not evidence of a real network-isolated deployment.
