import { useState, useEffect } from 'react';
import { TrendingUp, MapPin, Radio, BarChart2, ShoppingBag, Target, Zap, ArrowUpRight, Clock, DollarSign, Users } from 'lucide-react';

const ATTRIBUTION_MODELS = [
  { id: 'linear', label: 'Linear', desc: 'Equal credit to each touchpoint' },
  { id: 'time_decay', label: 'Time-Decay', desc: 'More credit to recent touches' },
  { id: 'first_touch', label: 'First Touch', desc: 'Full credit to first channel' },
  { id: 'last_touch', label: 'Last Touch', desc: 'Full credit to last channel' },
];

const TOUCHPOINTS = [
  { channel: 'LINE OA', icon: '💬', credit: { linear: 25, time_decay: 15, first_touch: 0, last_touch: 0 } },
  { channel: 'Facebook Ad', icon: '📘', credit: { linear: 25, time_decay: 10, first_touch: 100, last_touch: 0 } },
  { channel: 'TikTok Shop', icon: '🎵', credit: { linear: 25, time_decay: 30, first_touch: 0, last_touch: 0 } },
  { channel: 'WhatsApp Broadcast', icon: '📱', credit: { linear: 25, time_decay: 45, first_touch: 0, last_touch: 100 } },
];

const POS_LOCATIONS = [
  { name: 'Central World — BKK', platform: 'Wongnai', status: 'synced', lastSync: '2 min ago', orders: 47, revenue: '฿34,200' },
  { name: 'Terminal 21 — BKK', platform: 'PointSpot', status: 'synced', lastSync: '5 min ago', orders: 23, revenue: '฿18,900' },
  { name: 'Maya Mall — CNX', platform: 'Wongnai', status: 'syncing', lastSync: 'Syncing...', orders: 12, revenue: '฿8,700' },
  { name: 'Nimman — CNX', platform: 'PointSpot', status: 'error', lastSync: '3 hrs ago', orders: 0, revenue: '—' },
];

const BROADCAST_TRIGGERS = [
  { id: 'cart', trigger: 'Cart Abandoned > 30 min', sent: 2840, opened: 1920, conversion: '18.4%', status: 'active' },
  { id: 'visit', trigger: 'Product page viewed 3x', sent: 1240, opened: 890, conversion: '12.1%', status: 'active' },
  { id: 'win', trigger: 'High-value segment (฿5K+)', sent: 480, opened: 392, conversion: '31.2%', status: 'active' },
  { id: 'reeng', trigger: 'No purchase in 30 days', sent: 3200, opened: 1100, conversion: '6.8%', status: 'paused' },
];

