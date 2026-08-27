const PAIRS = {
  binance: ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT'],
  kucoin: ['BTC-USDT', 'ETH-USDT', 'SOL-USDT', 'KCS-USDT', 'XRP-USDT'],
};

const state = {
  exchange: 'binance',
  symbol: 'BTCUSDT',
  socket: null,
  reconnectTimer: null,
  pingTimer: null,
  trades: [],
  bids: new Map(),
  asks: new Map(),
};

const $ = (id) => document.getElementById(id);
const number = (value) => Number(value) || 0;

function cleanSymbol() {
  return state.symbol.replace('-', '');
}

function displayPair() {
  const clean = cleanSymbol();
  const quote = clean.endsWith('USDT') ? 'USDT' : clean.slice(-3);
  return `${clean.slice(0, -quote.length)}/${quote}`;
}

function tradingViewSymbol() {
  return `${state.exchange === 'kucoin' ? 'KUCOIN' : 'BINANCE'}:${cleanSymbol()}`;
}

function marketStatus(text, ok = false) {
  const el = $('feedStatus');
  el.textContent = `feed: ${text}`;
  el.dataset.ok = ok ? 'true' : 'false';
}

function formatPrice(value) {
  if (!Number.isFinite(value) || value <= 0) return '—';
  return value >= 1000 ? value.toLocaleString(undefined, { maximumFractionDigits: 2 }) : value.toLocaleString(undefined, { maximumFractionDigits: 6 });
}

function formatAmount(value) {
  if (!Number.isFinite(value)) return '—';
  return value.toLocaleString(undefined, { maximumFractionDigits: 6 });
}

function renderTicker(data) {
  const change = number(data.priceChangePercent ?? data.changeRate * 100);
  $('lastPrice').textContent = formatPrice(number(data.lastPrice ?? data.price));
  $('changePct').textContent = `${change >= 0 ? '+' : ''}${change.toFixed(2)}%`;
  $('changePct').dataset.direction = change >= 0 ? 'up' : 'down';
  $('highPrice').textContent = formatPrice(number(data.highPrice ?? data.high));
  $('lowPrice').textContent = formatPrice(number(data.lowPrice ?? data.low));
  $('volume').textContent = number(data.volume ?? data.vol).toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function sortedBook(map, side) {
  return Array.from(map.entries())
    .map(([price, quantity]) => ({ price: number(price), quantity: number(quantity) }))
    .filter((item) => item.quantity > 0)
    .sort((a, b) => side === 'bid' ? b.price - a.price : a.price - b.price)
    .slice(0, 14);
}

function renderBook() {
  const bids = sortedBook(state.bids, 'bid');
  const asks = sortedBook(state.asks, 'ask');
  $('bids').innerHTML = bids.map((item) => `<div><span>${formatPrice(item.price)}</span><span>${formatAmount(item.quantity)}</span></div>`).join('');
  $('asks').innerHTML = asks.slice().reverse().map((item) => `<div><span>${formatPrice(item.price)}</span><span>${formatAmount(item.quantity)}</span></div>`).join('');
  const bestBid = bids[0]?.price;
  const bestAsk = asks[0]?.price;
  $('midPrice').textContent = bestBid && bestAsk ? formatPrice((bestBid + bestAsk) / 2) : '—';
}

function addTrade({ id, price, quantity, time, side }) {
  state.trades.unshift({ id: String(id), price: number(price), quantity: number(quantity), time: number(time), side });
  state.trades = state.trades.slice(0, 40);
  $('trades').innerHTML = state.trades.map((trade) => {
    const timestamp = new Date(trade.time > 1e14 ? trade.time / 1e6 : trade.time).toLocaleTimeString([], { hour12: false });
    return `<div data-side="${trade.side}"><span>${formatPrice(trade.price)}</span><span>${formatAmount(trade.quantity)}</span><span>${timestamp}</span></div>`;
  }).join('');
}

function applyChanges(target, changes = []) {
  for (const entry of changes) {
    const price = String(entry[0]);
    const quantity = number(entry[1]);
    if (!quantity) target.delete(price);
    else target.set(price, quantity);
  }
}

function resetMarketState() {
  state.trades = [];
  state.bids.clear();
  state.asks.clear();
  $('trades').innerHTML = '';
  renderBook();
  for (const id of ['lastPrice', 'changePct', 'highPrice', 'lowPrice', 'volume']) $(id).textContent = '—';
}

function closeFeed() {
  if (state.reconnectTimer) clearTimeout(state.reconnectTimer);
  if (state.pingTimer) clearInterval(state.pingTimer);
  state.reconnectTimer = null;
  state.pingTimer = null;
  if (state.socket) {
    state.socket.onclose = null;
    state.socket.close();
    state.socket = null;
  }
}

async function loadBinanceSnapshot() {
  const response = await fetch(`https://api.binance.com/api/v3/depth?symbol=${cleanSymbol()}&limit=20`);
  if (!response.ok) throw new Error('binance snapshot failed');
  const data = await response.json();
  state.bids.clear(); state.asks.clear();
  applyChanges(state.bids, data.bids);
  applyChanges(state.asks, data.asks);
  renderBook();
}

function connectBinance() {
  const symbol = cleanSymbol().toLowerCase();
  const socket = new WebSocket(`wss://stream.binance.com:9443/stream?streams=${symbol}@trade/${symbol}@depth20@100ms/${symbol}@ticker`);
  state.socket = socket;
  socket.onopen = async () => {
    marketStatus('live · Binance', true);
    try { await loadBinanceSnapshot(); } catch { /* websocket updates still provide depth */ }
  };
  socket.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data).data;
      if (!payload) return;
      if (payload.e === 'trade') {
        addTrade({ id: payload.t, price: payload.p, quantity: payload.q, time: payload.T, side: payload.m ? 'sell' : 'buy' });
      } else if (payload.e === 'depthUpdate') {
        applyChanges(state.bids, payload.b);
        applyChanges(state.asks, payload.a);
        renderBook();
      } else if (Array.isArray(payload.bids) && Array.isArray(payload.asks)) {
        // Binance @depth20 partial snapshot stream sends { lastUpdateId, bids, asks }
        state.bids.clear(); state.asks.clear();
        applyChanges(state.bids, payload.bids);
        applyChanges(state.asks, payload.asks);
        renderBook();
      } else if (payload.e === '24hrTicker') {
        renderTicker({ lastPrice: payload.c, priceChangePercent: payload.P, highPrice: payload.h, lowPrice: payload.l, volume: payload.v });
      }
    } catch { /* ignore malformed exchange payloads */ }
  };
  socket.onerror = () => marketStatus('error');
  socket.onclose = () => scheduleReconnect();
}

