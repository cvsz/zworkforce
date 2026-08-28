# TradingView / 11 Wall Street interoperability analysis

Analysis date: 2026-08-27.

## Inputs

### TradingView Desktop Debian package

- Input: `tradingview_amd64.deb`
- SHA-256: `cb831fd0d8e5cd3cf24eb14a7f3a458d9994ffa7b1c39db57d09c7099930d7e3`
- Debian package: `tradingview`
- Version: `3.3.0-1`
- Architecture: `amd64`
- Maintainer metadata: TradingView Inc.

Observed package layout includes an Electron executable, `resources/app.asar`, Chromium/Electron resources and native modules including `tvdbridge.node`, `keytar.node` and a LevelDB binding.

The desktop entry registers `x-scheme-handler/tradingview` and launches `/opt/TradingView/tradingview --no-sandbox %U`. The integration therefore uses only the externally registered `tradingview:` URI scheme as an operating-system interoperability contract.

The package also configures the TradingView Ubuntu stable APT repository at `https://tvd-packages.tradingview.com/ubuntu/stable`.

### 11 Wall Street source payload

- Input label: `11-wall-street-v1.0.0.zip`
- SHA-256: `9afe7b58ebd8443ce25ec6aa41dade266798823548560ff0cc4ae45db0523e63`
- Actual container detected: gzip-compressed tar archive, not ZIP
- Project stack: Next.js 15, React 19, Bun-oriented scripts, TypeScript, Zustand and public market APIs
- Chart integration: `https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js`
- Public market integrations observed: Binance and KuCoin realtime feeds plus REST order-book snapshots
- The source `.env` contains a `DATABASE_URL`; its value was not copied into this repository.

## Boundary intentionally preserved

This work does **not** decompile, unpack into source, modify or redistribute TradingView's `app.asar`, native modules, credentials, signing material or proprietary visual assets. No private endpoint, license check, authentication token or DRM mechanism is bypassed.

The implementation independently composes three public/interoperable surfaces:

1. TradingView's public Advanced Chart embed.
2. Public Binance/KuCoin market-data endpoints.
3. The `tradingview:` custom protocol registered by the installed desktop application.

## Mapping into zWorkforce

The live zWorkforce repository keeps browser assets under a strict control-plane CSP. The market terminal needs external frame/script/connect origins, so widening that global policy would unnecessarily increase the main control plane's attack surface.

The integration is therefore isolated in `packages/wall-street/` with its own Node static server and CSP. A server-side `/api/zworkforce-health` bridge reads only the public `/health` response from the configured control plane. No zWorkforce API key, provider credential, storage secret or exchange credential is sent to the browser.

## Known limitations

- The desktop URI contract confirms handler registration, not undocumented command arguments. The UI launches the bare `tradingview:` scheme and does not invent proprietary deep-link syntax.
- Public exchange endpoint availability, CORS behavior and websocket schemas are controlled by the exchanges and can change independently.
- This package performs no order execution. Any future broker/exchange write path must use separate server-side credentials, explicit authorization and zWorkforce's bounded mutation/policy controls.
