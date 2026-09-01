"use client";

import React, { useEffect, useState, useCallback, useRef } from 'react';
import { usePathname } from 'next/navigation';
import { initI18n } from '../../i18n/client';
import { useTranslation } from 'react-i18next';
import { Toast } from '../../../components/Toast';

interface SystemHealth {
  status: string;
  uptime: string;
  cpu_usage: number;
  memory_usage: number;
  services: {
    postgres: boolean;
    redis: boolean;
    backend: boolean;
    celery: boolean;
    frontend: boolean;
  };
}

interface BotStatus {
  id: string;
  strategy_name: string;
  symbol: string;
  status: 'Running' | 'Stopped' | 'Error';
  execution_mode: 'Live' | 'Paper';
}

interface AuditLog {
  id: string;
  timestamp: string;
  severity: 'INFO' | 'WARN' | 'ERROR' | 'CRITICAL';
  message: string;
}

interface RiskLimits {
  kill_switch_active: boolean;
  max_notional: number;
  allowed_symbols: string[];
  current_exposure: number;
  position_limits: number;
}

interface WebhookAlert {
  id: string;
  timestamp: string;
  success: boolean;
  payload: string;
}

type TabKey = 'overview' | 'performance' | 'bots' | 'risk' | 'history' | 'webhooks';

function Shimmer({ w = '100%', h = '16px' }: { w?: string; h?: string }) {
  return <div className="shimmer" style={{ width: w, height: h, borderRadius: 'var(--radius-sm)' }} />;
}

function StatusDot({ ok, pulse = false }: { ok: boolean; pulse?: boolean }) {
  return (
    <span
      className={`status-dot ${ok ? 'status-dot-up' : 'status-dot-down'}`}
      style={{
        boxShadow: pulse && ok ? '0 0 8px rgba(16,185,129,0.6)' : pulse && !ok ? '0 0 8px rgba(239,68,68,0.6)' : 'none',
        animation: pulse ? 'pulse 2s infinite' : 'none'
      }}
    />
  );
}

function SeverityBadge({ severity }: { severity: string }) {
  const colors: Record<string, string> = {
    INFO: 'badge-info',
    WARN: 'badge-warning',
    ERROR: 'badge-danger',
    CRITICAL: 'badge-danger',
  };
  const cls = colors[severity] || 'badge-secondary';
  return <span className={`badge ${cls}`}>{severity}</span>;
}