async function loadKucoin24hrStats(symbol) {
  try {
    const response = await fetch(`https://api.kucoin.com/api/v1/market/stats?symbol=${encodeURIComponent(symbol)}`);
    if (!response.ok) return;
    const json = await response.json();
    if (json.data) {
      renderTicker({
        lastPrice: json.data.last,
        changeRate: json.data.changeRate,
        high: json.data.high,
        low: json.data.low,
        vol: json.data.vol,
      });
    }
  } catch { /* keep live stream unaffected */ }
}

async function loadKucoinSnapshot(symbol) {
  const response = await fetch(`https://api.kucoin.com/api/v1/market/orderbook/level2_20?symbol=${encodeURIComponent(symbol)}`);
  if (!response.ok) throw new Error('kucoin snapshot failed');
  const json = await response.json();
  if (!json.data) return;
  state.bids.clear(); state.asks.clear();
  applyChanges(state.bids, json.data.bids);
  applyChanges(state.asks, json.data.asks);
  renderBook();
}

async function connectKucoin() {
  const symbol = state.symbol.includes('-') ? state.symbol : state.symbol.replace(/USDT$/, '-USDT');
  try {
    const response = await fetch('https://api.kucoin.com/api/v1/bullet-public', { method: 'POST' });
    if (!response.ok) throw new Error('kucoin token failed');
    const json = await response.json();
    const server = json.data?.instanceServers?.[0];
    if (!json.data?.token || !server?.endpoint) throw new Error('kucoin token missing');
    const socket = new WebSocket(`${server.endpoint}?token=${encodeURIComponent(json.data.token)}&connectId=${Date.now().toString(36)}`);
    state.socket = socket;
    socket.onopen = async () => {
      marketStatus('live · KuCoin', true);
      const topics = [`/market/ticker:${symbol}`, `/market/level2:${symbol}`, `/market/match:${symbol}`];
      topics.forEach((topic, index) => socket.send(JSON.stringify({ id: Date.now() + index, type: 'subscribe', topic, response: true })));
      state.pingTimer = setInterval(() => {
        if (socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ id: Date.now(), type: 'ping' }));
      }, Math.max(10000, Number(server.pingInterval || 18000) - 1000));
      try {
        await Promise.all([loadKucoinSnapshot(symbol), loadKucoin24hrStats(symbol)]);
      } catch { /* keep realtime stream alive */ }
    };
    socket.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (!msg.data) return;
        if (msg.subject === 'trade.ticker') {
          if (msg.data.price) $('lastPrice').textContent = formatPrice(number(msg.data.price));
        } else if (msg.subject === 'trade.l2update') {
          applyChanges(state.bids, msg.data.changes?.bids);
          applyChanges(state.asks, msg.data.changes?.asks);
          renderBook();
        } else if (msg.subject === 'level2') {
          applyChanges(state.bids, msg.data.bids);
          applyChanges(state.asks, msg.data.asks);
          renderBook();
        } else if (msg.subject === 'trade.l3match') {
          addTrade({ id: msg.data.tradeId, price: msg.data.price, quantity: msg.data.size, time: msg.data.time, side: msg.data.side });
        }
      } catch { /* ignore malformed exchange payloads */ }
    };
    socket.onerror = () => marketStatus('error');
    socket.onclose = () => scheduleReconnect();
  } catch {
    marketStatus('unavailable · retrying');
    scheduleReconnect(5000);
  }
}

