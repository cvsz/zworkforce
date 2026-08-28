import { useState } from 'react';
import { 
  Clock, CheckCircle2, DollarSign, MessageSquare, 
  ArrowUpRight, ArrowDownRight, Award, Zap, Activity 
} from 'lucide-react';

const AGENTS = [
  { name: 'Sarah Connor', assigned: 142, response: '1.2 mins', resolution: '98.2%', status: 'online' },
  { name: 'Alex Rivera', assigned: 120, response: '2.1 mins', resolution: '96.5%', status: 'online' },
  { name: 'Automated AI Bot', assigned: 489, response: 'Instant (< 1s)', resolution: '89.1%', status: 'active' },
  { name: 'Marcus Wright', assigned: 65, response: '3.8 mins', resolution: '94.0%', status: 'away' }
];

export default function Analytics() {
  const [agents, setAgents] = useState(AGENTS);

  const toggleAgentStatus = (name) => {
    setAgents(prev => prev.map(a => {
      if (a.name === name) {
        const nextStatus = a.status === 'online' ? 'away' : a.status === 'away' ? 'offline' : 'online';
        return { ...a, status: nextStatus };
      }
      return a;
    }));
  };

  return (
    <div style={{ padding: '2rem', height: '100%', overflowY: 'auto' }}>
      {/* Page Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <div>
          <h2 style={{ fontSize: '1.75rem', color: '#fff', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <Activity size={28} style={{ color: 'var(--primary-color)' }} />
            Analytics Dashboard
          </h2>
          <p style={{ color: '#94a3b8', fontSize: '0.9rem', marginTop: '0.25rem' }}>
            Track team performance, channel volume, response metrics, and conversion statistics in real-time.
          </p>
        </div>
      </div>

      {/* Metric Cards Row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1.5rem', marginBottom: '2rem' }}>
        {/* Card 1: Total Conversations */}
        <div style={{ backgroundColor: '#0f172a', border: '1px solid rgba(255, 255, 255, 0.05)', borderRadius: '12px', padding: '1.25rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', color: '#64748b', fontSize: '0.8rem', fontWeight: '600' }}>
            <span>CONVERSATIONS</span>
            <MessageSquare size={16} />
          </div>
          <div style={{ fontSize: '1.8rem', color: '#fff', fontWeight: '700', margin: '0.5rem 0' }}>8,245</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.75rem', color: '#10b981' }}>
            <ArrowUpRight size={14} />
            <span>+14.2%</span>
            <span style={{ color: '#64748b', marginLeft: '0.25rem' }}>vs last week</span>
          </div>
        </div>

        {/* Card 2: Avg Response Time */}
        <div style={{ backgroundColor: '#0f172a', border: '1px solid rgba(255, 255, 255, 0.05)', borderRadius: '12px', padding: '1.25rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', color: '#64748b', fontSize: '0.8rem', fontWeight: '600' }}>
            <span>AVG RESPONSE TIME</span>
            <Clock size={16} />
          </div>
          <div style={{ fontSize: '1.8rem', color: '#fff', fontWeight: '700', margin: '0.5rem 0' }}>1.8 mins</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.75rem', color: '#10b981' }}>
            <ArrowDownRight size={14} style={{ transform: 'rotate(90deg)' }} />
            <span>-24.5%</span>
            <span style={{ color: '#64748b', marginLeft: '0.25rem' }}>faster speed</span>
          </div>
        </div>

        {/* Card 3: Resolution Rate */}
        <div style={{ backgroundColor: '#0f172a', border: '1px solid rgba(255, 255, 255, 0.05)', borderRadius: '12px', padding: '1.25rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', color: '#64748b', fontSize: '0.8rem', fontWeight: '600' }}>
            <span>RESOLUTION RATE</span>
            <CheckCircle2 size={16} />
          </div>
          <div style={{ fontSize: '1.8rem', color: '#fff', fontWeight: '700', margin: '0.5rem 0' }}>96.8%</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.75rem', color: '#10b981' }}>
            <ArrowUpRight size={14} />
            <span>+2.1%</span>
            <span style={{ color: '#64748b', marginLeft: '0.25rem' }}>resolved chats</span>
          </div>
        </div>

        {/* Card 4: AI Assisted Shopify Sales */}
        <div style={{ backgroundColor: '#0f172a', border: '1px solid rgba(255, 255, 255, 0.05)', borderRadius: '12px', padding: '1.25rem', position: 'relative', overflow: 'hidden' }}>
          <div style={{
            position: 'absolute',
            right: '-10px',
            top: '-10px',
            backgroundColor: 'rgba(0, 194, 142, 0.1)',
            color: 'var(--primary-color)',
            padding: '1rem',
            borderRadius: '50%'
          }}>
            <Zap size={24} className="glow-active" />
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', color: '#64748b', fontSize: '0.8rem', fontWeight: '600', paddingRight: '2rem' }}>
            <span>AI SHOP SALES</span>
            <DollarSign size={16} />
          </div>
          <div style={{ fontSize: '1.8rem', color: '#fff', fontWeight: '700', margin: '0.5rem 0' }}>$14,582.00</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.75rem', color: '#10b981' }}>
            <ArrowUpRight size={14} />
            <span>+38.5%</span>
            <span style={{ color: '#64748b', marginLeft: '0.25rem' }}>chat checkouts</span>
          </div>
        </div>
      </div>

      {/* Grid: Charts breakdown */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem', marginBottom: '2rem' }}>
        {/* Left Side: Channel Volume Breakdown */}
        <div style={{
          backgroundColor: '#0f172a',
          border: '1px solid rgba(255, 255, 255, 0.05)',
          borderRadius: '12px',
          padding: '1.5rem'
        }}>
          <h3 style={{ fontSize: '1.1rem', color: '#fff', marginBottom: '1.5rem' }}>Channel Distribution Volume</h3>
          
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            {/* WhatsApp */}
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', color: '#f8fafc', marginBottom: '0.5rem' }}>
                <span>WhatsApp Commerce</span>
                <span style={{ fontWeight: '600' }}>3,710 messages (45%)</span>
              </div>
              <div style={{ height: '8px', backgroundColor: '#11192e', borderRadius: '4px', overflow: 'hidden' }}>
                <div style={{ width: '45%', height: '100%', backgroundColor: '#25d366', borderRadius: '4px' }}></div>
              </div>
            </div>

            {/* LINE OA */}
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', color: '#f8fafc', marginBottom: '0.5rem' }}>
                <span>LINE Official Account</span>
                <span style={{ fontWeight: '600' }}>2,473 messages (30%)</span>
              </div>
              <div style={{ height: '8px', backgroundColor: '#11192e', borderRadius: '4px', overflow: 'hidden' }}>
                <div style={{ width: '30%', height: '100%', backgroundColor: '#06c15f', borderRadius: '4px' }}></div>
              </div>
            </div>

            {/* Messenger / Instagram */}
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', color: '#f8fafc', marginBottom: '0.5rem' }}>
                <span>Meta Social DM (FB/IG)</span>
                <span style={{ fontWeight: '600' }}>1,236 messages (15%)</span>
              </div>
              <div style={{ height: '8px', backgroundColor: '#11192e', borderRadius: '4px', overflow: 'hidden' }}>
                <div style={{ width: '15%', height: '100%', backgroundColor: '#0084ff', borderRadius: '4px' }}></div>
              </div>
            </div>

            {/* TikTok & Shopify Chat */}
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', color: '#f8fafc', marginBottom: '0.5rem' }}>
                <span>TikTok Shop & Shopify widget</span>
                <span style={{ fontWeight: '600' }}>826 messages (10%)</span>
              </div>
              <div style={{ height: '8px', backgroundColor: '#11192e', borderRadius: '4px', overflow: 'hidden' }}>
                <div style={{ width: '10%', height: '100%', backgroundColor: 'var(--primary-color)', borderRadius: '4px' }}></div>
              </div>
            </div>
          </div>
        </div>

        {/* Right Side: Hourly Traffic Volume Mock */}
        <div style={{
          backgroundColor: '#0f172a',
          border: '1px solid rgba(255, 255, 255, 0.05)',
          borderRadius: '12px',
          padding: '1.5rem',
          display: 'flex',
          flexDirection: 'column'
        }}>
          <h3 style={{ fontSize: '1.1rem', color: '#fff', marginBottom: '1.5rem' }}>Daily Chat Traffic Load</h3>
          
          <div style={{
            flex: 1,
            display: 'flex',
            alignItems: 'flex-end',
            justifyContent: 'space-between',
            height: '160px',
            paddingTop: '1rem',
            borderBottom: '1px solid rgba(255, 255, 255, 0.1)'
          }}>
            {[40, 65, 80, 50, 95, 110, 85, 60, 45, 30].map((h, i) => (
              <div key={i} style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                flex: 1,
                gap: '0.5rem'
              }}>
                <div
                  title={`${h} chats`}
                  style={{
                    width: '18px',
                    height: `${h}px`,
                    background: 'linear-gradient(to top, var(--primary-color), #05ffd2)',
                    borderRadius: '4px 4px 0 0',
                    transition: 'height 0.3s'
                  }}
                />
              </div>
            ))}
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', color: '#64748b', fontSize: '0.7rem', marginTop: '0.5rem' }}>
            <span>9:00 AM</span>
            <span>12:00 PM</span>
            <span>3:00 PM</span>
            <span>6:00 PM</span>
            <span>9:00 PM</span>
          </div>
        </div>
      </div>

      {/* Agent Performance Log */}
      <div style={{
        backgroundColor: '#0f172a',
        border: '1px solid rgba(255, 255, 255, 0.05)',
        borderRadius: '12px',
        padding: '1.5rem'
      }}>
        <h3 style={{ fontSize: '1.1rem', color: '#fff', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Award size={18} style={{ color: 'var(--primary-color)' }} />
          Operator & Agent Efficiency
        </h3>

        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem', textAlign: 'left' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.1)', color: '#64748b' }}>
                <th style={{ padding: '0.75rem 0.5rem' }}>Agent Name</th>
                <th style={{ padding: '0.75rem 0.5rem' }}>Conversations Handled</th>
                <th style={{ padding: '0.75rem 0.5rem' }}>Avg Response Speed</th>
                <th style={{ padding: '0.75rem 0.5rem' }}>Resolution Rating</th>
                <th style={{ padding: '0.75rem 0.5rem' }}>Status Control</th>
              </tr>
            </thead>
            <tbody>
              {agents.map(a => (
                <tr key={a.name} style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.02)', color: '#e2e8f0' }}>
                  <td style={{ padding: '0.75rem 0.5rem', fontWeight: '600' }}>{a.name}</td>
                  <td style={{ padding: '0.75rem 0.5rem' }}>{a.assigned}</td>
                  <td style={{ padding: '0.75rem 0.5rem', color: 'var(--primary-color)' }}>{a.response}</td>
                  <td style={{ padding: '0.75rem 0.5rem', fontWeight: '600' }}>{a.resolution}</td>
                  <td style={{ padding: '0.75rem 0.5rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span style={{
                        width: '8px',
                        height: '8px',
                        borderRadius: '50%',
                        backgroundColor: a.status === 'online' || a.status === 'active' ? '#10b981' : a.status === 'away' ? '#f59e0b' : '#ef4444'
                      }} />
                      <button
                        onClick={() => toggleAgentStatus(a.name)}
                        style={{
                          backgroundColor: '#1e293b',
                          color: '#f8fafc',
                          border: 'none',
                          borderRadius: '4px',
                          padding: '0.2rem 0.5rem',
                          fontSize: '0.7rem',
                          cursor: 'pointer',
                          textTransform: 'capitalize'
                        }}
                      >
                        {a.status}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