export default function MarketingO2O() {
  const [activeTab, setActiveTab] = useState('attribution');
  const [selectedModel, setSelectedModel] = useState('linear');
  const [posData, setPosData] = useState(POS_LOCATIONS);
  const [liveOrders, setLiveOrders] = useState(82);
  const [liveRevenue, setLiveRevenue] = useState(61800);

  // Simulate live POS sync
  useEffect(() => {
    const interval = setInterval(() => {
      setLiveOrders(prev => prev + Math.floor(Math.random() * 3));
      setLiveRevenue(prev => prev + Math.floor(Math.random() * 800 + 200));
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  const tabs = [
    { id: 'attribution', label: 'Multi-Touch Attribution', icon: <Target size={15} /> },
    { id: 'pos', label: 'POS Integration', icon: <MapPin size={15} /> },
    { id: 'broadcast', label: 'Behavioral Broadcast', icon: <Radio size={15} /> },
  ];

  const statusColor = { synced: '#10b981', syncing: '#f59e0b', error: '#ef4444' };

  return (
    <div style={{ padding: '2rem', height: '100%', overflowY: 'auto' }}>
      <div style={{ marginBottom: '1.75rem' }}>
        <h2 style={{ fontSize: '1.75rem', color: '#fff', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <TrendingUp size={28} style={{ color: 'var(--primary-color)' }} />
          Marketing & O2O Commerce
        </h2>
        <p style={{ color: '#94a3b8', fontSize: '0.9rem', marginTop: '0.25rem' }}>
          Multi-touch attribution, offline POS sync, and behavioral broadcast automation.
        </p>
      </div>

      {/* Tab Bar */}
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem', flexWrap: 'wrap' }}>
        {tabs.map(t => (
          <button key={t.id} onClick={() => setActiveTab(t.id)} style={{
            display: 'flex', alignItems: 'center', gap: '0.4rem', padding: '0.5rem 1rem',
            borderRadius: '8px', border: 'none', cursor: 'pointer', fontSize: '0.85rem',
            fontWeight: activeTab === t.id ? '600' : '400',
            background: activeTab === t.id ? 'var(--primary-color)' : 'rgba(255,255,255,0.05)',
            color: activeTab === t.id ? '#fff' : '#94a3b8', transition: 'all 0.2s'
          }}>{t.icon}{t.label}</button>
        ))}
      </div>

      {/* Multi-Touch Attribution */}
      {activeTab === 'attribution' && (
        <div>
          {/* Model selector */}
          <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1.5rem', flexWrap: 'wrap' }}>
            {ATTRIBUTION_MODELS.map(m => (
              <button key={m.id} onClick={() => setSelectedModel(m.id)} style={{
                padding: '0.625rem 1.25rem', borderRadius: '10px', border: 'none', cursor: 'pointer',
                background: selectedModel === m.id ? 'rgba(0,194,142,0.12)' : 'rgba(255,255,255,0.04)',
                border: `1px solid ${selectedModel === m.id ? 'rgba(0,194,142,0.3)' : 'rgba(255,255,255,0.06)'}`,
                color: selectedModel === m.id ? 'var(--primary-color)' : '#94a3b8',
                fontWeight: selectedModel === m.id ? '700' : '400',
                fontSize: '0.85rem', transition: 'all 0.2s', textAlign: 'left'
              }}>
                <div>{m.label}</div>
                <div style={{ fontSize: '0.7rem', opacity: 0.7, fontWeight: '400', marginTop: '0.1rem' }}>{m.desc}</div>
              </button>
            ))}
          </div>

          {/* Touchpoint funnel */}
          <div style={{ background: '#0f172a', borderRadius: '12px', padding: '1.5rem', marginBottom: '1.25rem' }}>
            <div style={{ color: '#fff', fontWeight: '600', marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <BarChart2 size={16} style={{ color: 'var(--primary-color)' }} />
              Credit Distribution — {ATTRIBUTION_MODELS.find(m => m.id === selectedModel)?.label} Model
            </div>
            {TOUCHPOINTS.map((tp, i) => {
              const credit = tp.credit[selectedModel];
              return (
                <div key={i} style={{ marginBottom: '1rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
                    <span style={{ color: '#e2e8f0', fontSize: '0.875rem' }}>{tp.icon} {tp.channel}</span>
                    <span style={{ color: credit > 0 ? 'var(--primary-color)' : '#475569', fontWeight: '700', fontSize: '0.875rem' }}>
                      {credit}%
                    </span>
                  </div>
                  <div style={{ height: '8px', background: 'rgba(255,255,255,0.05)', borderRadius: '4px', overflow: 'hidden' }}>
                    <div style={{
                      height: '100%', width: `${credit}%`,
                      background: `linear-gradient(90deg, var(--primary-color), #3b82f6)`,
                      borderRadius: '4px', transition: 'width 0.8s ease'
                    }} />
                  </div>
                </div>
              );
            })}
          </div>

          {/* Attribution summary cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem' }}>
            {[
              { label: 'Total Attributed Revenue', value: '฿284,500', delta: '+12.4%', icon: <DollarSign size={16} /> },
              { label: 'Avg. Touches to Convert', value: '3.7', delta: '-0.3', icon: <Target size={16} /> },
              { label: 'Best Performing Channel', value: selectedModel === 'last_touch' ? 'WhatsApp' : selectedModel === 'first_touch' ? 'Facebook Ad' : 'LINE OA', delta: 'Top ROI', icon: <ArrowUpRight size={16} /> },
            ].map((s, i) => (
              <div key={i} style={{ background: '#0f172a', border: '1px solid rgba(255,255,255,0.05)', borderRadius: '12px', padding: '1.25rem' }}>
                <div style={{ color: '#64748b', fontSize: '0.78rem', display: 'flex', alignItems: 'center', gap: '0.35rem', marginBottom: '0.5rem' }}>
                  {s.icon}{s.label}
                </div>
                <div style={{ color: '#fff', fontSize: '1.4rem', fontWeight: '800' }}>{s.value}</div>
                <div style={{ color: 'var(--primary-color)', fontSize: '0.78rem', marginTop: '0.25rem' }}>{s.delta}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* POS Integration */}
      {activeTab === 'pos' && (
        <div>
          {/* Live counter */}
          <div style={{
            background: 'linear-gradient(135deg, rgba(0,194,142,0.08), rgba(59,130,246,0.05))',
            border: '1px solid rgba(0,194,142,0.2)', borderRadius: '12px',
            padding: '1.25rem', marginBottom: '1.5rem',
            display: 'flex', gap: '3rem', alignItems: 'center'
          }}>
            <div>
              <div style={{ color: '#94a3b8', fontSize: '0.8rem', marginBottom: '0.25rem' }}>Live Orders (all stores)</div>
              <div style={{ color: 'var(--primary-color)', fontSize: '2rem', fontWeight: '800', transition: 'color 0.3s' }}>
                {liveOrders.toLocaleString()}
              </div>
            </div>
            <div>
              <div style={{ color: '#94a3b8', fontSize: '0.8rem', marginBottom: '0.25rem' }}>Today Revenue (Offline)</div>
              <div style={{ color: '#fff', fontSize: '2rem', fontWeight: '800' }}>
                ฿{liveRevenue.toLocaleString()}
              </div>
            </div>
            <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#10b981', fontSize: '0.85rem' }}>
              <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#10b981', animation: 'pulse 2s infinite' }} />
              Syncing with POS systems
            </div>
          </div>

          {/* Location cards */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {posData.map((loc, i) => (
              <div key={i} style={{
                background: '#0f172a', border: `1px solid rgba(255,255,255,0.05)`,
                borderLeft: `3px solid ${statusColor[loc.status]}`,
                borderRadius: '12px', padding: '1.25rem',
                display: 'flex', alignItems: 'center', gap: '1.5rem'
              }}>
                <MapPin size={20} style={{ color: statusColor[loc.status], flexShrink: 0 }} />
                <div style={{ flex: 1 }}>
                  <div style={{ color: '#fff', fontWeight: '600', fontSize: '0.9rem' }}>{loc.name}</div>
                  <div style={{ color: '#64748b', fontSize: '0.78rem', marginTop: '0.2rem' }}>Platform: {loc.platform}</div>
                </div>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ color: '#94a3b8', fontSize: '0.72rem' }}>Orders Today</div>
                  <div style={{ color: '#fff', fontWeight: '700' }}>{loc.orders}</div>
                </div>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ color: '#94a3b8', fontSize: '0.72rem' }}>Revenue</div>
                  <div style={{ color: 'var(--primary-color)', fontWeight: '700' }}>{loc.revenue}</div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <span style={{
                    padding: '0.2rem 0.5rem', borderRadius: '4px', fontSize: '0.7rem', fontWeight: '600',
                    background: `${statusColor[loc.status]}20`, color: statusColor[loc.status]
                  }}>{loc.status.toUpperCase()}</span>
                  <div style={{ color: '#475569', fontSize: '0.7rem', marginTop: '0.25rem' }}>
                    <Clock size={10} style={{ display: 'inline', marginRight: '3px' }} />{loc.lastSync}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Behavioral Broadcast */}
      {activeTab === 'broadcast' && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
            <div style={{ color: '#94a3b8', fontSize: '0.85rem' }}>
              Trigger-based messages sent based on real customer behavior — not fixed schedules.
            </div>
            <button style={{
              padding: '0.5rem 1.25rem', background: 'var(--primary-color)', border: 'none',
              borderRadius: '8px', color: '#fff', fontWeight: '600', fontSize: '0.85rem', cursor: 'pointer',
              display: 'flex', alignItems: 'center', gap: '0.5rem'
            }}>
              <Zap size={15} />New Trigger
            </button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {BROADCAST_TRIGGERS.map((t, i) => (
              <div key={i} style={{
                background: '#0f172a', border: '1px solid rgba(255,255,255,0.05)', borderRadius: '12px',
                padding: '1.25rem', display: 'grid', gridTemplateColumns: '1fr 100px 100px 120px 80px',
                alignItems: 'center', gap: '1.5rem'
              }}>
                <div>
                  <div style={{ color: '#fff', fontSize: '0.9rem', fontWeight: '600' }}>{t.trigger}</div>
                  <div style={{ color: '#64748b', fontSize: '0.75rem', marginTop: '0.25rem' }}>Behavioral trigger · Auto-send</div>
                </div>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ color: '#94a3b8', fontSize: '0.7rem' }}>Sent</div>
                  <div style={{ color: '#fff', fontWeight: '700' }}>{t.sent.toLocaleString()}</div>
                </div>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ color: '#94a3b8', fontSize: '0.7rem' }}>Opened</div>
                  <div style={{ color: '#fff', fontWeight: '700' }}>{t.opened.toLocaleString()}</div>
                </div>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ color: '#94a3b8', fontSize: '0.7rem' }}>Conversion</div>
                  <div style={{ color: 'var(--primary-color)', fontWeight: '700', fontSize: '1.1rem' }}>{t.conversion}</div>
                </div>
                <span style={{
                  padding: '0.25rem 0.6rem', borderRadius: '6px', fontSize: '0.72rem', fontWeight: '600',
                  background: t.status === 'active' ? 'rgba(16,185,129,0.15)' : 'rgba(100,116,139,0.15)',
                  color: t.status === 'active' ? '#10b981' : '#64748b'
                }}>{t.status.toUpperCase()}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
