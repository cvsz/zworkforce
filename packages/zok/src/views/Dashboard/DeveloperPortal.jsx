import { useState, useEffect } from 'react';
import { Code2, Terminal, Activity, Upload, CheckCircle, AlertTriangle, Clock, Zap, Database, Shield, ArrowRight, Copy, RefreshCw } from 'lucide-react';

const API_ENDPOINTS = [
  { method: 'GET', path: '/v1/conversations', desc: 'List all conversations', rateLimit: '1000/min', status: 200 },
  { method: 'POST', path: '/v1/messages/send', desc: 'Send a message via channel', rateLimit: '500/min', status: 200 },
  { method: 'GET', path: '/v1/contacts/{id}', desc: 'Retrieve contact details', rateLimit: '2000/min', status: 200 },
  { method: 'POST', path: '/v1/ai/respond', desc: 'Trigger AI response for message', rateLimit: '200/min', status: 200 },
  { method: 'DELETE', path: '/v1/conversations/{id}', desc: 'Archive conversation', rateLimit: '100/min', status: 204 },
  { method: 'POST', path: '/v1/webhooks', desc: 'Register a webhook endpoint', rateLimit: '50/min', status: 201 },
];

const HEALTH_METRICS = [
  { label: 'API Gateway', value: 99.99, unit: '%', status: 'ok', trend: '+0.01' },
  { label: 'Message Queue', value: 12, unit: 'ms', status: 'ok', trend: '-3ms' },
  { label: 'AI Inference', value: 187, unit: 'ms', status: 'warning', trend: '+24ms' },
  { label: 'Database Read', value: 4, unit: 'ms', status: 'ok', trend: '-1ms' },
  { label: 'Webhook Delivery', value: 98.7, unit: '%', status: 'ok', trend: '+0.2' },
  { label: 'LINE Channel', value: 100, unit: '%', status: 'ok', trend: '0' },
];

const MIGRATION_STEPS = [
  { id: 'upload', label: 'Upload File', desc: 'CSV / Excel up to 500k rows', icon: <Upload size={16} /> },
  { id: 'map', label: 'Map Columns', desc: 'Match fields to Zok schema', icon: <Database size={16} /> },
  { id: 'validate', label: 'Validate', desc: 'Check for duplicates & errors', icon: <Shield size={16} /> },
  { id: 'import', label: 'Import', desc: 'One-click bulk import', icon: <CheckCircle size={16} /> },
];

const SAMPLE_CURL = `curl -X POST https://api.zok.app/v1/messages/send \\
  -H "Authorization: Bearer zok_live_xxxxxxxxxxx" \\
  -H "Content-Type: application/json" \\
  -d '{
    "channel": "line",
    "contact_id": "c_0x4ef9",
    "message": {
      "type": "text",
      "content": "สวัสดีครับ มีอะไรให้ช่วยไหมครับ?"
    }
  }'`;

