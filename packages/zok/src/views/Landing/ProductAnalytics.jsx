import { ArrowRight, Activity, CheckCircle2, Clock, DollarSign } from 'lucide-react';

export default function ProductAnalytics({ onLaunchApp, isDark }) {
  const textColor = isDark ? '#fff' : '#0f172a';
  const mutedColor = isDark ? 'var(--dark-text-muted)' : 'var(--light-text-muted)';
  
  return (
    <div className="container" style={{ padding: '4rem 0', color: textColor }}>
      {/* Hero Header */}
      <div style={{ textAlign: 'center', marginBottom: '4rem' }}>
        <span style={{
          fontSize: '0.85rem',
          color: 'var(--primary-color)',
          backgroundColor: 'rgba(0, 194, 142, 0.1)',
          padding: '0.4rem 0.8rem',
          borderRadius: '20px',
          fontWeight: '700',
          textTransform: 'uppercase',
          letterSpacing: '0.05em'
        }}>
          Business Intelligence
        </span>
        <h1 style={{ fontSize: '3rem', margin: '1rem 0 0.5rem 0', letterSpacing: '-0.03em' }}>
          Real-Time Chat Analytics
        </h1>
        <p style={{ color: mutedColor, fontSize: '1.1rem', maxWidth: '650px', margin: '0 auto' }}>
          Track response performance metrics, average resolution times, and team operator statistics from a single analytics dashboard.
        </p>
        <button onClick={onLaunchApp} className="btn-primary" style={{ margin: '1.5rem auto 0 auto' }}>
          Open Analytics Sandbox <ArrowRight size={16} />
        </button>
      </div>

      {/* Feature Highlight Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '3rem', alignItems: 'center', marginBottom: '5rem' }}>
        <div>
          <h2 style={{ fontSize: '2rem', marginBottom: '1rem', letterSpacing: '-0.02em' }}>
            Data-Driven Customer Operations
          </h2>
          <p style={{ color: mutedColor, lineHeight: '1.6', marginBottom: '1.5rem' }}>
            Get accurate insights into support load volumes, platform distribution channels, and agent response efficiencies. Understand where delays happen and monitor chat conversions in real time.
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-start' }}>
              <CheckCircle2 size={20} style={{ color: 'var(--primary-color)', flexShrink: 0, marginTop: '0.2rem' }} />
              <div>
                <strong>First Response Time (FRT):</strong> Track how fast your operators or AI bots greet incoming chat leads. Set warnings for response lags.
              </div>
            </div>
            <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-start' }}>
              <CheckCircle2 size={20} style={{ color: 'var(--primary-color)', flexShrink: 0, marginTop: '0.2rem' }} />
              <div>
                <strong>Channel Popularity Matrix:</strong> View which channel (LINE OA vs WhatsApp) brings in the highest conversion volume.
              </div>
            </div>
            <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-start' }}>
              <CheckCircle2 size={20} style={{ color: 'var(--primary-color)', flexShrink: 0, marginTop: '0.2rem' }} />
              <div>
                <strong>Operator Productivity Logs:</strong> Audit individual support agents on open cases resolved, messages handled, and response ratings.
              </div>
            </div>
          </div>
        </div>

        {/* Visual Charts Grid Mock */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: '1rem'
        }}>
          <div style={{
            backgroundColor: isDark ? 'rgba(15, 23, 42, 0.4)' : '#fff',
            border: `1px solid ${isDark ? 'var(--dark-border)' : 'var(--light-border)'}`,
            borderRadius: '12px',
            padding: '1.25rem',
            boxShadow: '0 4px 20px rgba(0,0,0,0.05)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem', color: mutedColor, fontSize: '0.8rem' }}>
              <Clock size={16} style={{ color: 'var(--primary-color)' }} /> Avg. FRT
            </div>
            <div style={{ fontSize: '1.8rem', fontWeight: '800' }}>1.2m</div>
            <span style={{ fontSize: '0.75rem', color: '#10b981' }}>↓ 14% vs last week</span>
          </div>

          <div style={{
            backgroundColor: isDark ? 'rgba(15, 23, 42, 0.4)' : '#fff',
            border: `1px solid ${isDark ? 'var(--dark-border)' : 'var(--light-border)'}`,
            borderRadius: '12px',
            padding: '1.25rem',
            boxShadow: '0 4px 20px rgba(0,0,0,0.05)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem', color: mutedColor, fontSize: '0.8rem' }}>
              <DollarSign size={16} style={{ color: 'var(--primary-color)' }} /> Sales Generated
            </div>
            <div style={{ fontSize: '1.8rem', fontWeight: '800' }}>$12,480</div>
            <span style={{ fontSize: '0.75rem', color: '#10b981' }}>↑ 22% vs last week</span>
          </div>

          <div style={{
            backgroundColor: isDark ? 'rgba(15, 23, 42, 0.4)' : '#fff',
            border: `1px solid ${isDark ? 'var(--dark-border)' : 'var(--light-border)'}`,
            borderRadius: '12px',
            padding: '1.25rem',
            boxShadow: '0 4px 20px rgba(0,0,0,0.05)',
            gridColumn: 'span 2'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem', color: mutedColor, fontSize: '0.8rem' }}>
              <Activity size={16} style={{ color: 'var(--primary-color)' }} /> Hourly Chat Load
            </div>
            {/* Visual graph column block representation */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', height: '80px', padding: '0 0.5rem' }}>
              <div style={{ width: '12%', height: '30%', backgroundColor: 'rgba(0, 194, 142, 0.2)', borderRadius: '3px' }}></div>
              <div style={{ width: '12%', height: '45%', backgroundColor: 'rgba(0, 194, 142, 0.2)', borderRadius: '3px' }}></div>
              <div style={{ width: '12%', height: '80%', backgroundColor: 'var(--primary-color)', borderRadius: '3px' }}></div>
              <div style={{ width: '12%', height: '60%', backgroundColor: 'rgba(0, 194, 142, 0.5)', borderRadius: '3px' }}></div>
              <div style={{ width: '12%', height: '90%', backgroundColor: 'var(--primary-color)', borderRadius: '3px' }}></div>
              <div style={{ width: '12%', height: '40%', backgroundColor: 'rgba(0, 194, 142, 0.2)', borderRadius: '3px' }}></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
