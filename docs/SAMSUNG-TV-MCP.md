# Samsung Smart TV MCP Integration

สถานะ: **Read-only MCP reference, compatibility advisory และ offline manifest validation**. Live Samsung Open Source Release Center search, SDK build, SDB/USB installation, package signing and firmware operations are **not implemented**.

## Official references

- [Samsung Smart TV Developer](https://developer.samsung.com/smarttv/develop)
- [Samsung Open Source Release Center](https://opensource.samsung.com/main)

## Architecture

Existing zWorkforce `POST /mcp` uses the tenant-scoped identity and authorization system. These tools are available to principals with `viewer` role and `workforce:read` scope.

| Tool | Input | Output |
| --- | --- | --- |
| `samsung.sources` | `{}` | Curated official URLs, descriptions and `live_verified: false` |
| `samsung.model_guidance` | `{"model":"UA40F5500AR"}` | Normalized model, verification checklist and source links |
| `samsung.compatibility` | `{"model":"UA40F5500AR","model_year":2013}` | Year-based advisory, not hardware verification |
| `samsung.source_manifest` | `{"model":"UA40F5500AR","packages":[]}` | Validate operator-supplied unverified source license/hash declarations |

The model tool **does not guess** OS version or app format. Verify legacy Samsung TV platform versus Tizen via official model support documentation before choosing a packaging path.

## Example

```bash
zworkforce mcp-tools https://workforce.example.com/mcp
zworkforce mcp-call https://workforce.example.com/mcp samsung.sources --arguments '{}'
zworkforce mcp-call https://workforce.example.com/mcp samsung.model_guidance --arguments '{"model":"UA40F5500AR"}'
```

`ZWORKFORCE_MCP_TOKEN` must be configured as described in [MCP.md](MCP.md).

รายละเอียด [Samsung Source Manifest MCP](SAMSUNG-SOURCE-MANIFEST-MCP.md) และ [Samsung Compatibility](SAMSUNG-TV-MCP-PHASE2.md) ไม่ได้หมายถึง Live OSRC Search หรือการยืนยัน Hash จริง

## Future scoped work

- Explicit source-release metadata lookup with official-public endpoint validation, stable parsing, timeouts, rate limits, pagination, provenance, caching and evidence of live verification.
- License manifest and SBOM generation from **obtained** release files, never an invented inventory.
- Tizen SDK probe, manifest validation, packaging and SDB installation behind role/scope approvals, device allowlists, bounded subprocess calls and auditable operator confirmation.
- Separate legacy Samsung TV support; never send `.wgt` to unknown/non-Tizen models.

## Safety

Do not auto-download or execute binaries from release listings. Enforce egress host allowlists and redirects, avoid fetching user-supplied URLs, reject paths/commands as model IDs, require explicit authorization for device writes, and never equate released GPL components with complete firmware source or flashing permission.

## Validation

Run focused MCP tests, repository CI and a live device acceptance test only when an approved physical target is available. Successful unit tests alone do not establish hardware compatibility or production readiness.
