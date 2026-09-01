"use client";

import React, { useEffect, useState, useRef, useCallback } from 'react';
import { usePathname } from 'next/navigation';
import { initI18n } from '../../i18n/client';
import { useTranslation } from 'react-i18next';
import { ChartWidget } from '../../../components/ChartWidget';

interface BotResponse {
  bot_id: string;
  strategy_name: string;
  symbol: string;
  active: boolean;
  execution_mode: string;
}

interface AuditLogResponse {
  id: string;
  event_type: string;
  actor: string;
  severity: string;
  message: string;
  created_at: string;
  details?: unknown;
}

interface HealthInfo {
  status: string;
  environment: string;
  execution_mode: string;
  live_trading_enabled: boolean;
  kill_switch_active: boolean;
}

interface BacktestResult {
  strategy_id: string;
  candles_seen: number;
  orders_created: number;
  ending_usdt: number;
  ending_btc: number;
  profit_pct: number;
}

interface TickerItem {
  symbol: string;
  price: number;
  change: number;
  changePercent: number;
}

function useAnimatedValue(target: number, duration = 800): number {
  const [current, setCurrent] = useState(target);
  const rafRef = useRef<number>(0);
  const startValRef = useRef(current);

  useEffect(() => {
    const start = performance.now();
    startValRef.current = current;
    const delta = target - startValRef.current;

    const animate = (now: number) => {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setCurrent(startValRef.current + delta * eased);
      if (progress < 1) {
        rafRef.current = requestAnimationFrame(animate);
      }
    };

    rafRef.current = requestAnimationFrame(animate);
    return () => {
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = 0;
      }
    };
  }, [target, duration, current]);

  return current;
}

function Shimmer({ w = '100%', h = '16px' }: { w?: string; h?: string }) {
  return <div className="shimmer" style={{ width: w, height: h }} />;
}

