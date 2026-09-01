# 11 Wall Street for zWorkforce

A self-contained market-intelligence operator surface derived from the behavior of the provided `11-wall-street-v1.0.0.zip` project and the interoperability surface exposed by TradingView Desktop for Linux.

## What is integrated

- Official TradingView Advanced Chart public embed; no `app.asar` code or TradingView private assets are copied.
- Binance and KuCoin public realtime market feeds for ticker, order book and recent trades.
- TradingView Desktop launch via the registered `tradingview:` URI scheme discovered in the Debian desktop entry.
- ZWorkforce `/health` bridge so the operator surface can report whether the control plane is online without placing credentials in browser assets.
- A restrictive CSP scoped to this standalone process instead of relaxing the core ZWorkforce dashboard CSP.

This package is **market intelligence only**. It does not submit exchange orders, request API keys, inject into TradingView Desktop, bypass authentication, or access private TradingView APIs.

## Run

Requirements: Node.js 20+.

```bash
cd packages/wall-street
npm run check
ZWORKFORCE_URL=http://127.0.0.1:8080 npm start
```

Open `http://127.0.0.1:4174`.

Optional runtime settings:

```bash
WALL_STREET_HOST=127.0.0.1
WALL_STREET_PORT=4174
ZWORKFORCE_URL=http://127.0.0.1:8080
```

`ZWORKFORCE_URL` is used only by the Node server to call the public ZWorkforce health endpoint. It is not emitted into frontend JavaScript.

## Deployment model

Keep this package as an isolated operator surface and place it behind the same authenticated ingress as ZWorkforce if it will be exposed outside localhost. The core control plane intentionally retains its stricter `script-src 'self'` / `frame-ancestors 'none'` policy.

For TradingView Desktop, the button invokes `tradingview:` only after an explicit user click. The operating system decides which registered handler receives that URI.

## Provenance

See [`REVERSE_ENGINEERING.md`](REVERSE_ENGINEERING.md) for package hashes, observed Debian metadata and the exact interoperability boundary used for this integration.
