# Repo-aware `*.zeaz.dev` routing and Under Construction fallback

This design keeps existing live ZeaZDev services untouched while giving active product repositories a safe public placeholder when their site is not online.

## Behavior

- A repository-derived hostname that responds successfully stays on its existing DNS/origin path.
- A hostname that fails the public reachability probe is added to an **exact Cloudflare Worker route** and returns a branded `Under Construction` page with HTTP `503`.
- The fallback Worker exposes `/.well-known/zeaz-status` and `/health` as HTTP `200` JSON so operators can distinguish a deliberate placeholder from an origin failure.
- Optional wildcard DNS (`*.zeaz.dev`) can make repo hostnames without an exact DNS record resolve through the existing Cloudflare Tunnel. Exact DNS records still take precedence over the wildcard.
- The zone apex and `www.zeaz.dev` are not managed by this fallback.

The implementation deliberately does **not** replace all traffic with a wildcard Worker route. Only hostnames present in `repo_fallback_sites` are intercepted, so a live application such as `zmovie.zeaz.dev` remains on its real origin when its public probe passes.

## Repository discovery

`scripts/cloudflare/reconcile-repo-sites.sh` uses the authenticated GitHub CLI to enumerate repositories owned by `cvsz` and excludes archived/fork repositories. It considers product repositories using the `z*` / `zeaz*` naming convention plus a small set of explicit product aliases.

Existing aliases are mapped to the owning repository, including:

- `zwf.zeaz.dev` / `zwf-api.zeaz.dev` -> `cvsz/zworkforce`
- `studio.zeaz.dev` / `zider.zeaz.dev` -> `cvsz/zsp-aitool`
- `chat.zeaz.dev` -> `cvsz/open-webui`
- `qwen.zeaz.dev` -> `cvsz/qwen-gen`
- `zai.zeaz.dev` -> `cvsz/zeaz-ai-command-center`
- `zttshop.zeaz.dev` -> `cvsz/zttshop-php`
- `cme.zeaz.dev` -> `cvsz/cmeerp`
- `zany.zeaz.dev` -> `cvsz/zanything`

A repository homepage already set to a `*.zeaz.dev` URL is also treated as an authoritative candidate hostname.

## Audit and plan

From the `zworkforce` checkout on the trusted operator host:

```bash
bash scripts/cloudflare/reconcile-repo-sites.sh
```

This performs public HTTPS probes and writes ignored operator files:

```text
infrastructure/terraform/cloudflare/repo-fallback.auto.tfvars.json
infrastructure/terraform/cloudflare/repo-fallback-status.json
infrastructure/terraform/cloudflare/tfplan.repo-fallback
```

The generated Terraform map contains **offline hostnames only**. Inspect both the status JSON and Terraform plan before applying.

If DNS for repo-derived hostnames is not already covered, include the wildcard DNS resource in the plan:

```bash
bash scripts/cloudflare/reconcile-repo-sites.sh --wildcard-dns
```

Before enabling wildcard DNS, confirm there is no unmanaged conflicting wildcard record in the `zeaz.dev` zone. Exact records for existing applications are not replaced by a DNS wildcard.

## Apply

Application is intentionally fail-closed and requires an explicit acknowledgement:

```bash
ZEAZ_REPO_FALLBACK_APPLY=YES \
  bash scripts/cloudflare/reconcile-repo-sites.sh --wildcard-dns --apply
```

The helper uses a targeted Terraform plan limited to:

```text
cloudflare_workers_script.repo_under_construction
cloudflare_workers_route.repo_under_construction
cloudflare_dns_record.repo_fallback_wildcard
```

It does not rewrite the shared tunnel ingress configuration and therefore does not overwrite unrelated local changes such as pending zMovie ingress work.

## Verification

For a hostname currently under construction:

```bash
curl -i https://HOST.zeaz.dev/
curl -fsS https://HOST.zeaz.dev/.well-known/zeaz-status | jq .
```

Expected page response:

```text
HTTP 503
Retry-After: 900
```

Expected status endpoint includes:

```json
{
  "status": "under-construction",
  "hostname": "HOST.zeaz.dev",
  "repository": "cvsz/REPOSITORY"
}
```

For a live hostname, confirm the actual application still responds and is absent from `repo_fallback_sites`.

## Promotion from Under Construction to live

A fallback Worker intentionally intercepts all public paths for that hostname, so a normal public health probe cannot see a newly deployed origin until the exact Worker route is removed. Promotion therefore uses an explicit, reviewed override rather than guessing.

1. Deploy the repository runtime and its intended DNS/tunnel route.
2. Verify the origin locally or through an origin-bypassing operator check.
3. Generate the removal plan with the exact hostname explicitly promoted:

```bash
ZEAZ_REPO_FORCE_LIVE=HOST.zeaz.dev \
  bash scripts/cloudflare/reconcile-repo-sites.sh --wildcard-dns
```

4. Confirm `repo-fallback-status.json` records that hostname as live with `promotion-override` evidence and inspect the Terraform plan to ensure only that fallback route is removed.
5. Apply the reviewed plan:

```bash
ZEAZ_REPO_FORCE_LIVE=HOST.zeaz.dev \
ZEAZ_REPO_FALLBACK_APPLY=YES \
  bash scripts/cloudflare/reconcile-repo-sites.sh --wildcard-dns --apply
```

6. Rerun the reconciler **without** `ZEAZ_REPO_FORCE_LIVE`. The real public service must now pass one of the normal health/root probes. If it does not, the generated plan will safely propose restoring the fallback route.

This makes the repository/runtime state explicit without claiming an application is production-ready merely because its GitHub repository exists.