export default function DashboardPage() {
  const pathname = usePathname();
  const lng = pathname?.split('/')[1] || 'en';
  initI18n(lng);
  const { t } = useTranslation('translation');

  const [health, setHealth] = useState<HealthInfo | null>(null);
  const [bots, setBots] = useState<BotResponse[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLogResponse[]>([]);
  const [riskLimits, setRiskLimits] = useState<{
    max_notional: number;
    allowed_symbols: string[];
  } | null>(null);
  const [pnl, setPnl] = useState<{
    total: number;
    currency: string;
  }>({ total: 0.0, currency: 'USDT' });

  const [selectedStrategy, setSelectedStrategy] = useState('ma-crossover');
  const [selectedSymbol, setSelectedSymbol] = useState('BTC/USDT');
  const [notional, setNotional] = useState(25);
  const [fastPeriod, setFastPeriod] = useState(3);
  const [slowPeriod, setSlowPeriod] = useState(5);

  const [btStrategy, setBtStrategy] = useState('ma-crossover');
  const [btSymbol, setBtSymbol] = useState('BTC/USDT');
  const [btFast, setBtFast] = useState(3);
  const [btSlow, setBtSlow] = useState(5);
  const [btNotional, setBtNotional] = useState(50);
  const [btResult, setBtResult] = useState<BacktestResult | null>(null);
  const [btError, setBtError] = useState<string | null>(null);
  const [btChartData, setBtChartData] = useState<
    { timestamp: string; open: number; high: number; low: number; close: number; volume: number }[]
  >([]);

  const [loading, setLoading] = useState({
    startBot: false,
    killSwitch: false,
    backtest: false,
  });

  const [tickerData, setTickerData] = useState<TickerItem[]>([]);
  const [tickerOffline, setTickerOffline] = useState(false);
  const [toast, setToast] = useState<{ msg: string; type: 'success' | 'error' } | null>(null);

  const showToast = (msg: string, type: 'success' | 'error') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 4000);
  };

  const animatedPnl = useAnimatedValue(pnl.total);

  const formatPnl = (val: number) => {
    const abs = Math.abs(val);
    if (abs >= 1000) return `$${val.toFixed(2)}`;
    if (abs >= 1) return `$${val.toFixed(4)}`;
    return `${val.toFixed(6)}`;
  };

  const backendUrl =
    process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

  useEffect(() => {
    let cancelled = false;
    const fetchTicker = async () => {
      try {
        const res = await fetch(`${backendUrl}/api/v1/ticker/prices`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (!cancelled) {
          if (Array.isArray(data)) {
            setTickerData(data);
          } else if (data?.prices) {
            setTickerData(data.prices);
          }
          setTickerOffline(false);
        }
      } catch {
        if (!cancelled) setTickerOffline(true);
      }
    };
    fetchTicker();
    const interval = setInterval(fetchTicker, 5000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [backendUrl]);

  const fetchData = useCallback(async () => {
    try {
      const hr = await fetch(`${backendUrl}/health`);
      if (hr.ok) {
        const hData = await hr.json();
        setHealth(hData);
      }

      const br = await fetch(`${backendUrl}/api/v1/bot/status`);
      if (br.ok) {
        const bData = await br.json();
        setBots(bData);
      }

      const ar = await fetch(`${backendUrl}/api/v1/audit/logs?limit=15`);
      if (ar.ok) {
        const aData = await ar.json();
        setAuditLogs(aData);
      }

      const rr = await fetch(`${backendUrl}/api/v1/risk/limits`).catch(() => null);
      if (rr?.ok) {
        const rData = await rr.json();
        setRiskLimits({
          max_notional: rData.max_notional ?? rData.max_order_notional ?? 0,
          allowed_symbols: rData.allowed_symbols ?? [],
        });
      }
    } catch (err) {
      console.error('Error fetching dashboard telemetry:', err);
    }
  }, [backendUrl]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 3000);
    return () => clearInterval(interval);
  }, [fetchData]);

  useEffect(() => {
    let cancelled = false;
    const fetchPnl = async () => {
      try {
        const res = await fetch(`${backendUrl}/api/v1/pnl`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (!cancelled) {
          setPnl({
            total: data.total ?? data.pnl ?? 0,
            currency: data.currency || 'USDT',
          });
        }
      } catch {
        // PnL endpoint unavailable — keep last known value
      }
    };
    if (bots.some((b) => b.active)) {
      fetchPnl();
      const interval = setInterval(fetchPnl, 8000);
      return () => {
        cancelled = true;
        clearInterval(interval);
      };
    }
  }, [bots, backendUrl]);

  const handleStartBot = async (e: React.FormEvent) => {
    e.preventDefault();
    const n = Number(notional);
    const fp = Number(fastPeriod);
    const sp = Number(slowPeriod);
    if (!n || n <= 0 || !Number.isFinite(n)) {
      showToast('Invalid notional amount', 'error');
      return;
    }
    if (!Number.isInteger(fp) || fp < 1) {
      showToast('Fast period must be a positive integer', 'error');
      return;
    }
    if (!Number.isInteger(sp) || sp < 1) {
      showToast('Slow period must be a positive integer', 'error');
      return;
    }
    if (fp >= sp) {
      showToast('Fast period must be less than slow period', 'error');
      return;
    }
    if (!selectedSymbol || !selectedSymbol.includes('/')) {
      showToast('Invalid trading symbol', 'error');
      return;
    }
    setLoading((prev) => ({ ...prev, startBot: true }));
    try {
      const res = await fetch(`${backendUrl}/api/v1/bot/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          strategy_name: selectedStrategy,
          symbol: selectedSymbol,
          notional: n,
          fast_period: fp,
          slow_period: sp,
        }),
      });
      if (res.ok) {
        showToast(`${selectedStrategy} bot started on ${selectedSymbol}`, 'success');
        await fetchData();
      } else {
        showToast(`Bot start failed (${res.status})`, 'error');
      }
    } catch (err) {
      console.error(err);
      showToast('Bot service unavailable', 'error');
    } finally {
      setLoading((prev) => ({ ...prev, startBot: false }));
    }
  };

  const handleStopBot = async (botId: string) => {
    try {
      const res = await fetch(
        `${backendUrl}/api/v1/bot/stop?bot_id=${encodeURIComponent(botId)}`,
        { method: 'POST' },
      );
      if (res.ok) {
        showToast(`Bot ${botId.slice(0, 12)}… stopped`, 'success');
        await fetchData();
      } else {
        showToast(`Failed to stop bot ${botId.slice(0, 12)}…`, 'error');
      }
    } catch (err) {
      console.error(err);
      showToast('Bot service unavailable', 'error');
    }
  };

  const handleToggleKillSwitch = async () => {
    if (!health) return;
    const nextState = !health.kill_switch_active;
    setLoading((prev) => ({ ...prev, killSwitch: true }));
    try {
      const adminToken =
        typeof window !== 'undefined'
          ? window.localStorage.getItem('ztrader_admin_token')
          : null;
      const res = await fetch(`${backendUrl}/api/v1/risk/kill-switch`, {
        method: 'POST',
        headers: adminToken
          ? {
              'Content-Type': 'application/json',
              Authorization: `Bearer ${adminToken}`,
            }
          : { 'Content-Type': 'application/json' },
        body: JSON.stringify({ active: nextState }),
      });
      if (res.ok) {
        setHealth((prev) =>
          prev ? { ...prev, kill_switch_active: nextState } : null,
        );
        showToast(
          nextState ? 'Kill switch activated — all bots halted' : 'Kill switch deactivated — trading resumed',
          'success',
        );
        await fetchData();
      } else {
        showToast(
          `Kill switch failed (${res.status})`,
          'error',
        );
      }
    } catch (err) {
      console.error(err);
      showToast('Kill switch service unavailable', 'error');
    } finally {
      setLoading((prev) => ({ ...prev, killSwitch: false }));
    }
  };

  const fetchCandles = async (
    symbol: string,
  ): Promise<
    { timestamp: string; open: number; high: number; low: number; close: number; volume: number }[]
  > => {
    const res = await fetch(
      `${backendUrl}/api/v1/market/candles?symbol=${encodeURIComponent(symbol)}&interval=1h&limit=20`,
    );
    if (!res.ok) throw new Error(`Market data HTTP ${res.status}`);
    const data = await res.json();
    if (Array.isArray(data)) return data;
    if (data?.candles) return data.candles;
    throw new Error('Unexpected market data format');
  };

  const handleRunBacktest = async (e: React.FormEvent) => {
    e.preventDefault();
    setBtResult(null);
    setBtChartData([]);
    setBtError(null);
    setLoading((prev) => ({ ...prev, backtest: true }));

    try {
      const candles = await fetchCandles(btSymbol);

      const res = await fetch(`${backendUrl}/api/v1/backtest/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          strategy_name: btStrategy,
          symbol: btSymbol,
          fast_period: Number(btFast),
          slow_period: Number(btSlow),
          notional: Number(btNotional),
          candles,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        const startUsdt = 10000;
        const lastClose = candles[candles.length - 1]?.close ?? 0;
        const profit =
          data.ending_usdt + data.ending_btc * lastClose - startUsdt;
        const profitPct = (profit / startUsdt) * 100;
        setBtResult({
          ...data,
          profit_pct: profitPct,
        });
        setBtChartData(candles);
      } else {
        setBtError(`Backend returned ${res.status}`);
      }
    } catch (err) {
      console.error(err);
      setBtError(
        err instanceof Error ? err.message : 'Backtest service unavailable',
      );
    } finally {
      setLoading((prev) => ({ ...prev, backtest: false }));
    }
  };

  const activeBots = bots.filter((b) => b.active);
  const ksActive = health?.kill_switch_active ?? false;

  return (
    <div
      style={{
        maxWidth: '1280px',
        margin: '0 auto',
        padding: 'clamp(16px, 4vw, 40px) clamp(12px, 3vw, 24px)',
        position: 'relative',
      }}
    >
      {/* ── Premium Background Orbs ── */}
      <div
        className="bg-orb"
        style={{
          position: 'fixed',
          top: '-15%',
          left: '-10%',
          width: '600px',
          height: '600px',
          background:
            'radial-gradient(circle, rgba(59,130,246,0.08) 0%, transparent 70%)',
          borderRadius: '50%',
          zIndex: -1,
          pointerEvents: 'none',
        }}
      />
      <div
        className="bg-orb"
        style={{
          position: 'fixed',
          bottom: '-10%',
          right: '-5%',
          width: '500px',
          height: '500px',
          background:
            'radial-gradient(circle, rgba(139,92,246,0.06) 0%, transparent 70%)',
          borderRadius: '50%',
          zIndex: -1,
          pointerEvents: 'none',
        }}
      />
      <div
        className="bg-orb"
        style={{
          position: 'fixed',
          top: '40%',
          left: '60%',
          width: '300px',
          height: '300px',
          background:
            'radial-gradient(circle, rgba(16,185,129,0.04) 0%, transparent 70%)',
          borderRadius: '50%',
          zIndex: -1,
          pointerEvents: 'none',
        }}
      />

      <h1 className="visually-hidden">{t('dashboard.title')}</h1>

      {/* ── Ticker Tape ── */}
      <div
        className="ticker-tape"
        aria-live="polite"
        style={{
          marginBottom: '28px',
          background: 'var(--bg-card)',
          borderRadius: 'var(--radius-lg)',
          padding: '10px 0',
          border: '1px solid var(--border-card)',
          backdropFilter: 'blur(12px)',
        }}
      >
        <div className="ticker-content">
          {tickerOffline || tickerData.length === 0 ? (
            <span className="ticker-item" style={{ opacity: 0.4, fontStyle: 'italic' }}>
              <span className="ticker-symbol">MARKET DATA</span>
              <span className="ticker-change" style={{ color: 'var(--text-muted)' }}>
                OFFLINE
              </span>
            </span>
          ) : (
            [...tickerData, ...tickerData].map((item, idx) => (
              <span key={`${item.symbol}-${idx}`} className="ticker-item">
                <span className="ticker-symbol">{item.symbol}</span>
                <span className="ticker-price">
                  $
                  {item.price.toLocaleString(undefined, {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                  })}
                </span>
                <span
                  className={`ticker-change ${item.changePercent >= 0 ? 'up' : 'down'}`}
                >
                  {item.changePercent >= 0 ? '+' : ''}
                  {item.changePercent.toFixed(2)}%
                </span>
              </span>
            ))
          )}
        </div>
      </div>

      {/* ── Metrics Grid ── */}
      <div className="layout-stats" style={{ marginBottom: '28px' }}>
        <div className="metric-card">
          <span className="metric-label">
            {t('dashboard.pnl')} (Real-Time)
          </span>
          <strong
            className="metric-value"
            style={{
              color:
                pnl.total >= 0
                  ? 'var(--color-accent)'
                  : 'var(--color-danger)',
            }}
          >
            {pnl.total >= 0 ? '+' : ''}
            {formatPnl(animatedPnl)} {pnl.currency}
          </strong>
          <div
            className="metric-change"
            style={{
              color:
                pnl.total >= 0
                  ? 'var(--color-accent)'
                  : 'var(--color-danger)',
            }}
          >
            <svg
              width="12"
              height="12"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              {pnl.total >= 0 ? (
                <polyline points="18 15 12 9 6 15" />
              ) : (
                <polyline points="6 9 12 15 18 9" />
              )}
            </svg>
            {pnl.total >= 0 ? 'Gain' : 'Loss'} · Live
          </div>
        </div>

        <div className="metric-card">
          <span className="metric-label">{t('dashboard.open_bots')}</span>
          <strong
            className="metric-value"
            style={{ color: 'var(--color-primary)' }}
          >
            {activeBots.length}
          </strong>
          <div className="metric-change" style={{ color: 'var(--text-muted)' }}>
            {bots.length - activeBots.length} idle · {bots.length} total
          </div>
        </div>

        <div className="metric-card">
          <span className="metric-label">{t('execution.mode')}</span>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              marginTop: '6px',
            }}
          >
            <span
              className={`status-dot ${health?.live_trading_enabled ? 'status-dot-down' : 'status-dot-up'}`}
            />
            <strong className="metric-value" style={{ fontSize: '16px' }}>
              {health?.live_trading_enabled
                ? t('execution.live')
                : t('execution.paper')}
            </strong>
          </div>
          <div className="metric-change" style={{ color: 'var(--text-muted)' }}>
            Environment: {health?.environment || '—'}
          </div>
        </div>

        <div
          className="metric-card"
          style={{
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
            borderColor: ksActive
              ? 'rgba(239,68,68,0.3)'
              : 'var(--border-card)',
          }}
        >
          <button
            onClick={handleToggleKillSwitch}
            disabled={loading.killSwitch}
            className={`btn-base ${ksActive ? 'btn-danger' : 'btn-secondary'}`}
            style={{
              width: '100%',
              padding: '16px 12px',
              fontSize: '14px',
              fontWeight: '700',
              letterSpacing: '0.03em',
            }}
          >
            <span
              className={`status-dot ${ksActive ? 'status-dot-down' : 'status-dot-up'}`}
            />
            {ksActive ? 'KILL SWITCH ACTIVE' : 'KILL SWITCH SAFE'}
          </button>
        </div>
      </div>

      {/* ── Main Body Grid ── */}
      <div className="layout-grid" style={{ marginBottom: '32px' }}>
        {/* Left Column */}
        <div style={{ display: 'grid', gap: '28px' }}>
          {/* Strategy Trigger */}
          <div className="glass-card animate-fade-in">
            <h3 className="h3" style={{ marginBottom: '20px' }}>
              {t('dashboard.launch_strategy')}
            </h3>
            <form
              onSubmit={handleStartBot}
              className="layout-2col"
              style={{ gap: '16px' }}
            >
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">
                  {t('dashboard.strategy_label')}
                </label>
                <select
                  value={selectedStrategy}
                  onChange={(e) => setSelectedStrategy(e.target.value)}
                  className="input-field"
                >
                  <option value="ma-crossover">{t('strategy.ma_crossover')}</option>
                  <option value="scalp">{t('strategy.scalp')}</option>
                  <option value="swing">{t('strategy.swing')}</option>
                  <option value="position">{t('strategy.position')}</option>
                </select>
              </div>

              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">
                  {t('dashboard.pair_label')}
                </label>
                <select
                  value={selectedSymbol}
                  onChange={(e) => setSelectedSymbol(e.target.value)}
                  className="input-field"
                >
                  <option value="BTC/USDT">BTC/USDT</option>
                  <option value="ETH/USDT">ETH/USDT</option>
                  <option value="XAU/USD">XAU/USD (Gold)</option>
                </select>
              </div>

              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">
                  {t('dashboard.notional_label')}
                </label>
                <input
                  type="number"
                  value={notional}
                  onChange={(e) => setNotional(Number(e.target.value))}
                  className="input-field font-mono"
                />
              </div>

              <div className="layout-2col" style={{ gap: '8px' }}>
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label className="form-label">
                    {t('dashboard.fast_ma')}
                  </label>
                  <input
                    type="number"
                    value={fastPeriod}
                    onChange={(e) => setFastPeriod(Number(e.target.value))}
                    className="input-field font-mono"
                  />
                </div>
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label className="form-label">
                    {t('dashboard.slow_ma')}
                  </label>
                  <input
                    type="number"
                    value={slowPeriod}
                    onChange={(e) => setSlowPeriod(Number(e.target.value))}
                    className="input-field font-mono"
                  />
                </div>
              </div>

              <div style={{ gridColumn: 'span 2' }}>
                <button
                  type="submit"
                  disabled={loading.startBot || ksActive}
                  className="btn-base btn-primary btn-full btn-lg"
                  style={{
                    opacity: ksActive ? 0.5 : 1,
                    cursor: ksActive ? 'not-allowed' : 'pointer',
                  }}
                >
                  {ksActive ? (
                    <>
                      <span className="status-dot status-dot-down" />
                      {t('dashboard.launch_prevented')}
                    </>
                  ) : (
                    <>
                      <svg
                        width="16"
                        height="16"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2.5"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      >
                        <polygon points="5 3 19 12 5 21 5 3" />
                      </svg>
                      {t('bot.start')}
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>

          {/* Active Bots */}
          <div className="glass-card animate-fade-in">
            <h3
              className="h3"
              style={{
                marginBottom: '20px',
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
              }}
            >
              {t('dashboard.active_bots')}
              {activeBots.length > 0 && (
                <span className="badge badge-accent">
                  {activeBots.length} running
                </span>
              )}
            </h3>

            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '10px',
              }}
            >
              {activeBots.map((bot) => (
                <div
                  key={bot.bot_id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '16px',
                    background: 'var(--bg-surface)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--radius-lg)',
                    transition: 'var(--transition-smooth)',
                  }}
                >
                  <div>
                    <strong
                      style={{
                        fontSize: '15px',
                        color: 'var(--text-primary)',
                      }}
                    >
                      <span
                        className="status-dot status-dot-up"
                        style={{ marginRight: '8px' }}
                      />
                      {bot.bot_id}
                    </strong>
                    <div
                      style={{
                        marginTop: '6px',
                        display: 'flex',
                        gap: '6px',
                        flexWrap: 'wrap',
                      }}
                    >
                      <span className="badge badge-primary">
                        {bot.symbol}
                      </span>
                      <span className="badge badge-secondary">
                        {bot.strategy_name}
                      </span>
                      <span className="badge badge-accent">
                        {bot.execution_mode}
                      </span>
                    </div>
                  </div>
                  <button
                    onClick={() => handleStopBot(bot.bot_id)}
                    className="btn-base btn-danger btn-sm"
                  >
                    <svg
                      width="14"
                      height="14"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <rect x="6" y="4" width="4" height="16" />
                      <rect x="14" y="4" width="4" height="16" />
                    </svg>
                    {t('bot.stop')}
                  </button>
                </div>
              ))}
              {activeBots.length === 0 && (
                <div
                  style={{
                    textAlign: 'center',
                    padding: '36px 24px',
                    color: 'var(--text-muted)',
                    fontSize: '14px',
                  }}
                >
                  <svg
                    width="32"
                    height="32"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    style={{ margin: '0 auto 12px', opacity: 0.3 }}
                  >
                    <rect x="2" y="3" width="20" height="14" rx="2" ry="2" />
                    <line x1="8" y1="21" x2="16" y2="21" />
                    <line x1="12" y1="17" x2="12" y2="21" />
                  </svg>
                  {t('dashboard.no_strategies')}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Right Column */}
        <div style={{ display: 'grid', gap: '28px' }}>
          {/* Backtest */}
          <div className="glass-card animate-fade-in">
            <h3 className="h3" style={{ marginBottom: '16px' }}>
              {t('dashboard.backtest_title')}
            </h3>
            <form onSubmit={handleRunBacktest}>
              <div className="form-group" style={{ marginBottom: '14px' }}>
                <label className="form-label">{t('dashboard.strategy_label')}</label>
                <select
                  value={btStrategy}
                  onChange={(e) => setBtStrategy(e.target.value)}
                  className="input-field"
                >
                  <option value="ma-crossover">{t('strategy.ma_crossover')}</option>
                  <option value="scalp">{t('strategy.scalp')}</option>
                  <option value="swing">{t('strategy.swing')}</option>
                  <option value="position">{t('strategy.position')}</option>
                </select>
              </div>

              <div
                className="layout-2col"
                style={{ gap: '12px', marginBottom: '14px' }}
              >
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label className="form-label">
                    {t('dashboard.backtest_pair')}
                  </label>
                  <select
                    value={btSymbol}
                    onChange={(e) => setBtSymbol(e.target.value)}
                    className="input-field"
                  >
                    <option value="BTC/USDT">BTC/USDT</option>
                    <option value="ETH/USDT">ETH/USDT</option>
                    <option value="XAU/USD">XAU/USD (Gold)</option>
                  </select>
                </div>
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label className="form-label">
                    {t('dashboard.backtest_notional')}
                  </label>
                  <input
                    type="number"
                    value={btNotional}
                    onChange={(e) => setBtNotional(Number(e.target.value))}
                    className="input-field font-mono"
                  />
                </div>
              </div>

              <div
                className="layout-2col"
                style={{ gap: '12px', marginBottom: '18px' }}
              >
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label className="form-label">
                    {t('dashboard.backtest_fast')}
                  </label>
                  <input
                    type="number"
                    value={btFast}
                    onChange={(e) => setBtFast(Number(e.target.value))}
                    className="input-field font-mono"
                  />
                </div>
                <div className="form-group" style={{ marginBottom: 0 }}>
                  <label className="form-label">
                    {t('dashboard.backtest_slow')}
                  </label>
                  <input
                    type="number"
                    value={btSlow}
                    onChange={(e) => setBtSlow(Number(e.target.value))}
                    className="input-field font-mono"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={loading.backtest}
                className="btn-base btn-secondary btn-full"
                style={{ color: 'var(--color-primary-light)' }}
              >
                {loading.backtest ? (
                  <Shimmer w="80px" h="16px" />
                ) : (
                  <>
                    <svg
                      width="16"
                      height="16"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <polyline points="23 6 13.5 15.5 8.5 10.5 1 18" />
                      <polyline points="17 6 23 6 23 12" />
                    </svg>
                    {t('dashboard.backtest_run')}
                  </>
                )}
              </button>
            </form>

            {btError && (
              <div
                style={{
                  marginTop: '16px',
                  padding: '14px 18px',
                  borderRadius: 'var(--radius-md)',
                  background: 'rgba(239,68,68,0.08)',
                  border: '1px solid rgba(239,68,68,0.25)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  fontSize: '13px',
                  color: 'var(--color-danger)',
                }}
              >
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <circle cx="12" cy="12" r="10" />
                  <line x1="12" y1="8" x2="12" y2="12" />
                  <line x1="12" y1="16" x2="12.01" y2="16" />
                </svg>
                <span>{btError}</span>
                <button
                  onClick={() => setBtError(null)}
                  style={{
                    marginLeft: 'auto',
                    background: 'none',
                    border: 'none',
                    color: 'inherit',
                    cursor: 'pointer',
                    opacity: 0.6,
                    fontSize: '16px',
                    lineHeight: 1,
                  }}
                >
                  &times;
                </button>
              </div>
            )}

            {btResult && (
              <div
                className="animate-scale-in"
                style={{
                  marginTop: '20px',
                  padding: '20px',
                  background: 'var(--bg-surface)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius-lg)',
                }}
              >
                <strong
                  className="form-label"
                  style={{ marginBottom: '16px' }}
                >
                  {t('dashboard.backtest_outcome')}
                </strong>
                <div className="layout-2col" style={{ gap: '16px' }}>
                  <div>
                    <span
                      className="text-muted"
                      style={{ fontSize: '12px', display: 'block' }}
                    >
                      {t('dashboard.backtest_candles')}
                    </span>
                    <strong
                      className="font-mono"
                      style={{ fontSize: '16px' }}
                    >
                      {btResult.candles_seen}
                    </strong>
                  </div>
                  <div>
                    <span
                      className="text-muted"
                      style={{ fontSize: '12px', display: 'block' }}
                    >
                      {t('dashboard.backtest_orders')}
                    </span>
                    <strong
                      className="font-mono"
                      style={{ fontSize: '16px' }}
                    >
                      {btResult.orders_created}
                    </strong>
                  </div>
                  <div>
                    <span
                      className="text-muted"
                      style={{ fontSize: '12px', display: 'block' }}
                    >
                      {t('dashboard.backtest_usdt')}
                    </span>
                    <strong
                      className="font-mono"
                      style={{ fontSize: '16px' }}
                    >
                      ${btResult.ending_usdt.toFixed(2)}
                    </strong>
                  </div>
                  <div>
                    <span
                      className="text-muted"
                      style={{ fontSize: '12px', display: 'block' }}
                    >
                      {t('dashboard.backtest_asset')}
                    </span>
                    <strong
                      className="font-mono"
                      style={{ fontSize: '16px' }}
                    >
                      {btResult.ending_btc.toFixed(4)}
                    </strong>
                  </div>
                </div>
                <div className="divider" />
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                  }}
                >
                  <span
                    className="text-muted"
                    style={{ fontSize: '12px' }}
                  >
                    {t('dashboard.backtest_return')}
                  </span>
                  <strong
                    style={{
                      fontSize: '22px',
                      color:
                        btResult.profit_pct >= 0
                          ? 'var(--color-accent)'
                          : 'var(--color-danger)',
                    }}
                  >
                    {btResult.profit_pct >= 0 ? '+' : ''}
                    {btResult.profit_pct.toFixed(2)}%
                  </strong>
                </div>
                {btChartData.length > 0 && (
                  <div
                    style={{
                      marginTop: '16px',
                      borderRadius: 'var(--radius-md)',
                      overflow: 'hidden',
                      border: '1px solid var(--border-subtle)',
                    }}
                  >
                    <ChartWidget data={btChartData} />
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Risk Engine */}
          <div className="glass-card animate-fade-in">
            <h3 className="h3" style={{ marginBottom: '20px' }}>
              {t('risk.limits')}
            </h3>
            {riskLimits ? (
              <div
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '20px',
                }}
              >
                <div>
                  <span className="form-label">
                    {t('risk.max_notional')}
                  </span>
                  <strong
                    className="metric-value"
                    style={{
                      fontSize: '20px',
                      color: 'var(--color-primary)',
                    }}
                  >
                    ${riskLimits.max_notional.toFixed(2)} USDT
                  </strong>
                </div>

                <div>
                  <span className="form-label">
                    {t('risk.allowed_symbols')}
                  </span>
                  <div
                    style={{
                      display: 'flex',
                      gap: '8px',
                      flexWrap: 'wrap',
                      marginTop: '6px',
                    }}
                  >
                    {riskLimits.allowed_symbols.length > 0 ? (
                      riskLimits.allowed_symbols.map((sym) => (
                        <span key={sym} className="badge badge-primary">
                          {sym}
                        </span>
                      ))
                    ) : (
                      <span className="text-muted" style={{ fontSize: '13px' }}>
                        No symbols configured
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <Shimmer h="32px" w="140px" />
                <Shimmer h="24px" w="200px" />
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Audit Logs ── */}
      <div className="glass-card animate-fade-in">
        <h3
          className="h3"
          style={{
            marginBottom: '20px',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
          }}
        >
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="16" y1="13" x2="8" y2="13" />
            <line x1="16" y1="17" x2="8" y2="17" />
          </svg>
          {t('audit.logs')}
        </h3>

        <div className="table-wrapper">
    <table className="table-base">
      <caption className="visually-hidden">{t('dashboard.audit_log')}</caption>
      <thead>
        <tr>
          <th scope="col" className="table-th">Timestamp</th>
          <th scope="col" className="table-th">Event Type</th>
          <th scope="col" className="table-th">Actor</th>
          <th scope="col" className="table-th">Severity</th>
          <th scope="col" className="table-th">Message</th>
        </tr>
      </thead>
      <tbody>
              {auditLogs.map((log) => (
                <tr key={log.id} className="table-tr">
                  <td
                    className="table-td"
                    style={{ color: 'var(--text-secondary)' }}
                    data-label={t('dashboard.audit_timestamp')}
                  >
                    {new Date(log.created_at).toLocaleTimeString()}
                  </td>
                  <td className="table-td" style={{ fontWeight: '500' }} data-label={t('dashboard.audit_event_type')}>
                    {log.event_type}
                  </td>
                  <td
                    className="table-td"
                    style={{ color: 'var(--text-secondary)' }}
                    data-label={t('dashboard.audit_actor')}
                  >
                    {log.actor}
                  </td>
                  <td className="table-td" data-label={t('dashboard.audit_severity')}>
                    <span
                      className={`badge ${log.severity === 'critical' ? 'badge-danger' : log.severity === 'warning' ? 'badge-warning' : 'badge-info'}`}
                    >
                      {log.severity.toUpperCase()}
                    </span>
                  </td>
                  <td
                    className="table-td"
                    style={{ color: 'var(--text-muted)' }}
                    data-label={t('dashboard.audit_message')}
                  >
                    {log.message}
                  </td>
                </tr>
              ))}
              {auditLogs.length === 0 && (
                <tr>
                  <td
                    colSpan={5}
                    style={{
                      textAlign: 'center',
                      padding: 'clamp(16px, 6vw, 40px)',
                      color: 'var(--text-muted)',
                      fontStyle: 'italic',
                    }}
                  >
                    {t('dashboard.no_audit')}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {toast && (
        <div
          className="toast-container animate-slide-up"
          role="alert"
          aria-live="assertive"
          style={{
            position: 'fixed',
            bottom: '28px',
            right: '28px',
            zIndex: 9999,
            padding: '14px 20px',
            borderRadius: 'var(--radius-lg)',
            background: toast.type === 'success'
              ? 'rgba(10,26,20,0.97)'
              : 'rgba(26,10,10,0.97)',
            border: `1px solid ${toast.type === 'success' ? 'rgba(16,185,129,0.4)' : 'rgba(239,68,68,0.4)'}`,
            color: toast.type === 'success' ? '#10B981' : '#EF4444',
            fontSize: '14px',
            fontWeight: '600',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            boxShadow: `0 8px 32px ${toast.type === 'success' ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.15)'}`,
            backdropFilter: 'blur(12px)',
            WebkitBackdropFilter: 'blur(12px)',
            maxWidth: '420px',
          }}
        >
          {toast.type === 'success' ? (
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="20 6 9 17 4 12" />
            </svg>
          ) : (
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
          )}
          {toast.msg}
        </div>
      )}
    </div>
  );
}
