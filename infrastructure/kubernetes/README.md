# k3s deployment baseline

This directory is the GitOps boundary for the platform services. The base is
intentionally non-production and uses `dev` image tags so it cannot be
mistaken for an approved release artifact.

Before production use, create an overlay that replaces every image with an
immutable registry digest and supplies the `z-platform-runtime` Secret from
the selected secret manager. Never commit that Secret or provider keys.

The target cluster contract is Ubuntu 24.04 + k3s with Cilium as the CNI and
`kube-proxy` disabled. Cilium must be installed and validated at the cluster
layer before applying this application; these workload manifests do not
silently enable a second service-proxy dataplane.

The Cloudflare tunnel remains the public ingress boundary. Services are
ClusterIP-only; no workload is exposed with a public LoadBalancer or NodePort.

Validation:

```sh
kustomize build infrastructure/kubernetes/base
kubectl apply --dry-run=server -k infrastructure/kubernetes/base
```

The Argo CD application in `argocd/application.yaml` points to an operator-
owned `overlays/production` path. It is deliberately not applied by local
automation until the production image digests, secret-manager references,
cluster identity, and release approval exist.

The workflow `.github/workflows/container-images.yml` publishes the four runtime
images to GHCR with immutable `sha-<full-commit>` tags, SBOMs, and provenance.
Release promotion must copy the resulting digests into the production overlay
before Argo CD synchronization.
