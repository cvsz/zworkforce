import { ArrowRight, Network, CheckCircle2, Zap, Play, Settings } from 'lucide-react';

export default function ProductAutomations({ onLaunchApp, isDark }) {
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
          No-Code Automation
        </span>
        <h1 style={{ fontSize: '3rem', margin: '1rem 0 0.5rem 0', letterSpacing: '-0.03em' }}>
          Visual Chat Flow Builder
        </h1>
        <p style={{ color: mutedColor, fontSize: '1.1rem', maxWidth: '650px', margin: '0 auto' }}>
          Design multi-step customer journeys, conditional branch checkpoints, and automated shop triggers without writing a single line of code.
        </p>
        <button onClick={onLaunchApp} className="btn-primary" style={{ margin: '1.5rem auto 0 auto' }}>
          Open Flow Builder <ArrowRight size={16} />
        </button>
      </div>

      {/* Feature Highlight Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '3rem', alignItems: 'center', marginBottom: '5rem' }}>
        {/* Visual Mock Canvas */}
        <div style={{
          backgroundColor: isDark ? 'rgba(15, 23, 42, 0.4)' : '#fff',
          border: `1px solid ${isDark ? 'var(--dark-border)' : 'var(--light-border)'}`,
          borderRadius: '16px',
          padding: '1.5rem',
          boxShadow: '0 10px 40px rgba(0, 0, 0, 0.1)',
          display: 'flex',
          flexDirection: 'column',
          gap: '1rem'
        }}>
          <span style={{ fontWeight: '700', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
            <Network size={16} style={{ color: 'var(--primary-color)' }} /> Automation Canvas Preview
          </span>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', position: 'relative' }}>
            {/* Trigger node */}
            <div style={{ padding: '0.75rem', borderRadius: '8px', borderLeft: '4px solid #10b981', backgroundColor: isDark ? 'rgba(255,255,255,0.02)' : '#f8fafc', border: `1px solid ${isDark ? 'var(--dark-border)' : 'var(--light-border)'}` }}>
              <div style={{ fontWeight: '700', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                <Zap size={12} style={{ color: '#10b981' }} /> Trigger: Customer Keyword
              </div>
              <div style={{ fontSize: '0.75rem', color: mutedColor }}>contains "price" or "discount"</div>
            </div>

            {/* Condition node */}
            <div style={{ padding: '0.75rem', borderRadius: '8px', borderLeft: '4px solid #f59e0b', backgroundColor: isDark ? 'rgba(255,255,255,0.02)' : '#f8fafc', border: `1px solid ${isDark ? 'var(--dark-border)' : 'var(--light-border)'}` }}>
              <div style={{ fontWeight: '700', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                <Settings size={12} style={{ color: '#f59e0b' }} /> Condition: VIP Status
              </div>
              <div style={{ fontSize: '0.75rem', color: mutedColor }}>Is tag "VIP Customer"?</div>
            </div>

            {/* Action node */}
            <div style={{ padding: '0.75rem', borderRadius: '8px', borderLeft: '4px solid ' + 'var(--primary-color)', backgroundColor: isDark ? 'rgba(255,255,255,0.02)' : '#f8fafc', border: `1px solid ${isDark ? 'var(--dark-border)' : 'var(--light-border)'}` }}>
              <div style={{ fontWeight: '700', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                <Play size={12} style={{ color: 'var(--primary-color)' }} /> Action: Send WhatsApp Promo
              </div>
              <div style={{ fontSize: '0.75rem', color: mutedColor }}>Send VIP coupon details template</div>
            </div>
          </div>
        </div>

        <div>
          <h2 style={{ fontSize: '2rem', marginBottom: '1rem', letterSpacing: '-0.02em' }}>
            Scale Your Operations with Visual Flows
          </h2>
          <p style={{ color: mutedColor, lineHeight: '1.6', marginBottom: '1.5rem' }}>
            Ensure your store operates 24/7 without needing staff online. Design logic trees that greet new customers, check shopify catalogs, collect customer emails, and distribute coupons instantly.
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-start' }}>
              <CheckCircle2 size={20} style={{ color: 'var(--primary-color)', flexShrink: 0, marginTop: '0.2rem' }} />
              <div>
                <strong>Flexible Conditional Branching:</strong> Check tag states, incoming channels, and response parameters before executing actions.
              </div>
            </div>
            <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-start' }}>
              <CheckCircle2 size={20} style={{ color: 'var(--primary-color)', flexShrink: 0, marginTop: '0.2rem' }} />
              <div>
                <strong>Shopify Action Nodes:</strong> Trigger cart link displays, order confirmations, and abandoned checkout followups automatically.
              </div>
            </div>
            <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-start' }}>
              <CheckCircle2 size={20} style={{ color: 'var(--primary-color)', flexShrink: 0, marginTop: '0.2rem' }} />
              <div>
                <strong>Instant Channel Publishing:</strong> Map your automation trees instantly to active WhatsApp templates and LINE Official Account bots.
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