function scheduleReconnect(delay = 3000) {
  if (state.reconnectTimer) return;
  marketStatus('reconnecting');
  state.reconnectTimer = setTimeout(() => {
    state.reconnectTimer = null;
    connectFeed();
  }, delay);
}

function connectFeed() {
  closeFeed();
  resetMarketState();
  marketStatus('connecting');
  if (state.exchange === 'kucoin') void connectKucoin();
  else connectBinance();
}

function renderChart() {
  const container = $('chart');
  container.innerHTML = '';
  const widget = document.createElement('div');
  widget.className = 'tradingview-widget-container';
  widget.innerHTML = '<div class="tradingview-widget-container__widget"></div>';
  const script = document.createElement('script');
  script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js';
  script.type = 'text/javascript';
  script.async = true;
  script.textContent = JSON.stringify({
    autosize: true,
    symbol: tradingViewSymbol(),
    interval: '15',
    timezone: 'Asia/Bangkok',
    theme: 'dark',
    style: '1',
    locale: 'en',
    allow_symbol_change: true,
    hide_top_toolbar: false,
    hide_legend: false,
    save_image: true,
    calendar: false,
    studies: ['RSI@tv-basicstudies', 'MACD@tv-basicstudies'],
    backgroundColor: 'rgba(9, 14, 25, 1)',
    gridColor: 'rgba(94, 234, 212, 0.08)',
  });
  widget.appendChild(script);
  container.appendChild(widget);
  $('webChartLink').href = `https://www.tradingview.com/chart/?symbol=${encodeURIComponent(tradingViewSymbol())}`;
}

function refreshLabels() {
  const label = displayPair();
  $('pairLabel').textContent = label;
  $('bookPair').textContent = label;
}

function populateSymbols() {
  const select = $('symbolSelect');
  select.innerHTML = PAIRS[state.exchange].map((symbol) => `<option value="${symbol}">${symbol.replace('-', '/').replace('USDT', '/USDT').replace('//', '/')}</option>`).join('');
  state.symbol = PAIRS[state.exchange][0];
  select.value = state.symbol;
}

function switchMarket() {
  refreshLabels();
  renderChart();
  connectFeed();
}

async function checkZworkforce() {
  const el = $('zworkforceStatus');
  try {
    const response = await fetch('/api/zworkforce-health', { headers: { Accept: 'application/json' } });
    const data = await response.json();
    if (response.ok && data.status === 'ok') {
      el.textContent = `zWorkforce: online${data.version ? ` · ${data.version}` : ''}`;
      el.dataset.ok = 'true';
      return;
    }
  } catch { /* status remains unavailable */ }
  el.textContent = 'zWorkforce: unavailable';
  el.dataset.ok = 'false';
}

$('exchangeSelect').addEventListener('change', (event) => {
  state.exchange = event.target.value;
  populateSymbols();
  switchMarket();
});

$('symbolSelect').addEventListener('change', (event) => {
  state.symbol = event.target.value;
  switchMarket();
});

$('desktopBtn').addEventListener('click', () => {
  $('desktopHint').textContent = 'Desktop launch requested through the registered tradingview: protocol handler.';
  window.location.href = 'tradingview:';
});

window.addEventListener('beforeunload', closeFeed);
populateSymbols();
refreshLabels();
renderChart();
connectFeed();
void checkZworkforce();
setInterval(checkZworkforce, 30000);