export default function AdminDashboardPage() {
  const pathname = usePathname();
  const lng = pathname?.split('/')[1] || 'en';
  initI18n(lng);
  const { t } = useTranslation('translation');

  const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

  const [tab, setTab] = useState<TabKey>('overview');
  const [paperMode, setPaperMode] = useState(false);
  const [toast, setToast] = useState<{ msg: string; type: 'success' | 'error' } | null>(null);

  // Mocks and states
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [bots, setBots] = useState<BotStatus[]>([]);
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [risk, setRisk] = useState<RiskLimits | null>(null);
  const [webhooks, setWebhooks] = useState<WebhookAlert[]>([]);
  const [loading, setLoading] = useState(true);

  const showToast = useCallback((msg: string, type: 'success' | 'error') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3000);
  }, []);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      // Simulate API fetches
      setHealth({
        status: 'Operational',
        uptime: '99.99%',
        cpu_usage: 45,
        memory_usage: 60,
        services: { postgres: true, redis: true, backend: true, celery: true, frontend: true }
      });
      setBots([
        { id: '1', strategy_name: 'Grid_BTC', symbol: 'BTC/USDT', status: 'Running', execution_mode: 'Live' },
        { id: '2', strategy_name: 'RSI_ETH', symbol: 'ETH/USDT', status: 'Stopped', execution_mode: 'Paper' },
        { id: '3', strategy_name: 'MACD_SOL', symbol: 'SOL/USDT', status: 'Error', execution_mode: 'Live' },
      ]);
      setRisk({
        kill_switch_active: false,
        max_notional: 100000,
        allowed_symbols: ['BTC/USDT', 'ETH/USDT', 'SOL/USDT'],
        current_exposure: 45000,
        position_limits: 50000,
      });
      setLogs([
        { id: '1', timestamp: new Date().toISOString(), severity: 'INFO', message: 'Bot Grid_BTC started' },
        { id: '2', timestamp: new Date(Date.now() - 3600000).toISOString(), severity: 'WARN', message: 'API rate limit nearing' },
        { id: '3', timestamp: new Date(Date.now() - 7200000).toISOString(), severity: 'ERROR', message: 'Failed to execute order MACD_SOL' },
      ]);
      setWebhooks([
        { id: '1', timestamp: new Date().toISOString(), success: true, payload: '{"action": "buy", "symbol": "BTC/USDT"}' },
        { id: '2', timestamp: new Date(Date.now() - 1800000).toISOString(), success: false, payload: '{"action": "sell", "symbol": "INVALID"}' },
      ]);
    } catch (e) {
      showToast('Failed to load data', 'error');
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    fetchData();
    const intv = setInterval(fetchData, 30000);
    return () => clearInterval(intv);
  }, [fetchData]);

  const toggleKillSwitch = () => {
    if (risk) {
      setRisk({ ...risk, kill_switch_active: !risk.kill_switch_active });
      showToast(risk.kill_switch_active ? 'Kill Switch Deactivated' : 'Kill Switch ACTIVATED', risk.kill_switch_active ? 'success' : 'error');
    }
  };

  const emergencyStopAll = () => {
    showToast('Emergency Stop Triggered - All Bots Halted', 'error');
    setBots(bots.map(b => ({ ...b, status: 'Stopped' })));
  };

  return (
    <div style={{ maxWidth: '1440px', margin: '0 auto', padding: '32px 24px', minHeight: '100vh', display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <style>{`
        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
        .dashboard-tab { padding: 12px 24px; border-radius: var(--radius-lg); font-weight: 600; cursor: pointer; transition: all 0.2s; color: var(--text-muted); background: transparent; border: none; font-size: 14px; }
        .dashboard-tab:hover { color: var(--text-primary); background: rgba(255,255,255,0.05); }
        .dashboard-tab.active { color: var(--color-primary-light); background: var(--color-primary-bg); border: 1px solid var(--color-primary-border); }
        .metric-bar-bg { height: 8px; background: rgba(255,255,255,0.1); border-radius: 4px; overflow: hidden; }
        .metric-bar-fill { height: 100%; transition: width 0.5s ease-out; }
      `}</style>

      {/* ── Quick Actions Toolbar ── */}
      <div className="glass-card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px 24px', flexWrap: 'wrap', gap: '16px' }}>
        <div style={{ display: 'flex', gap: '16px', alignItems: 'center', flexWrap: 'wrap' }}>
          <h1 className="h2 font-mono" style={{ margin: 0 }}>zTrader Admin</h1>
          <div className="divider" style={{ width: '1px', height: '24px' }} />
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            {['overview', 'performance', 'bots', 'risk', 'history', 'webhooks'].map((tKey) => (
              <button key={tKey} className={`dashboard-tab ${tab === tKey ? 'active' : ''}`} onClick={() => setTab(tKey as TabKey)}>
                {tKey.charAt(0).toUpperCase() + tKey.slice(1)}
              </button>
            ))}
          </div>
        </div>
        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
          <button className="btn-base btn-ghost" onClick={fetchData}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{marginRight: '8px'}}><path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2"/></svg>
            Refresh
          </button>
          <button className="btn-base btn-ghost" onClick={() => showToast('Report Exported', 'success')}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{marginRight: '8px'}}><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>
            Export
          </button>
          <button className="btn-base" style={{ background: 'rgba(255,255,255,0.1)' }} onClick={() => setPaperMode(!paperMode)}>
            {paperMode ? 'Paper Mode' : 'Live Mode'}
          </button>
          <button className="btn-base btn-danger" onClick={emergencyStopAll}>
            Emergency Stop
          </button>
        </div>
      </div>

      <div style={{ flex: 1 }}>
        {/* ── OVERVIEW ── */}
        {tab === 'overview' && health && (
          <div className="layout-grid animate-fade-in-up" style={{ gridTemplateColumns: 'repeat(3, 1fr)', gap: '24px' }}>
            <div className="glass-card layout-stats" style={{ gridColumn: 'span 2' }}>
              <h2 className="h3">System Health Overview</h2>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px', marginTop: '16px' }}>
                <div className="metric-card">
                  <div className="text-muted">CPU Usage</div>
                  <div style={{ display: 'flex', alignItems: 'end', gap: '8px', margin: '8px 0' }}>
                    <div className="h2">{health.cpu_usage}%</div>
                  </div>
                  <div className="metric-bar-bg">
                    <div className="metric-bar-fill" style={{ width: `${health.cpu_usage}%`, background: 'var(--color-primary)' }} />
                  </div>
                </div>
                <div className="metric-card">
                  <div className="text-muted">Memory Usage</div>
                  <div style={{ display: 'flex', alignItems: 'end', gap: '8px', margin: '8px 0' }}>
                    <div className="h2">{health.memory_usage}%</div>
                  </div>
                  <div className="metric-bar-bg">
                    <div className="metric-bar-fill" style={{ width: `${health.memory_usage}%`, background: 'var(--color-accent)' }} />
                  </div>
                </div>
              </div>
              <div style={{ marginTop: '24px', display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
                {Object.entries(health.services).map(([srv, ok]) => (
                  <div key={srv} className="badge badge-secondary" style={{ padding: '8px 16px', fontSize: '14px', display: 'flex', gap: '8px', alignItems: 'center' }}>
                    <StatusDot ok={ok} pulse={ok} /> {srv.toUpperCase()}
                  </div>
                ))}
              </div>
            </div>

            <div className="glass-card-accent">
              <h2 className="h3">Exchange API Status</h2>
              <div style={{ marginTop: '16px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div style={{ padding: '16px', background: 'rgba(0,0,0,0.2)', borderRadius: 'var(--radius-md)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                    <strong>Binance EN</strong>
                    <StatusDot ok={true} pulse />
                  </div>
                  <div className="text-muted" style={{ fontSize: '12px' }}>Rate Limit: 45/1200</div>
                  <div className="metric-bar-bg" style={{ marginTop: '4px' }}>
                    <div className="metric-bar-fill" style={{ width: '15%', background: 'var(--color-accent)' }} />
                  </div>
                </div>
                <div style={{ padding: '16px', background: 'rgba(0,0,0,0.2)', borderRadius: 'var(--radius-md)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                    <strong>Binance TH</strong>
                    <StatusDot ok={true} pulse />
                  </div>
                  <div className="text-muted" style={{ fontSize: '12px' }}>Rate Limit: 120/1200</div>
                  <div className="metric-bar-bg" style={{ marginTop: '4px' }}>
                    <div className="metric-bar-fill" style={{ width: '35%', background: 'var(--color-warning)' }} />
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ── PERFORMANCE ── */}
        {tab === 'performance' && (
          <div className="animate-fade-in-up">
            <div className="glass-card" style={{ marginBottom: '24px' }}>
              <h2 className="h3">Trading Performance Analytics</h2>
              <div style={{ height: '300px', background: 'rgba(255,255,255,0.02)', border: '1px dashed rgba(255,255,255,0.1)', borderRadius: 'var(--radius-md)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginTop: '16px' }}>
                <span className="text-muted font-mono">[ Portfolio Value Chart Placeholder ]</span>
              </div>
            </div>
            <div className="layout-3col">
              <div className="metric-card">
                <div className="text-muted">Total PnL</div>
                <div className="h2" style={{ color: 'var(--color-accent)', margin: '8px 0' }}>+$12,450.00</div>
                <div className="text-muted font-mono" style={{ fontSize: '12px' }}>Grid_BTC: +$8k | RSI_ETH: +$4.45k</div>
              </div>
              <div className="metric-card">
                <div className="text-muted">Win Rate Gauge</div>
                <div className="h2" style={{ margin: '8px 0' }}>68.5%</div>
                <div className="metric-bar-bg">
                  <div className="metric-bar-fill" style={{ width: '68.5%', background: 'var(--color-primary)' }} />
                </div>
              </div>
              <div className="metric-card">
                <div className="text-muted">Sharpe Ratio</div>
                <div className="h2" style={{ color: 'var(--color-accent)', margin: '8px 0' }}>2.14</div>
                <div className="text-muted font-mono" style={{ fontSize: '12px' }}>Excellent Risk-Adjusted Return</div>
              </div>
            </div>
          </div>
        )}

        {/* ── BOTS ── */}
        {tab === 'bots' && (
          <div className="glass-card animate-fade-in-up">
            <h2 className="h3" style={{ marginBottom: '16px' }}>Bot Management Console</h2>
            <div className="table-wrapper">
              <table className="table-base" style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
                    <th className="table-th" style={{ padding: '12px', textAlign: 'left' }}>Strategy</th>
                    <th className="table-th" style={{ padding: '12px', textAlign: 'left' }}>Symbol</th>
                    <th className="table-th" style={{ padding: '12px', textAlign: 'left' }}>Status</th>
                    <th className="table-th" style={{ padding: '12px', textAlign: 'left' }}>Mode</th>
                    <th className="table-th" style={{ padding: '12px', textAlign: 'right' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {bots.map(b => (
                    <tr key={b.id} className="table-tr" style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                      <td className="table-td font-mono" style={{ padding: '12px' }}>{b.strategy_name}</td>
                      <td className="table-td" style={{ padding: '12px' }}>{b.symbol}</td>
                      <td className="table-td" style={{ padding: '12px' }}>
                        <span className={`badge ${b.status === 'Running' ? 'badge-accent' : b.status === 'Stopped' ? 'badge-secondary' : 'badge-danger'}`}>
                          {b.status}
                        </span>
                      </td>
                      <td className="table-td" style={{ padding: '12px' }}>{b.execution_mode}</td>
                      <td className="table-td" style={{ padding: '12px', textAlign: 'right' }}>
                        <button className="btn-base btn-sm" style={{ marginRight: '8px' }}>
                          {b.status === 'Running' ? 'Stop' : 'Start'}
                        </button>
                        <button className="btn-base btn-ghost btn-sm">Configure</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* ── RISK ── */}
        {tab === 'risk' && risk && (
          <div className="layout-2col animate-fade-in-up" style={{ gap: '24px' }}>
            <div className="glass-card" style={{ borderColor: risk.kill_switch_active ? 'var(--color-danger)' : 'var(--border-card)', transition: 'all 0.3s' }}>
              <h2 className="h3" style={{ color: risk.kill_switch_active ? 'var(--color-danger)' : 'inherit' }}>Kill Switch</h2>
              <p className="text-muted" style={{ margin: '16px 0' }}>Immediately halts all trading activity, cancels open orders, and stops all bots.</p>
              <button 
                className={`btn-base ${risk.kill_switch_active ? 'btn-danger' : 'btn-primary'}`} 
                style={{ width: '100%', padding: '16px', fontSize: '18px', fontWeight: 'bold' }}
                onClick={toggleKillSwitch}
              >
                {risk.kill_switch_active ? 'DEACTIVATE KILL SWITCH' : 'ACTIVATE KILL SWITCH'}
              </button>
            </div>
            
            <div className="glass-card">
              <h2 className="h3">Risk Parameters</h2>
              <div style={{ marginTop: '16px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div className="metric-card">
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                    <span className="text-muted">Current Exposure / Position Limits</span>
                    <span className="font-mono">${risk.current_exposure.toLocaleString()} / ${risk.max_notional.toLocaleString()}</span>
                  </div>
                  <div className="metric-bar-bg">
                    <div className="metric-bar-fill" style={{ width: `${(risk.current_exposure / risk.max_notional) * 100}%`, background: 'var(--color-warning)' }} />
                  </div>
                </div>
                <div>
                  <div className="text-muted" style={{ marginBottom: '8px' }}>Allowed Symbols</div>
                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                    {risk.allowed_symbols.map(s => <span key={s} className="badge badge-primary">{s}</span>)}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ── HISTORY ── */}
        {tab === 'history' && (
          <div className="glass-card animate-fade-in-up">
            <h2 className="h3" style={{ marginBottom: '16px' }}>Audit Log & Order History</h2>
            <div className="table-wrapper">
              <table className="table-base" style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
                    <th className="table-th" style={{ padding: '12px', textAlign: 'left' }}>Timestamp</th>
                    <th className="table-th" style={{ padding: '12px', textAlign: 'left' }}>Severity</th>
                    <th className="table-th" style={{ padding: '12px', textAlign: 'left' }}>Message</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.map(l => (
                    <tr key={l.id} className="table-tr" style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                      <td className="table-td text-muted font-mono" style={{ fontSize: '13px', padding: '12px' }}>{new Date(l.timestamp).toLocaleString()}</td>
                      <td className="table-td" style={{ padding: '12px' }}><SeverityBadge severity={l.severity} /></td>
                      <td className="table-td" style={{ padding: '12px' }}>{l.message}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div style={{ display: 'flex', justifyContent: 'center', marginTop: '16px', gap: '8px' }}>
                <button className="btn-base btn-ghost btn-sm">Prev</button>
                <button className="btn-base btn-ghost btn-sm">Next</button>
              </div>
            </div>
          </div>
        )}

        {/* ── WEBHOOKS ── */}
        {tab === 'webhooks' && (
          <div className="glass-card animate-fade-in-up">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h2 className="h3">TradingView Webhook Monitor</h2>
              <div style={{ display: 'flex', gap: '16px' }}>
                <span className="text-muted">Success: <span style={{color: 'var(--color-accent)'}}>{webhooks.filter(w => w.success).length}</span></span>
                <span className="text-muted">Failed: <span style={{color: 'var(--color-danger)'}}>{webhooks.filter(w => !w.success).length}</span></span>
              </div>
            </div>
            <div className="table-wrapper">
              <table className="table-base" style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
                    <th className="table-th" style={{ padding: '12px', textAlign: 'left' }}>Timestamp</th>
                    <th className="table-th" style={{ padding: '12px', textAlign: 'left' }}>Status</th>
                    <th className="table-th" style={{ padding: '12px', textAlign: 'left' }}>Payload Inspector</th>
                  </tr>
                </thead>
                <tbody>
                  {webhooks.map(w => (
                    <tr key={w.id} className="table-tr" style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                      <td className="table-td text-muted font-mono" style={{ fontSize: '13px', padding: '12px' }}>{new Date(w.timestamp).toLocaleString()}</td>
                      <td className="table-td" style={{ padding: '12px' }}><StatusDot ok={w.success} /> <span style={{marginLeft:'8px'}}>{w.success ? 'Success' : 'Failed'}</span></td>
                      <td className="table-td font-mono" style={{ fontSize: '12px', padding: '12px' }}>
                        <div style={{ background: 'rgba(0,0,0,0.2)', padding: '8px', borderRadius: '4px' }}>
                           {w.payload}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
      
      {toast && <Toast msg={toast.msg} type={toast.type} />}
    </div>
  );
}