export default function DeveloperPortal() {
  const [activeTab, setActiveTab] = useState('api');
  const [migrationStep, setMigrationStep] = useState(0);
  const [migrating, setMigrating] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [copied, setCopied] = useState(false);
  const [healthData, setHealthData] = useState(HEALTH_METRICS);
  const [slaUptime, setSlaUptime] = useState('99.99%');
  const [latencyHistory, setLatencyHistory] = useState([12, 14, 11, 13, 15, 12, 11, 10, 12, 14, 13, 12]);

  // Simulate real-time health updates
  useEffect(() => {
    const interval = setInterval(() => {
      setHealthData(prev => prev.map(m => ({
        ...m,
        value: m.unit === 'ms'
          ? Math.max(5, m.value + (Math.random() > 0.5 ? 1 : -1) * Math.floor(Math.random() * 4))
          : Math.min(100, Math.max(98, m.value + (Math.random() > 0.5 ? 0.01 : -0.01)))
      })));
      setLatencyHistory(prev => [...prev.slice(1), Math.floor(Math.random() * 20) + 5]);
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  const handleCopy = () => {
    navigator.clipboard.writeText(SAMPLE_CURL).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleStartMigration = () => {
    setMigrating(true);
    setUploadProgress(0);
    setMigrationStep(0);
    const stepTimings = [800, 1400, 1200, 1600];
    let cumulative = 0;
    MIGRATION_STEPS.forEach((_, i) => {
      cumulative += stepTimings[i];
      setTimeout(() => {
        setMigrationStep(i + 1);
        if (i === MIGRATION_STEPS.length - 1) setMigrating(false);
      }, cumulative);
    });
    const progressInterval = setInterval(() => {
      setUploadProgress(p => {
        if (p >= 100) { clearInterval(progressInterval); return 100; }
        return p + 2;
      });
    }, 100);
  };

  const tabs = [
    { id: 'api', label: 'API Docs', icon: <Code2 size={15} /> },
    { id: 'health', label: 'System Health', icon: <Activity size={15} /> },
    { id: 'migration', label: 'Data Migration', icon: <Database size={15} /> },
  ];

  const statusColor = { ok: '#10b981', warning: '#f59e0b', error: '#ef4444' };
  const methodColor = { GET: '#10b981', POST: '#3b82f6', DELETE: '#ef4444', PUT: '#f59e0b' };

  return (
    <div style={{ padding: '2rem', height: '100%', overflowY: 'auto' }}>
      {/* Header */}
      <div style={{ marginBottom: '1.75rem' }}>
        <h2 style={{ fontSize: '1.75rem', color: '#fff', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <Terminal size={28} style={{ color: 'var(--primary-color)' }} />
          Developer Portal
        </h2>
        <p style={{ color: '#94a3b8', fontSize: '0.9rem', marginTop: '0.25rem' }}>
          API documentation, system health monitoring, and data migration tools — all in one place.
        </p>
      </div>

      {/* Sandbox Banner */}
      <div style={{
        background: 'linear-gradient(135deg, rgba(0,194,142,0.08) 0%, rgba(59,130,246,0.06) 100%)',
        border: '1px solid rgba(0,194,142,0.2)',
        borderRadius: '12px',
        padding: '1rem 1.5rem',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: '1.75rem',
        flexWrap: 'wrap',
        gap: '1rem'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <Zap size={20} style={{ color: 'var(--primary-color)' }} />
          <div>
            <div style={{ color: '#fff', fontWeight: '600', fontSize: '0.95rem' }}>Sandbox Environment Active</div>
            <div style={{ color: '#94a3b8', fontSize: '0.8rem' }}>API Key: <code style={{ color: 'var(--primary-color)', fontSize: '0.75rem' }}>zok_sandbox_sk_demo_xxxxxxxxxxx</code></div>
          </div>
        </div>
        <div style={{ display: 'flex', gap: '2rem', alignItems: 'center' }}>
          {[{ label: 'Calls Today', value: '1,247' }, { label: 'Rate Limit', value: '5,000/hr' }, { label: 'SLA', value: slaUptime }].map(s => (
            <div key={s.label} style={{ textAlign: 'center' }}>
              <div style={{ color: 'var(--primary-color)', fontWeight: '700', fontSize: '1.1rem' }}>{s.value}</div>
              <div style={{ color: '#64748b', fontSize: '0.7rem' }}>{s.label}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Tab Bar */}
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem' }}>
        {tabs.map(t => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id)}
            style={{
              display: 'flex', alignItems: 'center', gap: '0.4rem',
              padding: '0.5rem 1rem',
              borderRadius: '8px',
              border: 'none',
              cursor: 'pointer',
              fontSize: '0.85rem',
              fontWeight: activeTab === t.id ? '600' : '400',
              background: activeTab === t.id ? 'var(--primary-color)' : 'rgba(255,255,255,0.05)',
              color: activeTab === t.id ? '#fff' : '#94a3b8',
              transition: 'all 0.2s'
            }}
          >
            {t.icon}{t.label}
          </button>
        ))}
      </div>

      {/* API Docs Tab */}
      {activeTab === 'api' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 420px', gap: '1.5rem' }}>
          <div>
            <h3 style={{ color: '#fff', fontSize: '1rem', marginBottom: '1rem' }}>REST API Reference</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {API_ENDPOINTS.map((ep, i) => (
                <div key={i} style={{
                  background: '#0f172a',
                  border: '1px solid rgba(255,255,255,0.05)',
                  borderRadius: '10px',
                  padding: '1rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '1rem',
                  cursor: 'pointer',
                  transition: 'border-color 0.2s'
                }}>
                  <span style={{
                    padding: '0.2rem 0.5rem',
                    borderRadius: '4px',
                    fontSize: '0.7rem',
                    fontWeight: '700',
                    minWidth: '48px',
                    textAlign: 'center',
                    background: `${methodColor[ep.method]}20`,
                    color: methodColor[ep.method]
                  }}>{ep.method}</span>
                  <code style={{ color: '#e2e8f0', fontSize: '0.8rem', flex: 1 }}>{ep.path}</code>
                  <span style={{ color: '#64748b', fontSize: '0.78rem', flex: 2 }}>{ep.desc}</span>
                  <span style={{ color: '#10b981', fontSize: '0.7rem', background: 'rgba(16,185,129,0.1)', padding: '0.15rem 0.4rem', borderRadius: '4px' }}>
                    {ep.rateLimit}
                  </span>
                  <span style={{ color: '#94a3b8', fontSize: '0.75rem' }}>{ep.status}</span>
                  <ArrowRight size={14} style={{ color: '#475569' }} />
                </div>
              ))}
            </div>
          </div>
          {/* Code Sample */}
          <div>
            <div style={{
              background: '#070b19',
              borderRadius: '10px',
              border: '1px solid rgba(255,255,255,0.08)',
              overflow: 'hidden'
            }}>
              <div style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '0.75rem 1rem',
                borderBottom: '1px solid rgba(255,255,255,0.05)',
                background: '#0a101f'
              }}>
                <span style={{ color: '#94a3b8', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Terminal size={14} />cURL Example
                </span>
                <button onClick={handleCopy} style={{
                  background: 'none', border: 'none', cursor: 'pointer',
                  color: copied ? 'var(--primary-color)' : '#64748b',
                  display: 'flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.75rem'
                }}>
                  <Copy size={13} />{copied ? 'Copied!' : 'Copy'}
                </button>
              </div>
              <pre style={{
                padding: '1.25rem',
                color: '#10b981',
                fontSize: '0.72rem',
                lineHeight: '1.7',
                overflowX: 'auto',
                margin: 0,
                whiteSpace: 'pre-wrap'
              }}>{SAMPLE_CURL}</pre>
            </div>

            <div style={{ marginTop: '1rem', background: '#0f172a', border: '1px solid rgba(255,255,255,0.05)', borderRadius: '10px', padding: '1rem' }}>
              <h4 style={{ color: '#fff', fontSize: '0.85rem', marginBottom: '0.75rem' }}>Response — 200 OK</h4>
              <pre style={{ color: '#10b981', fontSize: '0.72rem', lineHeight: '1.6', margin: 0 }}>{`{
  "message_id": "msg_0x7bc3a",
  "status": "delivered",
  "channel": "line",
  "latency_ms": 187,
  "timestamp": "2026-08-10T11:01:00Z"
}`}</pre>
            </div>
          </div>
        </div>
      )}

      {/* System Health Tab */}
      {activeTab === 'health' && (
        <div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem' }}>
            <h3 style={{ color: '#fff', fontSize: '1rem' }}>Real-time System Status</h3>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#10b981', fontSize: '0.8rem' }}>
              <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#10b981', animation: 'pulse 2s infinite' }} />
              All Systems Operational — Live
            </div>
          </div>

          {/* SLA Bar */}
          <div style={{
            background: 'linear-gradient(135deg, rgba(16,185,129,0.08), rgba(59,130,246,0.06))',
            border: '1px solid rgba(16,185,129,0.2)',
            borderRadius: '12px',
            padding: '1.25rem',
            marginBottom: '1.25rem',
            display: 'flex',
            gap: '3rem',
            alignItems: 'center'
          }}>
            <div>
              <div style={{ color: '#94a3b8', fontSize: '0.8rem' }}>30-Day Uptime SLA</div>
              <div style={{ color: '#10b981', fontSize: '2rem', fontWeight: '800' }}>99.99%</div>
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ height: '8px', background: 'rgba(255,255,255,0.05)', borderRadius: '4px', overflow: 'hidden' }}>
                <div style={{ height: '100%', width: '99.99%', background: 'linear-gradient(90deg, #10b981, #00c28e)', borderRadius: '4px', transition: 'width 1s ease' }} />
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '0.3rem' }}>
                <span style={{ color: '#475569', fontSize: '0.7rem' }}>0%</span>
                <span style={{ color: '#475569', fontSize: '0.7rem' }}>100%</span>
              </div>
            </div>
            <div>
              <div style={{ color: '#94a3b8', fontSize: '0.8rem' }}>Target</div>
              <div style={{ color: '#94a3b8', fontSize: '1.4rem', fontWeight: '600' }}>99.99%</div>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem' }}>
            {healthData.map((m, i) => (
              <div key={i} style={{
                background: '#0f172a',
                border: `1px solid ${statusColor[m.status]}30`,
                borderRadius: '12px',
                padding: '1.25rem'
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem' }}>
                  <span style={{ color: '#94a3b8', fontSize: '0.8rem' }}>{m.label}</span>
                  <span style={{
                    padding: '0.15rem 0.5rem',
                    borderRadius: '4px',
                    fontSize: '0.65rem',
                    fontWeight: '600',
                    background: `${statusColor[m.status]}20`,
                    color: statusColor[m.status]
                  }}>{m.status.toUpperCase()}</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.25rem' }}>
                  <span style={{ color: statusColor[m.status], fontSize: '1.75rem', fontWeight: '800' }}>
                    {m.unit === '%' ? m.value.toFixed(2) : m.value}
                  </span>
                  <span style={{ color: '#64748b', fontSize: '0.85rem' }}>{m.unit}</span>
                </div>
                <div style={{ color: m.trend.startsWith('-') || m.trend === '0' ? '#10b981' : '#f59e0b', fontSize: '0.75rem', marginTop: '0.25rem' }}>
                  {m.trend !== '0' ? m.trend : 'No change'}
                </div>
              </div>
            ))}
          </div>

          {/* Latency sparkline */}
          <div style={{ marginTop: '1.25rem', background: '#0f172a', border: '1px solid rgba(255,255,255,0.05)', borderRadius: '12px', padding: '1.25rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem' }}>
              <span style={{ color: '#fff', fontSize: '0.9rem' }}>API Latency (last 24 data points)</span>
              <span style={{ color: '#10b981', fontSize: '0.8rem' }}>avg {Math.round(latencyHistory.reduce((a,b)=>a+b,0)/latencyHistory.length)}ms</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'flex-end', gap: '4px', height: '60px' }}>
              {latencyHistory.map((v, i) => (
                <div key={i} style={{
                  flex: 1,
                  height: `${(v / 30) * 100}%`,
                  background: v > 20 ? '#f59e0b' : 'var(--primary-color)',
                  borderRadius: '3px 3px 0 0',
                  opacity: 0.7 + i * 0.025,
                  transition: 'height 0.5s ease'
                }} />
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Data Migration Tab */}
      {activeTab === 'migration' && (
        <div style={{ maxWidth: '720px' }}>
          <h3 style={{ color: '#fff', fontSize: '1rem', marginBottom: '0.5rem' }}>Data Migration Tool</h3>
          <p style={{ color: '#64748b', fontSize: '0.85rem', marginBottom: '1.5rem' }}>
            One-click import from competitors (Manychat, Freshchat, Zendesk). Supports CSV/Excel up to 500,000 contacts.
          </p>

          {/* Stepper */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0', marginBottom: '2rem' }}>
            {MIGRATION_STEPS.map((step, i) => (
              <div key={step.id} style={{ display: 'flex', alignItems: 'center', flex: 1 }}>
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.5rem', flex: 1 }}>
                  <div style={{
                    width: '40px', height: '40px', borderRadius: '50%',
                    background: migrationStep > i ? 'var(--primary-color)' : migrationStep === i && migrating ? 'rgba(0,194,142,0.2)' : '#1e293b',
                    border: `2px solid ${migrationStep > i ? 'var(--primary-color)' : migrationStep === i && migrating ? 'var(--primary-color)' : 'rgba(255,255,255,0.1)'}`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    color: migrationStep > i ? '#fff' : migrationStep === i && migrating ? 'var(--primary-color)' : '#64748b',
                    transition: 'all 0.5s ease'
                  }}>
                    {migrationStep > i ? <CheckCircle size={18} /> : step.icon}
                  </div>
                  <span style={{ color: migrationStep >= i ? '#fff' : '#64748b', fontSize: '0.78rem', fontWeight: migrationStep >= i ? '600' : '400', textAlign: 'center' }}>
                    {step.label}
                  </span>
                  <span style={{ color: '#475569', fontSize: '0.7rem', textAlign: 'center' }}>{step.desc}</span>
                </div>
                {i < MIGRATION_STEPS.length - 1 && (
                  <div style={{
                    height: '2px', width: '40px', flexShrink: 0,
                    background: migrationStep > i ? 'var(--primary-color)' : 'rgba(255,255,255,0.05)',
                    transition: 'background 0.5s ease',
                    alignSelf: 'flex-start', marginTop: '20px'
                  }} />
                )}
              </div>
            ))}
          </div>

          {/* Drop zone */}
          <div style={{
            border: '2px dashed rgba(0,194,142,0.3)',
            borderRadius: '12px',
            padding: '2.5rem',
            textAlign: 'center',
            background: 'rgba(0,194,142,0.02)',
            marginBottom: '1.5rem',
            cursor: 'pointer'
          }}>
            <Upload size={32} style={{ color: 'var(--primary-color)', marginBottom: '0.75rem', opacity: 0.7 }} />
            <div style={{ color: '#e2e8f0', fontWeight: '600', marginBottom: '0.25rem' }}>
              {migrationStep === 0 ? 'Drop your CSV or Excel file here' : migrationStep < MIGRATION_STEPS.length ? MIGRATION_STEPS[migrationStep - 1]?.label + ' complete' : '✓ Migration Complete!'}
            </div>
            <div style={{ color: '#64748b', fontSize: '0.8rem' }}>supports .csv, .xlsx, .xls — max 500,000 rows</div>
          </div>

          {/* Progress bar */}
          {(migrating || migrationStep > 0) && (
            <div style={{ marginBottom: '1.5rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
                <span style={{ color: '#94a3b8', fontSize: '0.8rem' }}>
                  {migrating ? MIGRATION_STEPS[migrationStep]?.label || 'Processing...' : 'Import Complete'}
                </span>
                <span style={{ color: 'var(--primary-color)', fontSize: '0.8rem' }}>{uploadProgress}%</span>
              </div>
              <div style={{ height: '6px', background: 'rgba(255,255,255,0.05)', borderRadius: '3px', overflow: 'hidden' }}>
                <div style={{
                  height: '100%', width: `${uploadProgress}%`,
                  background: 'linear-gradient(90deg, var(--primary-color), #3b82f6)',
                  borderRadius: '3px', transition: 'width 0.2s ease'
                }} />
              </div>
            </div>
          )}

          <div style={{ display: 'flex', gap: '1rem' }}>
            <button
              onClick={handleStartMigration}
              disabled={migrating}
              style={{
                flex: 1, padding: '0.875rem',
                background: migrating ? 'rgba(0,194,142,0.2)' : 'var(--primary-color)',
                border: 'none', borderRadius: '8px',
                color: '#fff', fontWeight: '700', fontSize: '0.9rem', cursor: migrating ? 'not-allowed' : 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem',
                transition: 'all 0.2s'
              }}
            >
              {migrating ? <><RefreshCw size={16} style={{ animation: 'spin 1s linear infinite' }} />Processing...</> : <><Zap size={16} />Start Import</>}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
