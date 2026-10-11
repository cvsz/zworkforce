# Samsung TV MCP compatibility phase

Adds `samsung.compatibility` to the existing authenticated `POST /mcp` endpoint. It accepts a validated Samsung model ID and **explicit, operator-provided model year**. The SDK recommendation is a year-based advisory, **not verified device compatibility**. Device model, firmware, SDK support, and signing availability must be checked separately.

Official documents:
- Legacy Samsung TV SDK 2010-2014: https://developer.samsung.com/smarttv/legacy/overview.html
- Legacy platform FAQ (USB signing): https://developer.samsung.com/smarttv/legacy/samsung-legacy-platform-faq.html
- Tizen TV quick start: https://developer.samsung.com/smarttv/develop/getting-started/quick-start-guide.html
- Samsung Open Source Release Center: https://opensource.samsung.com/main

Example:
```bash
zworkforce mcp-call https://workforce.example.com/mcp samsung.compatibility --arguments '{"model":"UA40F5500AR","model_year":2013}'
```

The model year must be separately confirmed by the operator. For Samsung's 2010-2014 legacy platform, Tizen `.wgt` packaging is not supported; use Samsung Legacy SDK and Samsung Seller Office instructions for a compatible package and device-specific signature. No USB install or live device testing is claimed.

Security: requires `viewer` and `workforce:read`, performs no network access or device mutation, stores no secrets, and does not infer compatibility from a bare model string.

Next phases: model lookup backed by official documentation, source release metadata with provenance/license checks, SDK probe and bounded builder adapters requiring operator approval. Implement these separately with integration tests before asserting support.
